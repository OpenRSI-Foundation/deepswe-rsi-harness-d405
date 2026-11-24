"""Fixed roster, complete aggregation, and sole final reward publication."""
import asyncio
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import traceback
from pathlib import Path, PurePosixPath
from candidate_gate import validate

ROOT = Path('/tests')
WORKSPACE = Path('/workspace')
PROTOCOL = 'deep-swe-0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea-pier-b26211ed2bbee6d145f6b8c5b80e39f18b296f08-v1'
EVALUATOR_REVISION = 2  # Completion-gated provider accounting and command diagnostics.


def artifact_id(root):
    digest = hashlib.sha256()
    for p in sorted([root/'candidate.json', *(root/'candidate').rglob('*'), *(root/'research').rglob('*')]):
        digest.update(str(p.relative_to(root)).encode()+b'\0')
        if p.is_symlink(): digest.update(b'link\0'+os.readlink(p).encode())
        elif p.is_file():
            digest.update(b'file\0'+str(p.stat().st_mode & 0o777).encode()+b'\0')
            with p.open('rb') as f:
                for chunk in iter(lambda:f.read(1048576),b''): digest.update(chunk)
        else: digest.update(b'dir\0')
    return digest.hexdigest()


def contamination(root, archive):
    # Exact known answer-asset copies are a fail-closed gate; this is not a
    # claim of exhaustive detection of transformed data or pretraining exposure.
    forbidden = set()
    for m in archive:
        if m.isfile() and m.size >= 512 and ('/tests/' in m.name or '/solution/' in m.name):
            forbidden.add(hashlib.sha256(archive.extractfile(m).read()).digest())
    for top in ('candidate','research'):
        for p in (root/top).rglob('*'):
            if p.is_file() and not p.is_symlink():
                digest = hashlib.sha256()
                with p.open('rb') as f:
                    for chunk in iter(lambda:f.read(1048576),b''): digest.update(chunk)
                if digest.digest() in forbidden:
                    return [dict(code='data_boundary',path=str(p),field='',condition='Known evaluation answer material may not be included in the candidate or research data.')]
    return []


def unpack(scratch):
    import tomllib
    tasks = {}
    with tarfile.open(ROOT/'upstream.tar.gz') as archive:
        for member in archive:
            parts = PurePosixPath(member.name).parts
            if not member.isfile() or len(parts)<4 or parts[1]!='tasks': continue
            if parts[3] not in ('tests','task.toml','instruction.md'): continue
            if '..' in parts or member.size > 100*1024**2: raise RuntimeError('Unsafe packaged task asset.')
            relative = Path(*parts[2:]); dest = scratch/relative
            dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            with dest.open('xb') as f: f.write(archive.extractfile(member).read())
            dest.chmod(0o600)
    for p in sorted(scratch.iterdir()):
        config = tomllib.loads((p/'task.toml').read_text())
        config['_instruction'] = (p/'instruction.md').read_text()
        tasks[p.name] = config
    return tasks


