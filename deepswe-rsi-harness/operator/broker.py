#!/usr/bin/env python3
"""Operator-owned inference/research route. No CONNECT, arbitrary forwarding, or secrets in Work."""
import argparse
import base64
import hashlib
import http.client
import http.server
import io
import ipaddress
import json
import os
import secrets
import socket
import ssl
import sys
import tarfile
import threading
import time
import urllib.parse
import zipfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from provider import ProviderProxy


class Research:
    def __init__(self, root, log):
        self.roster=json.loads((root/'tests/roster.json').read_text())
        self.log=log;self.bad_hashes=set()
        with tarfile.open(root/'tests/upstream.tar.gz') as a:
            for m in a:
                if m.isfile() and m.size>=512 and ('/tests/' in m.name or '/solution/' in m.name):
                    self.bad_hashes.add(hashlib.sha256(a.extractfile(m).read()).digest())

    def normalize(self,url):
        for _ in range(4):
            decoded=urllib.parse.unquote(url)
            if decoded==url:break
            url=decoded
        u=urllib.parse.urlsplit(url)
        if u.scheme!='https' or u.username or u.password or u.port not in (None,443) or not u.hostname:
            raise ValueError('Research accepts credential-free HTTPS URLs on port 443 only.')
        host=u.hostname.encode('idna').decode().lower().rstrip('.')
        path=urllib.parse.urljoin('/',u.path).lower()
        if '\\' in path or '\x00' in url or any(ord(c)<32 for c in url):raise ValueError('Invalid normalized URL.')
        text=(host+path+'?'+u.query).lower()
        if host.endswith('datacurve.ai') or 'deep-swe' in text or 'deepswe' in text or any(x in text for x in self.roster['all']):
            raise ValueError('Benchmark repository, raw/API/archive, or known-copy route is prohibited.')
        addresses=sorted({row[4][0] for row in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)})
        if not addresses or any(not ipaddress.ip_address(x).is_global for x in addresses):
            raise ValueError('Private, reserved and local research destinations are prohibited.')
        return host,urllib.parse.urlunsplit(('','',u.path or '/',u.query,'')),addresses[0]

    def inspect(self,data,depth=0):
        if hashlib.sha256(data).digest() in self.bad_hashes:raise ValueError('Known benchmark answer material was rejected.')
        lower=data.lower()
        if b'datacurve-ai/deep-swe' in lower or any(x.encode() in lower for x in self.roster['all']):
            raise ValueError('Known benchmark content was rejected.')
        if depth>=2:return
        members=[]
        try:
            if zipfile.is_zipfile(io.BytesIO(data)):
                with zipfile.ZipFile(io.BytesIO(data)) as a:
                    if sum(x.file_size for x in a.infolist())>32*1024**2:raise ValueError('Research archive expands beyond 32 MiB.')
                    members=[a.read(x) for x in a.infolist() if not x.is_dir()]
            else:
                with tarfile.open(fileobj=io.BytesIO(data)) as a:
                    files=[x for x in a if x.isfile()]
                    if sum(x.size for x in files)>32*1024**2:raise ValueError('Research archive expands beyond 32 MiB.')
                    members=[a.extractfile(x).read() for x in files]
        except (tarfile.ReadError,zipfile.BadZipFile):pass
        for data in members:self.inspect(data,depth+1)

    def fetch(self,url):
        first=url;visited=[];status='rejected';size=0;digest=None
        try:
            for _ in range(6):
                host,path,address=self.normalize(url);visited.append(url)
                # Pin the checked address for this request, while retaining TLS
                # hostname verification. Every redirect repeats all checks.
                class Pinned(http.client.HTTPSConnection):
                    def connect(self):
                        raw=socket.create_connection((address,443),timeout=30)
                        self.sock=self._context.wrap_socket(raw,server_hostname=host)
                c=Pinned(host,timeout=30)
                try:
                    c.request('GET',path,headers={'User-Agent':'DeepSWE-research-broker/1','Accept-Encoding':'identity'})
                    response=c.getresponse()
                    if response.status in (301,302,303,307,308):
                        url=urllib.parse.urljoin(url,response.getheader('location',''));continue
                    if response.status!=200:raise RuntimeError(f'Research server returned HTTP {response.status}.')
                    if response.getheader('content-encoding','identity')!='identity':raise ValueError('Unexpected encoded research response.')
                    data=response.read(16*1024**2+1)
                    if len(data)>16*1024**2:raise ValueError('Research response exceeds 16 MiB.')
                    self.inspect(data);size=len(data);digest=hashlib.sha256(data).hexdigest();status='accepted'
                    return {'url':url,'sha256':digest,'content_type':response.getheader('content-type'), 'data':base64.b64encode(data).decode()}
                finally:c.close()
            raise ValueError('Too many research redirects.')
        finally:self.log({'kind':'research','requested_url':first,'redirects':visited,'status':status,'bytes':size,'sha256':digest})


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--bind',required=True);ap.add_argument('--port',type=int,default=8765)
    ap.add_argument('--state',type=Path,required=True);ap.add_argument('--images',type=Path,required=True);a=ap.parse_args()
    os.umask(0o077);a.state.mkdir(parents=True,exist_ok=False)
    token=secrets.token_urlsafe(32);(a.state/'token').write_text(token)
    lock=threading.Lock();root=Path(__file__).resolve().parents[1]
    def log(row):
        with lock:
            with (a.state/'provenance.jsonl').open('a') as f:f.write(json.dumps({'time':time.time(),**row})+'\n')
    research=Research(root,log);proxy=ProviderProxy(record=lambda row:log({'kind':'inference',**row}))
    images=json.loads(a.images.read_text());dev={k:v for k,v in images['images'].items() if k in research.roster['development']}
    slots=threading.BoundedSemaphore(32)
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def log_message(self,*args):pass
        def do_CONNECT(self):self.send_error(405)
        def do_GET(self):self.handle_request()
        def do_POST(self):self.handle_request()
        def do_DELETE(self):self.handle_request()
        def handle_request(self):
            auth=self.headers.get('Authorization','').removeprefix('Bearer ') or self.headers.get('x-api-key','')
            if not secrets.compare_digest(auth,token):self.send_error(401);return
            if not slots.acquire(False):self.send_error(429);return
            started=False;cancel=threading.Event()
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<=length<=16*1024**2 or self.headers.get('Transfer-Encoding'):raise ValueError('Bounded Content-Length required.')
                self.connection.settimeout(60);body=self.rfile.read(length)
                if len(body)!=length:raise ValueError('Truncated request.')
                if self.path in ('/research/fetch','/research/search','/research/development-images'):
                    if self.path.endswith('development-images'):result=dev
                    else:
                        req=json.loads(body)
                        url=req['url'] if self.path.endswith('fetch') else 'https://www.google.com/search?'+urllib.parse.urlencode({'q':req['query']})
                        result=research.fetch(url)
                    raw=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();started=True;self.wfile.write(raw)
                else:
                    def headers(status, values):
                        nonlocal started
                        self.send_response(status)
                        for k,v in values.items():self.send_header(k,v)
                        self.send_header('Transfer-Encoding','chunked');self.end_headers();started=True
                    def chunk(data):
                        self.wfile.write(f'{len(data):x}\r\n'.encode()+data+b'\r\n');self.wfile.flush()
                    proxy.request(self.command,self.path,body,{k.lower():v for k,v in self.headers.items()},headers,chunk,cancel,time.monotonic()+10800)
                    self.wfile.write(b'0\r\n\r\n');self.wfile.flush()
            except Exception as exc:
                cancel.set();log({'kind':'broker_error','class':type(exc).__name__,'message':str(exc)})
                if not started:self.send_error(400,str(exc))
                self.close_connection=True
            finally:slots.release()
    server=http.server.ThreadingHTTPServer((a.bind,a.port),Handler)
    print('Broker ready; run credential is stored in the private state/token file.',flush=True)
    try:server.serve_forever()
    finally:server.server_close()


if __name__=='__main__':main()
