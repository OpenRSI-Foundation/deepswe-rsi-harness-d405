"""Credential-owning, bounded Responses/Messages transport and accounting."""
import hashlib
import http.client
import json
import os
import re
import socket
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

# Provider streams may wait for sandbox copies. Never occupy the sandbox
# executor while waiting for a copy scheduled back onto that executor.
PROVIDER_THREADS = ThreadPoolExecutor(max_workers=32, thread_name_prefix='inference')


class ProviderFailure(RuntimeError):
    """A recorded, unscored inference failure; an identical request may retry."""


class Completion:
    """Observe provider completion, without changing bytes sent to the client."""
    def __init__(self, provider, method, path, observe_usage):
        self.provider = provider
        self.inference = (method == 'POST' and path in ('/v1/responses', '/v1/messages')) or (
            method == 'GET' and re.fullmatch(r'/v1/responses/resp_[A-Za-z0-9_-]+', path) is not None)
        self.observe_usage = observe_usage
        self.terminal = False
        self.error = None
        self.provider_code = None
        self.pending = b''
        self.data = []
        self.event = ''

    def item(self, value, event='', streaming=False):
        if not isinstance(value, dict):
            self.error = self.error or 'invalid_provider_object'
            return
        self.observe_usage(value)
        kind = value.get('type', event)
        response = value.get('response', value)
        if isinstance(response, dict):
            for details in (response.get('error'), response.get('incomplete_details')):
                if isinstance(details, dict):
                    code = details.get('code') or details.get('type') or details.get('reason')
                    if isinstance(code, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', code):
                        self.provider_code = code
        if event == 'error' or kind in ('error', 'response.failed', 'response.incomplete') or value.get('error'):
            self.error = self.error or (kind if kind in ('error', 'response.failed', 'response.incomplete') else 'provider_error')
        if not self.inference:
            return
        if self.provider == 'openai':
            response = value.get('response', {}) if streaming else value
            status = response.get('status') if isinstance(response, dict) else None
            if status in ('failed', 'incomplete', 'cancelled'):
                self.error = self.error or 'response_' + status
            if isinstance(response, dict) and response.get('error'):
                self.error = self.error or 'response_error'
            if (not streaming or kind == 'response.completed') and status == 'completed':
                self.terminal = True
        elif streaming:
            if kind == 'message_stop': self.terminal = True
        elif kind == 'message' and value.get('stop_reason') is not None:
            self.terminal = True

    def json(self, data, event='', streaming=False):
        try:
            value = json.loads(data)
        except (ValueError, UnicodeError):
            self.error = self.error or 'invalid_provider_json'
            return
        self.item(value, event, streaming)

    def feed(self, chunk):
        self.pending += chunk
        while b'\n' in self.pending:
            line, self.pending = self.pending.split(b'\n', 1)
            line = line.rstrip(b'\r')
            if not line:
                if self.data:
                    data = b'\n'.join(self.data)
                    if data.strip() != b'[DONE]': self.json(data, self.event, True)
                elif self.event == 'error':
                    self.error = self.error or 'provider_error'
                self.data = []; self.event = ''
            elif line.startswith(b'data:'):
                self.data.append(line[5:].lstrip(b' '))
            elif line.startswith(b'event:'):
                self.event = line[6:].strip().decode(errors='replace')

    def finish(self, streaming):
        if streaming and (self.pending.strip() or self.data or self.event):
            self.error = self.error or 'truncated_stream_event'
        if self.inference and not self.terminal:
            self.error = self.error or 'missing_inference_completion'
        return self.error


class ProviderProxy:
    def __init__(self, declarations=None, record=None):
        self.declarations = declarations
        self.records = []
        self.record = record
        self.lock = threading.Lock()
        self.ids = set()
        self.item_ids = set()

    def require_complete(self):
        with self.lock:
            unresolved = [dict(attempt_id=r['attempt_id'], provider=r['provider'], path=r['path'],
                               status=r['status'], error=r['error'], diagnostic=r['diagnostic'])
                          for r in self.records if not r['finished'] or
                          (not r['completed'] and r['recovered_by'] is None)]
        if unresolved:
            raise ProviderFailure('Unresolved inference attempts: ' + json.dumps(unresolved) +
                                  '. A completed retry of the same request is required before done; no reward.')

    def request(self, method, path, body, headers, on_headers, on_chunk, cancel, deadline):
        url = urllib.parse.urlsplit(path)
        if url.scheme or url.netloc or url.fragment or not url.path.startswith('/'):
            raise ValueError('Inference paths must be relative to the approved provider service.')
        path = url.path
        if path.startswith('/responses') or path.startswith('/messages') or path == '/models':
            path = '/v1' + path
        provider = 'anthropic' if path.startswith('/v1/messages') else 'openai'
        allowed = {'openai': {'/v1/responses', '/v1/responses/compact', '/v1/responses/input_tokens', '/v1/models'},
                   'anthropic': {'/v1/messages', '/v1/messages/count_tokens'}}[provider]
        dynamic = re.fullmatch(r'/v1/responses/(resp_[A-Za-z0-9_-]+)(/cancel|/input_items)?', path)
        if path not in allowed and not (dynamic and dynamic[1] in self.ids):
            raise ValueError('Only approved same-service Responses/Messages operations are allowed.')
        if method not in ('POST', 'GET', 'DELETE') or len(body) > 16 * 1024**2:
            raise ValueError('Unsupported method or oversized request.')
        obj = json.loads(body) if body else {}
        if not isinstance(obj, dict):
            raise ValueError('API request body must be an object.')
        def inspect(value):
            if isinstance(value, dict):
                kind = value.get('type', '')
                if isinstance(kind, str) and (kind.startswith(('web_search', 'web_fetch', 'file_search', 'code_interpreter', 'code_execution')) or kind in ('mcp', 'remote_mcp')):
                    raise ValueError('Provider-hosted retrieval and external media are disabled; use logged research fetch in Work.')
                if kind in ('input_image','image_url'):
                    image = value.get('image_url','')
                    if isinstance(image,dict): image = image.get('url','')
                    if not isinstance(image,str) or not image.startswith('data:image/'):
                        raise ValueError('Image inputs must be inline data, not remote retrieval.')
                if kind == 'input_file' and (not value.get('file_data') or value.get('file_id') or value.get('file_url')):
                    raise ValueError('File inputs must be inline data, not remote retrieval.')
                if kind == 'item_reference' and value.get('id') not in self.item_ids:
                    raise ValueError('Referenced response items must belong to this episode.')
                if value.get('type') == 'url' and 'url' in value:
                    raise ValueError('Remote media retrieval is disabled.')
                for v in value.values(): inspect(v)
            elif isinstance(value, list):
                for v in value: inspect(v)
        inspect(obj)
        for tool in obj.get('tools', []):
            kind = tool.get('type','custom') if isinstance(tool,dict) else ''
            client_kind = isinstance(kind,str) and (kind in ('function','custom','namespace','local_shell','shell','apply_patch') or kind.startswith(('bash_','text_editor_','computer_')))
            if not isinstance(tool,dict) or not (client_kind or (kind=='tool_search' and tool.get('execution')=='client')):
                raise ValueError('Only client-executed tools are permitted.')
        if obj.get('previous_response_id') and obj['previous_response_id'] not in self.ids:
            raise ValueError('Response history must belong to this episode.')
        if obj.get('conversation') or obj.get('background'):
            raise ValueError('Shared conversations and detached background inference violate episode isolation/deadlines.')
        model = obj.get('model')
        if model and self.declarations is not None:
            choices = [d for d in self.declarations if d['provider'] == provider and d['model'] == model]
            if not choices:
                raise ValueError('Requested provider/model was not declared in candidate.json.')
        keyname = 'OPENAI_API_KEY' if provider == 'openai' else 'ANTHROPIC_API_KEY'
        host = 'api.openai.com' if provider == 'openai' else 'api.anthropic.com'
        outgoing = {'Content-Type': 'application/json', 'Accept-Encoding': 'identity'}
        if provider == 'anthropic':
            outgoing['anthropic-version'] = headers.get('anthropic-version', '2023-06-01')
            if headers.get('anthropic-beta'): outgoing['anthropic-beta'] = headers['anthropic-beta']
        if headers.get('openai-beta'): outgoing['OpenAI-Beta'] = headers['openai-beta']
        target = path + ('?' + url.query if url.query else '')
        # JSON whitespace/key order and relay-generated IDs are not request identity.
        # Model, inputs, settings, service path/query and forwarded protocol headers are.
        operation = hashlib.sha256(json.dumps([provider, method, target, obj, outgoing],
                                   sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        with self.lock:
            record = dict(attempt_id=len(self.records)+1, provider=provider, model=model, method=method, path=path,
                          settings={k:obj[k] for k in ('reasoning','thinking','temperature','max_tokens','max_output_tokens','output_config') if k in obj},
                          request_sha256=hashlib.sha256(body).hexdigest(), operation_sha256=operation,
                          status=None, duration_sec=None, response_bytes=0, response_sha256=None,
                          usage=None, cost_usd=None, error=None, diagnostic='Request still running.',
                          finished=False, completed=False, recovered_by=None,
                          retry_of=[r['attempt_id'] for r in self.records if r['operation_sha256']==operation
                                    and r['finished'] and not r['completed'] and r['recovered_by'] is None],
                          recovered_attempts=[])
            self.records.append(record)
        start = time.monotonic(); status = None; count = 0; usage = None; failure = None; diagnostic = None
        digest = hashlib.sha256(); plain = bytearray()
        connection = http.client.HTTPSConnection(host, timeout=max(1, min(300, deadline - start)))
        finished = threading.Event()
        def watch():
            while not finished.wait(0.2):
                if cancel.is_set() or time.monotonic() >= deadline:
                    if connection.sock is not None:
                        try: connection.sock.shutdown(socket.SHUT_RDWR)
                        except OSError: pass
                    return
        watcher = threading.Thread(target=watch,daemon=True); watcher.start()
        forward = bytearray(); last_forward = start
        def usage_from(item):
            nonlocal usage
            if not isinstance(item, dict): return
            candidate = item.get('usage')
            if isinstance(candidate, dict):
                usage = {**(usage or {}), **candidate}
            identity = item.get('id')
            if isinstance(identity, str):
                if identity.startswith('resp_'): self.ids.add(identity)
                else: self.item_ids.add(identity)
            for key in ('response', 'message','item'): usage_from(item.get(key))
            for child in item.get('output',[]): usage_from(child)
        completion = Completion(provider, method, path, usage_from)
        try:
            secret = os.environ.get(keyname)
            if not secret: raise RuntimeError(f'Missing runtime credential {keyname}.')
            if provider == 'openai': outgoing['Authorization'] = 'Bearer ' + secret
            else: outgoing['x-api-key'] = secret
            if cancel.is_set() or time.monotonic() >= deadline: raise TimeoutError('Inference deadline expired.')
            connection.request(method, target, body=body or None, headers=outgoing)
            response = connection.getresponse(); status = response.status
            streaming = 'text/event-stream' in response.getheader('content-type', '').lower()
            if not 200 <= status < 300:
                failure = 'provider_http_error'; diagnostic = f'{provider} returned HTTP {status} for {method} {path}.'
            safe_headers = {k: v for k, v in response.getheaders() if k.lower() in {'content-type', 'retry-after', 'x-request-id', 'request-id'} or k.lower().startswith('x-ratelimit-')}
            on_headers(status, safe_headers)
            while True:
                if cancel.is_set() or time.monotonic() >= deadline: raise TimeoutError('Inference canceled or deadline expired.')
                chunk = response.read1(65536)
                if not chunk: break
                count += len(chunk)
                if count > 64 * 1024**2: raise RuntimeError('Provider response exceeded 64 MiB.')
                digest.update(chunk)
                if streaming:
                    completion.feed(chunk)
                else:
                    plain.extend(chunk)
                forward.extend(chunk)
                if len(forward)>=65536 or time.monotonic()-last_forward>=0.25:
                    on_chunk(bytes(forward));forward.clear();last_forward=time.monotonic()
            if forward:on_chunk(bytes(forward))
            if response.length not in (None, 0):
                raise RuntimeError('Provider response ended before its declared Content-Length.')
            if not streaming: completion.json(plain)
            observed_error = completion.finish(streaming)
            if observed_error and not failure:
                failure = observed_error; diagnostic = f'{provider} {method} {path}: {observed_error}.'
            if failure and completion.provider_code:
                diagnostic += ' Provider error code: ' + completion.provider_code + '.'
            if cancel.is_set() or time.monotonic() >= deadline:
                raise TimeoutError('Inference canceled or deadline expired before delivery completed.')
        except Exception as exc:
            failure = failure or type(exc).__name__
            diagnostic = f'{provider} {method} {path}: {type(exc).__name__}: {exc}'
            raise ProviderFailure(diagnostic) from exc
        finally:
            finished.set();watcher.join(timeout=1)
            connection.close()
            with self.lock:
                record.update(status=status, duration_sec=time.monotonic()-start, response_bytes=count,
                              response_sha256=digest.hexdigest(), usage=usage, error=failure,
                              diagnostic=diagnostic, finished=True, completed=failure is None)
                if record['completed']:
                    for earlier in self.records:
                        if earlier['attempt_id'] in record['retry_of'] and earlier['recovered_by'] is None:
                            earlier['recovered_by'] = record['attempt_id']
                            record['recovered_attempts'].append(earlier['attempt_id'])
                if self.record: self.record(record)
        return record

    def buffered(self, method, path, body, headers, cancel, deadline):
        result = {}; chunks = []
        record = self.request(method, path, body, headers,
                              lambda status, h: result.update(status=status, headers=h), chunks.append, cancel, deadline)
        result['body'] = b''.join(chunks)
        result['inference'] = {k:record[k] for k in ('attempt_id','completed','error','diagnostic','retry_of','recovered_attempts')}
        return result
