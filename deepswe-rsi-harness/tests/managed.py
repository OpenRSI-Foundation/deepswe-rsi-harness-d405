"""Pier's environment contract over the injected v2 local sandbox client."""
import asyncio
import base64
import io
import json
import os
import shlex
import sys
import tarfile
import threading
import time
from pathlib import Path, PurePosixPath

sys.path.insert(0, os.environ['RSI_SANDBOX_PYTHONPATH'])
from rsi_sandbox_client import SandboxClient
from pier.environments.base import BaseEnvironment, ExecResult
from pier.environments.capabilities import EnvironmentCapabilities

PULL_SLOTS = asyncio.Semaphore(4)


class PierManagedEnvironment(BaseEnvironment):
    @staticmethod
    def type():
        return 'rsi-pier-managed'

    @property
    def capabilities(self):
        return EnvironmentCapabilities(disable_internet=True)

    def _validate_definition(self):
        if not self.task_env_config.docker_image or '@sha256:' not in self.task_env_config.docker_image:
            raise ValueError('A prepared immutable image digest is required.')

    def __init__(self, *args, **kwargs):
        self.client = SandboxClient()
        self.handle = None
        self.image = None
        self.deadline = time.monotonic() + 14400
        super().__init__(*args, **kwargs)

    async def start(self, force_build=False):
        if force_build:
            raise ValueError('Child builds are not authorized.')
        async with PULL_SLOTS:
            job = await asyncio.to_thread(self.client.image_pull, self.task_env_config.docker_image)
            view = await asyncio.to_thread(self.client.follow_job, job)
        if view['state'] != 'succeeded':
            raise RuntimeError(f"image_pull failed: {view.get('error')}")
        self.image = view['result']['image']['handle']
        spec = dict(version=1, network='none', lifetime_sec=14400.0, disk_mb=20480,
                    services={'main': dict(image=self.image, entrypoint=['/bin/bash', '-c'],
                    command=['while true; do sleep 3600; done'], working_dir='/app',
                    cpus=2.0, memory_mb=8192, shm_mb=1024, network='none')})
        created = await asyncio.to_thread(self.client.env_create, spec)
        self.handle = created['env_id']
        await asyncio.to_thread(self.client.env_start, self.handle, 300)
        status = await asyncio.to_thread(self.client.wait_env, self.handle, 300)
        if status['state'] != 'ready':
            raise RuntimeError('Managed environment did not become running.')

    async def stop(self, delete=True):
        if self.handle is not None:
            await asyncio.to_thread(self.client.env_destroy, self.handle)
            self.handle = None
        if self.image is not None:
            await asyncio.to_thread(self.client.image_release, self.image)
            self.image = None

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None, output=None):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Episode deadline expired.')
        timeout = min(float(timeout_sec or remaining), remaining)
        merged = dict(self._persistent_env); merged.update(env or {})
        eid = await asyncio.to_thread(self.client.exec_start, self.handle, 'main',
                   ['/bin/bash', '-o', 'pipefail', '-c', command], cwd=cwd or '/app',
                   env=merged, user=None if user is None else str(user), timeout_sec=timeout)
        chunks = {'stdout': bytearray(), 'stderr': bytearray()}
        output_lock = threading.Lock()
        accepting_output = True
        def collect(stream, data):
            with output_lock:
                if not accepting_output: return
                # Publish the available prefix before reporting a bound violation.
                available = 16 * 1024**2 - len(chunks[stream])
                kept = data[:available]
                chunks[stream].extend(kept)
                if output is not None and kept:
                    output({'trace':'command_output', 'exec_id':eid, 'stream':stream,
                            'text':kept.decode(errors='replace')})
                if len(data) > available:
                    raise RuntimeError('Task command output exceeds the 16 MiB per-stream bound.')
        final = {}; error = None; cleanup_error = None
        # Shield the follower so cancellation can kill the command and drain
        # already available output before teardown, rather than abandon a thread.
        follower = asyncio.create_task(asyncio.to_thread(self.client.follow_exec, eid, collect))
        follower.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
        try:
            final = await asyncio.shield(follower)
            if final.get('truncated') or final.get('oom_kills') or final.get('state') != 'exited':
                raise RuntimeError('Managed exec did not complete: ' + json.dumps({k:final.get(k) for k in ('state','truncated','oom_kills','exit_code')}))
            rc = final.get('exit_code')
            if type(rc) is not int:
                raise RuntimeError('Managed exec returned no integer exit status.')
            return ExecResult(stdout=chunks['stdout'].decode(errors='replace'),
                              stderr=chunks['stderr'].decode(errors='replace'), return_code=rc)
        except BaseException as exc:
            error = f'{type(exc).__name__}: {exc}'
            try:
                await asyncio.to_thread(self.client.exec_kill, eid)
            except Exception as cleanup:
                cleanup_error = f'{type(cleanup).__name__}: {cleanup}'
            if not follower.done():
                try:
                    final = await asyncio.wait_for(asyncio.shield(follower), 30)
                except BaseException as drain:
                    cleanup_error = (cleanup_error or '') + f' Output drain: {type(drain).__name__}: {drain}'
            raise
        finally:
            with output_lock:
                accepting_output = False
                if output is not None:
                    output({'trace':'command_end', 'exec_id':eid,
                            'state':final.get('state'), 'return_code':final.get('exit_code'),
                            'truncated':final.get('truncated'), 'oom_kills':final.get('oom_kills'),
                            'error':error, 'cleanup_error':cleanup_error,
                            'stdout_bytes':len(chunks['stdout']), 'stderr_bytes':len(chunks['stderr'])})

    async def put_bytes(self, path, data, mode=0o644):
        target = PurePosixPath(path)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w') as out:
            info = tarfile.TarInfo(target.name); info.size = len(data); info.mode = mode
            out.addfile(info, io.BytesIO(data))
        buf.seek(0)
        stage = await asyncio.to_thread(self.client.upload_stage, buf)
        await asyncio.to_thread(self.client.copy_in, self.handle, 'main', str(target.parent), stage['stage_id'])

    async def upload_file(self, source_path, target_path):
        p = Path(source_path)
        await self.put_bytes(target_path, p.read_bytes(), p.stat().st_mode & 0o777)

    async def put_atomic(self,path,data):
        temporary=path+'.transfer'
        await self.put_bytes(temporary,data)
        result=await self.exec('mv -- '+shlex.quote(temporary)+' '+shlex.quote(path),timeout_sec=30)
        if result.return_code:raise RuntimeError('Atomic child relay transfer failed.')

    async def upload_dir(self, source_dir, target_dir):
        # Transfers may contain payload symlinks, but never host paths.
        source = Path(source_dir)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w') as out:
            for p in sorted(source.rglob('*')):
                if p.is_symlink() and not p.resolve().is_relative_to(source.resolve()):
                    raise ValueError(f'Escaping upload link: {p}')
                out.add(p, arcname=str(p.relative_to(source)), recursive=False)
        buf.seek(0)
        stage = await asyncio.to_thread(self.client.upload_stage, buf)
        await asyncio.to_thread(self.client.copy_in, self.handle, 'main', target_dir, stage['stage_id'])

    async def get_bytes(self, path, limit=16 * 1024**2):
        stage = await asyncio.to_thread(self.client.copy_out, self.handle, 'main', path, limit)
        buf = io.BytesIO()
        await asyncio.to_thread(self.client.download_stage, stage['stage_id'], buf)
        buf.seek(0)
        with tarfile.open(fileobj=buf) as archive:
            members = [m for m in archive if m.isfile()]
            if len(members) != 1 or members[0].size > limit:
                raise ValueError('Expected exactly one bounded regular file.')
            return archive.extractfile(members[0]).read()

    async def download_file(self, source_path, target_path):
        Path(target_path).write_bytes(await self.get_bytes(source_path))

    async def download_dir(self, source_dir, target_dir):
        stage = await asyncio.to_thread(self.client.copy_out, self.handle, 'main', source_dir, 64 * 1024**2)
        buf = io.BytesIO()
        await asyncio.to_thread(self.client.download_stage, stage['stage_id'], buf)
        buf.seek(0); target = Path(target_dir); target.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=buf) as archive:
            for m in archive:
                p = PurePosixPath(m.name)
                if p.is_absolute() or '..' in p.parts or not (m.isfile() or m.isdir()):
                    raise ValueError('Unsafe download archive member.')
            archive.extractall(target, filter='data')
