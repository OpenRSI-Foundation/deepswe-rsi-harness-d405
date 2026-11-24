"""One scoped candidate worker, one solving environment, then pristine grading."""
import asyncio
import base64
import contextlib
import json
import os
import re
import shutil
import signal
import socket
import struct
import subprocess
import threading
import time
from pathlib import Path, PurePosixPath
from pier.models.task.config import EnvironmentConfig
from pier.models.trial.paths import TrialPaths
from managed import PierManagedEnvironment
from provider import ProviderProxy, ProviderFailure, PROVIDER_THREADS


class EpisodeFailure(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message); self.code = code


def make_env(task, image, scratch):
    return PierManagedEnvironment(environment_dir=scratch, environment_name=task['metadata']['task_id'],
        session_id=scratch.name, trial_paths=TrialPaths(trial_dir=scratch),
        task_env_config=EnvironmentConfig(docker_image=image, cpus=2, memory_mb=8192, storage_mb=20480, gpus=0, network_mode='no-network'))


class WorkerBroker:
    def __init__(self, environment, candidate, manifest, deadline, scratch, emit):
        self.environment = environment; self.candidate = candidate; self.manifest = manifest
        self.deadline = deadline; self.scratch = scratch; self.emit = emit
        self.proxy = ProviderProxy(manifest['providers'])
        self.cancel = threading.Event(); self.relay = None; self.relay_exec = None
        self.requests = {}; self.done = False; self.failure = None
        self.inference_slots = asyncio.Semaphore(4)

    async def provision(self):
        if self.relay is not None: raise ValueError('Reference payload was already provisioned.')
        p = self.candidate / 'payload'
        if not p.is_dir(): raise ValueError('Missing candidate/payload reference dependencies.')
        await self.environment.exec('mkdir -p /opt/deepswe-cli /tmp/deepswe-relay /logs/agent')
        await self.environment.upload_dir(p, '/opt/deepswe-cli')
        await self.environment.upload_file(self.candidate / 'relay.js', '/tmp/deepswe-relay/relay.js')
        self.environment._persistent_env['PATH'] = '/opt/deepswe-cli/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
        self.relay_exec = await asyncio.to_thread(self.environment.client.exec_start,
            self.environment.handle, 'main', ['/opt/deepswe-cli/bin/node', '/tmp/deepswe-relay/relay.js'],
            timeout_sec=max(1, self.deadline-time.monotonic()))
        self.relay = asyncio.create_task(self.pump())

    async def transfer_request(self, identity):
        root = '/tmp/deepswe-relay/' + identity
        raw = await self.environment.get_bytes(root + '/request.json', 24 * 1024**2)
        req = json.loads(raw); seq = 0; loop = asyncio.get_running_loop(); sent_headers = False
        canceled = self.requests[identity]['cancel']
        def upload(path, data):
            future = asyncio.run_coroutine_threadsafe(self.environment.put_atomic(path, data), loop)
            future.result(timeout=max(1, min(300, self.deadline-time.monotonic())))
        def headers(status, values):
            nonlocal sent_headers
            upload(root + '/headers.json', json.dumps(dict(status=status, headers=values)).encode())
            sent_headers = True
        def chunk(data):
            nonlocal seq
            upload(root + f'/chunk-{seq}', data); seq += 1
        try:
            async with self.inference_slots:
                await loop.run_in_executor(PROVIDER_THREADS, self.proxy.request, req['method'], req['path'],
                    base64.b64decode(req['body'], validate=True), req.get('headers', {}), headers, chunk, canceled, self.deadline)
        except ProviderFailure as exc:
            # The proxy records this unresolved attempt. Keep the relay alive
            # so the CLI may retry; only trusted completion can recover it.
            self.emit({'trace':'inference_failure', 'diagnostic':str(exc)})
            if not sent_headers:
                await self.environment.put_atomic(root + '/headers.json',json.dumps({'status':502,'headers':{'content-type':'application/json'}}).encode())
                await self.environment.put_atomic(root + '/chunk-0',json.dumps({'error':str(exc)}).encode())
                seq = 1
        except Exception as exc:
            if not canceled.is_set(): self.failure = EpisodeFailure('inference_transport', f'{type(exc).__name__}: {exc}')
            if not sent_headers:
                await self.environment.put_atomic(root + '/headers.json',json.dumps({'status':502,'headers':{'content-type':'application/json'}}).encode())
        finally:
            await self.environment.put_atomic(root + '/done.json', json.dumps({'chunks':seq}).encode())

    async def scan_requests(self):
        result = await self.environment.exec("find /tmp/deepswe-relay -mindepth 2 -maxdepth 2 -type f -name request.json -o -name cancel -o -name ack", timeout_sec=30)
        if result.return_code: raise RuntimeError('Relay spool enumeration failed.')
        # Process request files before cancellation/ack files, independent of find order.
        paths = sorted((result.stdout or '').splitlines(), key=lambda p: not p.endswith('/request.json'))
        for name in paths:
            match = re.fullmatch(r'/tmp/deepswe-relay/([a-f0-9]{32})/(request.json|cancel|ack)', name)
            if not match: continue
            identity, kind = match.groups()
            if kind == 'request.json' and identity not in self.requests:
                if len(self.requests) >= 20000: raise ValueError('Episode relay exceeds 20000 requests.')
                if sum(not x['task'].done() for x in self.requests.values()) >= 64: raise ValueError('Too many pending relay requests.')
                self.requests[identity] = {'cancel':threading.Event()}
                self.requests[identity]['task'] = asyncio.create_task(self.transfer_request(identity))
            elif kind == 'cancel' and identity in self.requests:
                self.requests[identity]['cancel'].set()
            elif kind == 'ack' and identity in self.requests and self.requests[identity]['task'].done():
                await self.requests[identity]['task']
                await self.environment.exec('rm -rf /tmp/deepswe-relay/'+identity,timeout_sec=30)

    async def pump(self):
        try:
            while not self.cancel.is_set() and time.monotonic() < self.deadline:
                await self.scan_requests()
                for request in self.requests.values():
                    if request['task'].done():
                        error = request['task'].exception()
                        if error: raise error
                if self.failure: raise self.failure
                await asyncio.sleep(0.25)
        except Exception as exc:
            self.failure = EpisodeFailure('relay_transport', f'{type(exc).__name__}: {exc}')

    async def dispatch(self, req):
        if time.monotonic() >= self.deadline: raise TimeoutError('Shared solving deadline expired.')
        op = req.get('operation')
        if op == 'done': self.done = True; return {}
        if self.done: raise ValueError('Episode already completed.')
        if op == 'provision_reference': await self.provision(); return {}
        if op == 'exec':
            command = req.get('command'); env = req.get('env', {}); cwd = req.get('cwd', '/app')
            if not isinstance(command, str) or len(command) > 60000 or not isinstance(env, dict): raise ValueError('Invalid command or environment.')
            value = req.get('timeout_sec')
            if value is not None and (type(value) not in (int,float) or not 0 < value <= 10800): raise ValueError('Invalid command timeout.')
            loop = asyncio.get_running_loop()
            # follow_exec calls this from its sandbox thread. Serialize emission
            # on the episode loop; successful output is not emitted a second time.
            result = await self.environment.exec(command, cwd=cwd, env=env, timeout_sec=value,
                        output=lambda row:loop.call_soon_threadsafe(self.emit, row))
            return result.model_dump()
        if op in ('read','write'):
            path = req.get('path')
            if not isinstance(path,str) or not path.startswith('/') or '..' in PurePosixPath(path).parts or path.startswith(('/proc/','/sys/','/dev/')):
                raise ValueError('File operation requires a normal absolute child path.')
            if op == 'read': return {'data':base64.b64encode(await self.environment.get_bytes(path)).decode()}
            data = base64.b64decode(req['data'], validate=True)
            if len(data) > 16*1024**2: raise ValueError('Write exceeds 16 MiB.')
            await self.environment.put_bytes(path,data); return {}
        if op == 'inference':
            result = await asyncio.get_running_loop().run_in_executor(PROVIDER_THREADS,self.proxy.buffered, req.get('method','POST'), req['path'],
                     json.dumps(req['body']).encode(), req.get('headers',{}), self.cancel, self.deadline)
            result['body'] = base64.b64encode(result['body']).decode(); return result
        raise ValueError('Unknown episode RPC operation.')

    async def serve(self, sock):
        loop = asyncio.get_running_loop(); sock.setblocking(False)
        async def exact(n):
            result = bytearray()
            while len(result) < n:
                b = await loop.sock_recv(sock, n-len(result))
                if not b: raise EOFError()
                result.extend(b)
            return result
        try:
            for _ in range(200000):
                n = struct.unpack('!I', await exact(4))[0]
                if not 0 < n <= 24*1024**2: raise ValueError('RPC frame exceeds bound.')
                req = json.loads(await exact(n))
                if not isinstance(req,dict): raise ValueError('RPC request must be an object.')
                try: response = {'result':await self.dispatch(req)}
                except ProviderFailure as exc:
                    response = {'error':str(exc), 'inference_failure':True}
                except Exception as exc:
                    self.failure = EpisodeFailure('candidate_rpc', f'{type(exc).__name__}: {exc}')
                    response = {'error':str(self.failure)}
                data = json.dumps(response).encode()
                await loop.sock_sendall(sock, struct.pack('!I',len(data))+data)
                if self.failure: return
            raise ValueError('RPC operation bound exceeded.')
        except EOFError: return

    async def close(self):
        self.cancel.set()
        if self.relay:
            self.relay.cancel()
            with contextlib.suppress(asyncio.CancelledError): await self.relay
        if self.relay_exec:
            await asyncio.to_thread(self.environment.client.exec_kill,self.relay_exec)
            # exec_kill only sends a signal; wait for actual relay termination
            # before the last spool scan. Its bounded streams are candidate-owned.
            loop = asyncio.get_running_loop()
            def relay_output(stream, data):
                loop.call_soon_threadsafe(self.emit, {'trace':'relay_'+stream, 'text':data.decode(errors='replace')})
            final = await asyncio.wait_for(asyncio.to_thread(self.environment.client.follow_exec,
                                          self.relay_exec, relay_output), 30)
            self.emit({'trace':'relay_end', **{k:final.get(k) for k in ('state','exit_code','truncated','oom_kills')}})
            if final.get('truncated') or final.get('oom_kills') or final.get('state') not in ('exited','killed'):
                self.failure = EpisodeFailure('relay_transport','Relay did not stop cleanly before the final request scan.')
            # Include queued requests even when the worker exited between polls.
            await self.scan_requests()
        for request in self.requests.values():
            if request.get('cancel'): request['cancel'].set()
        jobs = [x['task'] for x in self.requests.values() if 'task' in x]
        if jobs:
            results = await asyncio.wait_for(asyncio.gather(*jobs, return_exceptions=True), 90)
            for result in results:
                if isinstance(result,BaseException):
                    self.failure = EpisodeFailure('relay_transport',f'{type(result).__name__}: {result}')


