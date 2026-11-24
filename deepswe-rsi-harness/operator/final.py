#!/usr/bin/env python3
"""Operator-only final evaluation using the production Harness lifecycle.

The oracle only copies a frozen artifact; it performs no research or inference.
ProductionRuntimeServices constructs SandboxBroker, docker_env_runtime and
SandboxLifecycle with the real resource leases/firewall policy. No fake backend
or standalone Docker authority is substituted for that route.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROTOCOL='deep-swe-0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea-pier-b26211ed2bbee6d145f6b8c5b80e39f18b296f08-v1'
EVALUATOR_REVISION=2


def identity(root):
    h=hashlib.sha256()
    for p in sorted([root/'candidate.json',*(root/'candidate').rglob('*'),*(root/'research').rglob('*')]):
        h.update(str(p.relative_to(root)).encode()+b'\0')
        if p.is_symlink():h.update(b'link\0'+os.readlink(p).encode())
        elif p.is_file():
            h.update(b'file\0'+str(p.stat().st_mode&0o777).encode()+b'\0')
            with p.open('rb') as f:
                for b in iter(lambda:f.read(1048576),b''):h.update(b)
        else:h.update(b'dir\0')
    return h.hexdigest()


def harvest(state,plan,roster):
    records={x['task_id']:x for x in plan['completed']}
    failures={}
    for attempt in sorted(state.glob('attempt-*')):
        logs=list((attempt/'logs').glob('runs/**/feedback/agent-*.log'))+list((attempt/'logs').glob('runs/**/verifier/*/interrupted-feedback.log'))
        for path in logs:
            with path.open() as f:
                for line in f:
                    try:item=json.loads(line)
                    except ValueError:continue
                    if not isinstance(item,dict) or set(item) not in ({'final_episode'},{'final_failure'}):continue
                    kind=next(iter(item));row=item[kind];name=row.get('task_id')
                    if name not in roster['all'] or row.get('artifact')!=plan['artifact'] or row.get('protocol')!=PROTOCOL or row.get('evaluator_revision')!=EVALUATOR_REVISION:
                        raise RuntimeError('Invalid final checkpoint identity from trusted evaluator.')
                    if kind=='final_failure':failures[name]=row;continue
                    if type(row.get('outcome')) is not int or row['outcome'] not in (0,1):raise RuntimeError('Invalid final binary outcome.')
                    if name in records and records[name]!=row:raise RuntimeError('Conflicting completed episode; no best-of-repeats is allowed.')
                    records[name]=row
    plan['completed']=[records[k] for k in sorted(records)]
    plan['failures']=[failures[k] for k in sorted(failures) if k not in records]
    return records


def save(path,plan):
    pending=path.with_suffix('.tmp')
    with pending.open('w') as f:
        json.dump(plan,f,indent=2);f.flush();os.fsync(f.fileno())
    pending.replace(path)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--artifact',type=Path,required=True);ap.add_argument('--state',type=Path,required=True)
    ap.add_argument('--images',type=Path,required=True);ap.add_argument('--sandbox-policy',type=Path,required=True)
    ap.add_argument('--retry-infrastructure',action='append',default=[],metavar='TASK_ID')
    ap.add_argument('--retry-reason',default='')
    a=ap.parse_args();os.umask(0o077);root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root/'tests'))
    from candidate_gate import validate
    manifest,errors=validate(a.artifact.resolve())
    if errors:raise SystemExit(json.dumps(errors))
    aid=identity(a.artifact);roster=json.loads((root/'tests/roster.json').read_text())
    if a.state.resolve().is_relative_to(root) or a.state.resolve().is_relative_to(a.artifact.resolve()):
        raise SystemExit('Final state must be outside the task and frozen artifact.')
    a.state.mkdir(parents=True,exist_ok=True);a.state=a.state.resolve()
    # A private operator-owned state directory is the only checkpoint authority.
    if a.state.stat().st_uid!=os.geteuid() or a.state.stat().st_mode&0o077:
        raise SystemExit('Final state must be owned by this operator and mode 0700.')
    planfile=a.state/'plan.json'
    if planfile.exists():
        plan=json.loads(planfile.read_text())
        if plan['artifact']!=aid or plan['protocol']!=PROTOCOL or plan['policy']!='one-run' or plan.get('evaluator_revision')!=EVALUATOR_REVISION:raise SystemExit('Final state belongs to another artifact/protocol/evaluator revision; old checkpoints cannot bypass corrected inference gates.')
    else:
        plan=dict(protocol=PROTOCOL,evaluator_revision=EVALUATOR_REVISION,artifact=aid,policy='one-run',completed=[],attempts=[],failures=[])
        with planfile.open('x') as f:json.dump(plan,f,indent=2)
    if (a.state/'report.json').exists():raise SystemExit('Final report already exists; no best-of-repeats evaluation is permitted.')
    harvest(a.state,plan,roster);save(planfile,plan)
    failed={x['task_id'] for x in plan['failures']}
    if failed and (set(a.retry_infrastructure)!=failed or not a.retry_reason.strip()):
        raise SystemExit('Unscored episodes require an operator-established infrastructure cause before retry: '+', '.join(sorted(failed))+'. Supply each --retry-infrastructure TASK_ID and --retry-reason after diagnosis. Candidate failures cannot be selected for repeats.')
    number=max((int(p.name.split('-')[1]) for p in a.state.glob('attempt-*') if p.name.split('-')[1].isdigit()),default=0)+1
    attempt=a.state/f'attempt-{number}'
    attempt.mkdir();task=attempt/'task'
    shutil.copytree(root,task)
    # This operator-private task instance is never returned to adaptive Work.
    shutil.copytree(a.artifact,task/'solution/frozen',symlinks=True)
    if identity(task/'solution/frozen')!=aid or identity(a.artifact)!=aid:raise RuntimeError('Frozen artifact changed during materialization.')
    (task/'solution/solve.sh').write_text('#!/bin/bash\nset -euo pipefail\nrm -rf /workspace/candidate /workspace/research\ncp -a /solution/frozen/candidate /workspace/candidate\ncp -a /solution/frozen/candidate.json /workspace/candidate.json\ncp -a /solution/frozen/research /workspace/research\n')
    (task/'solution/solve.sh').chmod(0o755)
    (task/'tests/final-plan.json').write_text(json.dumps(plan))
    config=(task/'task.toml').read_text().replace('timeout_sec = 172800','timeout_sec = 219600').replace('timeout_sec = 72000','timeout_sec = 216000')
    (task/'task.toml').write_text(config)
    env=dict(os.environ);env['DEEPSWE_IMAGE_LOCK']=a.images.read_text()
    # No research broker, proxy, provider Agent or extra research credential.
    for key in list(env):
        if key.upper() in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','RSI_AGENT_API_BASE_URL','RSI_AGENT_API_KEY','OPENAI_BASE_URL','ANTHROPIC_BASE_URL'):
            env.pop(key)
    command=['rsi-harness','run',str(task),'--agent','oracle','--primary-reward','reward','--score-direction','maximize',
             '--sandbox-policy',str(a.sandbox_policy.resolve()),'--data-root',str(attempt/'runtime'),'--logs-root',str(attempt/'logs'),'--verbose']
    started=time.time();exit_code=None
    plan['attempts'].append(dict(directory=attempt.name,started=started,duration_sec=None,exit_code=None,completed=len(plan['completed']),
                                 infrastructure_retries=a.retry_infrastructure,retry_reason=a.retry_reason))
    save(planfile,plan)
    try:
        with (attempt/'operator.log').open('xb') as log:
            result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
            exit_code=result.returncode
    finally:
        records=harvest(a.state,plan,roster)
        plan['attempts'][-1].update(duration_sec=time.time()-started,exit_code=exit_code,completed=len(records))
        save(planfile,plan)
    if set(records)!=set(roster['all']):
        raise SystemExit(f'Final evaluation incomplete; {len(records)} trusted episodes checkpointed. Resume the same command after recovery. No accuracy report.')
    # Require the production Judge to finish cleanly; checkpoint completeness
    # alone does not turn a cleanup/infrastructure failure into a report.
    if exit_code!=0:raise SystemExit('Harness did not complete successfully. Recover and resume; completed episodes will not be repeated.')
    dev=set(roster['development']);held=set(roster['all'])-dev
    report=dict(protocol=PROTOCOL,evaluator_revision=EVALUATOR_REVISION,artifact=aid,policy='one-run',count=113,
        reward=sum(x['outcome'] for x in records.values())/113,
        reused_34=sum(records[x]['outcome'] for x in dev)/34,remaining_79=sum(records[x]['outcome'] for x in held)/79,
        inference_requests=sum(len(x.get('accounting',[])) for x in records.values()),cost_usd=None,
        usage_evidence='plan.json completed[].accounting and attempt logs include every observed request/retry; unavailable usage/cost remains null',
        attempts=plan['attempts'])
    with (a.state/'report.json').open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))


if __name__=='__main__':main()