async def evaluate(manifest, identity, scratch, final):
    from episode import solve, grade, EpisodeFailure
    roster = json.loads((ROOT/'roster.json').read_text())
    tasks_dir = scratch/'tasks'; tasks_dir.mkdir(mode=0o700)
    tasks = unpack(tasks_dir)
    if set(tasks) != set(roster['all']) or len(tasks)!=113 or len(roster['development'])!=34:
        raise RuntimeError('Packaged task membership mismatch.')
    images = json.loads(os.environ['DEEPSWE_IMAGE_LOCK'])
    if images.get('protocol') != PROTOCOL or set(images.get('images',{})) != set(tasks):
        raise RuntimeError('Preparation output is missing or does not match the fixed protocol.')
    for name, task in tasks.items():
        row = images['images'][name]
        if row['tag'] != task['environment']['docker_image'] or not re.fullmatch(r'public\.ecr\.aws/[^@]+@sha256:[a-f0-9]{64}',row['digest']):
            raise RuntimeError('Preparation image identity mismatch.')
    selected = roster['all'] if final else roster['development']
    completed = {}
    if final:
        plan = json.loads((ROOT/'final-plan.json').read_text())
        if plan['protocol']!=PROTOCOL or plan['artifact']!=identity or plan['policy']!='one-run' or plan.get('evaluator_revision')!=EVALUATOR_REVISION:
            raise RuntimeError('Final plan is not bound to this frozen artifact/protocol.')
        for row in plan['completed']:
            if row.get('artifact')!=identity or row.get('protocol')!=PROTOCOL or row.get('evaluator_revision')!=EVALUATOR_REVISION or row.get('task_id') not in selected or type(row.get('outcome')) is not int or row['outcome'] not in (0,1) or row['task_id'] in completed:
                raise RuntimeError('Invalid or duplicate trusted final checkpoint.')
            completed[row['task_id']] = row
    semaphore = asyncio.Semaphore(8)
    failures = []
    accounting = {}
    def emit(name, data):
        # Candidate output is always nested in JSON: it cannot forge a final
        # checkpoint record by writing control-looking lines to its stdout.
        if 'accounting' in data: accounting[name] = data['accounting']
        if not final: print(json.dumps({'task_id':name,**data},allow_nan=False),flush=True)
    async def one(name):
        async with semaphore:
            ep = scratch/name; ep.mkdir(mode=0o711); ep.chmod(0o711)
            try:
                patch = await solve(tasks[name],images['images'][name]['digest'],manifest,WORKSPACE,ep,lambda d:emit(name,d))
                outcome = await grade(tasks[name],images['images'][name]['digest'],tasks_dir/name,patch,ep)
                row = dict(task_id=name,outcome=outcome,status='completed',error_class=None,artifact=identity,protocol=PROTOCOL,evaluator_revision=EVALUATOR_REVISION,accounting=accounting.get(name,[]))
                completed[name] = row
                if final: print(json.dumps({'final_episode':row}),flush=True)
                else: emit(name,{'outcome':outcome,'status':'completed','error_class':None})
            except Exception as exc:
                code = exc.code if isinstance(exc,EpisodeFailure) else type(exc).__name__
                failures.append((name,code))
                if final:
                    print(json.dumps({'final_failure':{'task_id':name,'artifact':identity,'protocol':PROTOCOL,'evaluator_revision':EVALUATOR_REVISION,'error_class':code,'diagnostic':str(exc),'accounting':accounting.get(name,[])}}),flush=True)
                # No protected grader stream appears here; exception text from
                # control-plane failures remains actionable and credential-free.
                emit(name,{'outcome':None,'status':'unscored','error_class':code,'diagnostic':str(exc)})
            finally:
                shutil.rmtree(ep)
    await asyncio.gather(*(one(name) for name in selected if name not in completed))
    if failures or set(completed)!=set(selected):
        raise RuntimeError(f'Evaluation incomplete: {len(completed)}/{len(selected)} completed; {len(failures)} unscored. No reward.')
    reward = sum(completed[name]['outcome'] for name in selected)/len(selected)
    if not math.isfinite(reward) or not 0<=reward<=1: raise RuntimeError('Invalid aggregate.')
    summary = {'count':len(selected),'reward':reward}
    if final:
        dev = set(roster['development']); held = set(selected)-dev
        summary['reused_34'] = sum(completed[x]['outcome'] for x in dev)/34
        summary['remaining_79'] = sum(completed[x]['outcome'] for x in held)/79
    return summary


def main():
    os.umask(0o077)
    manifest, errors = validate(WORKSPACE)
    if errors:
        print(json.dumps({'status':'candidate_invalid','errors':errors}),flush=True)
        raise SystemExit(2)
    with tarfile.open(ROOT/'upstream.tar.gz') as archive:
        errors = contamination(WORKSPACE,archive)
    if errors:
        print(json.dumps({'status':'candidate_invalid','errors':errors}),flush=True)
        raise SystemExit(2)
    probe = subprocess.run(['rsi-isolate','isolation'],capture_output=True,text=True)
    if probe.returncode:
        # Only the documented root/no-Landlock open-tests exception may change
        # /tests permissions; never modify its content or children.
        if os.geteuid()==0 and 'Landlock' in probe.stderr and '/tests' in probe.stderr:
            ROOT.chmod(0o700)
            probe = subprocess.run(['rsi-isolate','isolation'],capture_output=True,text=True)
        if probe.returncode: raise RuntimeError('Isolation preflight: '+probe.stderr)
    isolation = json.loads(probe.stdout)
    if not isolation.get('landlock_abi') and isolation.get('mode') != 'userns':
        raise RuntimeError('Concurrent episode workers require enforced filesystem read grants (Landlock or user namespace isolation).')
    identity = artifact_id(WORKSPACE)
    final = (ROOT/'final-plan.json').is_file()
    try:
        with tempfile.TemporaryDirectory(prefix='deepswe-') as directory:
            scratch = Path(directory); scratch.chmod(0o711)
            summary = asyncio.run(evaluate(manifest,identity,scratch,final))
    except Exception:
        # No provider credential is placed in exception text by our transport.
        traceback.print_exc()
        raise SystemExit(1)
    print(json.dumps({'status':'completed',**summary}),flush=True)
    with open('/logs/verifier/reward.json','x',encoding='utf-8') as output:
        json.dump({'reward':summary['reward']},output,allow_nan=False)