async def solve(task, image, manifest, workspace, scratch, emit):
    environment = make_env(task, image, scratch / 'solve')
    worker = None; broker = None; serving = None; a = b = None
    try:
        await environment.start()
        deadline = time.monotonic() + 10800
        environment.deadline = deadline
        if manifest['mode'] == 'custom':
            stage = scratch / 'public'; stage.mkdir(mode=0o755); stage.chmod(0o755)
            candidate = stage / 'candidate'
            shutil.copytree(workspace / 'candidate', candidate, symlinks=True)
            # The copy has been validated for escaping links before candidate launch.
            for p in [candidate, *candidate.rglob('*')]:
                if not p.is_symlink(): p.chmod((p.stat().st_mode & 0o777) | (0o555 if p.is_dir() else 0o444))
            tp = stage / 'task.json'
            tp.write_text(json.dumps({'id':task['metadata']['task_id'], 'instruction':task['_instruction'], 'deadline_sec':10800})); tp.chmod(0o444)
            write = scratch / 'worker'; write.mkdir(mode=0o777); write.chmod(0o777)
            a,b = socket.socketpair()
            broker = WorkerBroker(environment,candidate,manifest,deadline,scratch,emit)
            argv = [x.replace('/workspace/candidate/',str(candidate)+'/') for x in manifest['entrypoint']]
            command = ['rsi-isolate','run','--no-network','--read',str(stage),'--read','/opt/pier',
                       '--write',str(write),'--cwd',str(write),'--timeout','10800','--pass-fd',str(b.fileno()),
                       '--env',f'DEEPSWE_RPC_FD={b.fileno()}','--env',f'DEEPSWE_TASK_JSON={tp}',
                       '--env',f'CANDIDATE_ROOT={candidate}','--',*argv]
            worker = await asyncio.create_subprocess_exec(*command,pass_fds=(b.fileno(),),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            b.close(); serving = asyncio.create_task(broker.serve(a))
            async def drain(stream, name):
                while data := await stream.read(65536): emit({'trace':name,'text':data.decode(errors='replace')})
            async with asyncio.timeout(max(1,deadline-time.monotonic())+5):
                await asyncio.gather(drain(worker.stdout,'candidate_stdout'),drain(worker.stderr,'candidate_stderr'),worker.wait())
            # Stop all candidate descendants before collection, even after clean exit.
            if worker.returncode or not broker.done:
                raise EpisodeFailure('candidate_process',f'Worker exit={worker.returncode}; explicit done={broker.done}. No reward.')
            await asyncio.wait_for(serving, 30)
            if broker.failure: raise broker.failure
            await broker.close()
            if broker.failure: raise broker.failure
            try:
                broker.proxy.require_complete()
            except ProviderFailure as exc:
                raise EpisodeFailure('inference_incomplete',str(exc)) from exc
        environment.deadline = time.monotonic()+300
        for collect in task['verifier']['collect']:
            result = await environment.exec(collect['command'],timeout_sec=300)
            if result.return_code: raise EpisodeFailure('patch_collection',f'Collection exit={result.return_code}; {result.stderr}')
        return await environment.get_bytes('/logs/artifacts/model.patch', 64*1024**2)
    finally:
        try:
            if worker and worker.returncode is None:
                worker.send_signal(signal.SIGTERM)
                await asyncio.wait_for(worker.wait(),30)
        finally:
            try:
                if serving:
                    serving.cancel()
                    with contextlib.suppress(asyncio.CancelledError): await serving
            finally:
                if a: a.close()
                if b: b.close()
                try:
                    if broker and not broker.cancel.is_set(): await broker.close()
                finally:
                    try:
                        if broker: emit({'accounting':broker.proxy.records})
                    finally:
                        await environment.stop()


async def grade(task, image, task_dir, patch, scratch):
    environment = make_env(task,image,scratch / 'grade')
    try:
        await environment.start()
        await environment.exec('mkdir -p /tests /logs/artifacts /logs/verifier')
        await environment.upload_dir(task_dir / 'tests','/tests')
        await environment.put_bytes('/logs/artifacts/model.patch',patch)
        environment.deadline = time.monotonic()+1800
        # These streams contain hidden test names/answers. Never forward them.
        result = await environment.exec('/bin/bash /tests/test.sh',timeout_sec=1800)
        if result.return_code:
            raise EpisodeFailure('upstream_verifier_exit',f'Pristine verifier exited {result.return_code}; protected grading streams withheld.')
        value = json.loads(await environment.get_bytes('/logs/verifier/reward.json',1048576))
        reward = value.get('reward') if isinstance(value,dict) else None
        if type(reward) not in (int,float) or reward not in (0,1):
            raise EpisodeFailure('upstream_incomplete','Expected a completed binary upstream reward; crash sentinels are unscored.')
        return int(reward)
    finally:
        await environment.stop()
