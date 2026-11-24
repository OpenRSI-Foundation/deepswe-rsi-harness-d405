#!/usr/bin/env python3
"""Execution-stage preparation only: freeze real image identities and inspect bases."""
import argparse
import json
import subprocess
import tarfile
import tomllib
from pathlib import Path

PROTOCOL = 'deep-swe-0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea-pier-b26211ed2bbee6d145f6b8c5b80e39f18b296f08-v1'


def run(*args):
    return subprocess.check_output(args,text=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    if a.output.exists(): raise SystemExit('Refusing to replace a frozen image manifest.')
    root=Path(__file__).resolve().parents[1]
    configs={}
    with tarfile.open(root/'tests/upstream.tar.gz') as archive:
        for m in archive:
            if m.isfile() and m.name.endswith('/task.toml'):
                configs[m.name.split('/')[-2]]=tomllib.loads(archive.extractfile(m).read().decode())
    if len(configs)!=113: raise RuntimeError('Expected all 113 task definitions.')
    result={'protocol':PROTOCOL,'images':{}}
    for name,task in sorted(configs.items()):
        tag=task['environment']['docker_image']
        subprocess.run(['docker','pull','--platform','linux/amd64',tag],check=True)
        meta=json.loads(run('docker','image','inspect',tag))[0]
        if meta['Architecture']!='amd64' or meta['Os']!='linux' or meta['Config'].get('Volumes'):
            raise RuntimeError(f'{name}: incompatible image metadata or anonymous volumes.')
        repository=tag.rsplit(':',1)[0]
        digests=[x for x in meta['RepoDigests'] if x.startswith(repository+'@sha256:')]
        if len(digests)!=1: raise RuntimeError(f'{name}: digest is ambiguous.')
        digest=digests[0];base=task['metadata']['base_commit_hash']
        # Read-only probe in an offline ephemeral container. No task verifier,
        # solution, CLI agent, or benchmark evaluation runs during preparation.
        command=' && '.join(['test -d /app','command -v bash','command -v git',
            f'test "$(git -C /app rev-parse HEAD)" = {base}',
            'test -z "$(git -C /app status --porcelain --untracked-files=all)"',
            f'test "$(git -C /app rev-list --all | sort -u)" = "$(git -C /app rev-list {base} | sort -u)"',
            'unreachable=$(git -C /app fsck --no-reflogs --unreachable)','test -z "$unreachable"',
            'test ! -e /tests/test.sh','test ! -e /solution/solve.sh'])
        subprocess.run(['docker','run','--rm','--network','none','--read-only','--cpus','2','--memory','8g',
            '-e','GIT_CONFIG_COUNT=1','-e','GIT_CONFIG_KEY_0=safe.directory','-e','GIT_CONFIG_VALUE_0=/app',
            '--entrypoint','/bin/bash',digest,'-o','pipefail','-c',command],check=True)
        result['images'][name]={'tag':tag,'digest':digest,'image_id':meta['Id'],'base_commit':base}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print('Prepared and pre-pulled 113 immutable images; no benchmark score was measured.')


if __name__=='__main__':main()
