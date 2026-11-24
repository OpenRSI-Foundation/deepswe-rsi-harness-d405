#!/opt/pier/.venv/bin/python -I
"""Pinned Pier installed-agent behavior, with offline setup and scoped RPC."""
import asyncio
import base64
import json
import os
import socket
import struct
import sys
from pathlib import Path
from types import SimpleNamespace
from pier.agents.installed.codex import Codex
from pier.agents.installed.claude_code import ClaudeCode
from pier.models.agent.context import AgentContext


class RemoteEnvironment:
    default_user = None
    def __init__(self):
        self.sock = socket.socket(fileno=int(os.environ['DEEPSWE_RPC_FD']))

    def call(self, operation, **arguments):
        raw = json.dumps(dict(operation=operation, **arguments)).encode()
        self.sock.sendall(struct.pack('!I', len(raw)) + raw)
        def exact(n):
            b = bytearray()
            while len(b) < n:
                part = self.sock.recv(n - len(b))
                if not part: raise RuntimeError('Episode RPC closed.')
                b.extend(part)
            return b
        n = struct.unpack('!I', exact(4))[0]
        if n > 24 * 1024**2: raise RuntimeError('Oversized RPC response.')
        result = json.loads(exact(n))
        if 'error' in result: raise RuntimeError(result['error'])
        return result['result']

    def agent_process_env(self, env):
        return env

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        result = await asyncio.to_thread(self.call, 'exec', command=command, cwd=cwd or '/app', env=env or {}, timeout_sec=timeout_sec)
        if result['return_code']:
            raise RuntimeError(f"Reference command failed ({result['return_code']}): {result['stderr']}")
        return SimpleNamespace(**result)

    async def upload_file(self, source_path, target_path):
        await asyncio.to_thread(self.call, 'write', path=target_path, data=base64.b64encode(Path(source_path).read_bytes()).decode())


async def main():
    task = json.loads(Path(os.environ['DEEPSWE_TASK_JSON']).read_text())
    remote = RemoteEnvironment()
    selected = sys.argv[1]
    # Payload transfer and relay startup are broker-owned, outside Pier's setup.
    remote.call('provision_reference')
    logs = Path(os.environ['TMPDIR']) / 'pier'; logs.mkdir()
    if selected == 'codex':
        agent = Codex(logs_dir=logs, model_name='gpt-5.6-sol', version='0.172.0', reasoning_effort='max',
                      config_toml=('web_search = "disabled"\nmodel_provider = "episode_relay"\n'
                                   '[model_providers.episode_relay]\nname = "OpenAI episode relay"\n'
                                   'base_url = "http://127.0.0.1:18765/v1"\nwire_api = "responses"\n'
                                   'requires_openai_auth = true\nsupports_websockets = false\n'),
                      extra_env={'OPENAI_API_KEY': 'episode-relay', 'OPENAI_BASE_URL': 'http://127.0.0.1:18765/v1'})
    elif selected == 'claude':
        agent = ClaudeCode(logs_dir=logs, model_name='claude-opus-5', version='2.1.331', reasoning_effort='high',
                           disallowed_tools='EnterPlanMode,WebSearch,WebFetch',
                           extra_env={'ANTHROPIC_API_KEY': 'episode-relay', 'ANTHROPIC_BASE_URL': 'http://127.0.0.1:18765'})
    else:
        raise ValueError('Unknown reference selector.')
    await agent.run(task['instruction'], remote, AgentContext())
    remote.call('done')


if __name__ == '__main__':
    asyncio.run(main())
