#!/usr/bin/env python3
"""Read-only generation checks. Parse task code as data; never import/execute it."""
import ast
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tomllib
from pathlib import Path

root=Path(__file__).resolve().parents[1]
files=sorted(p for p in root.rglob('*') if p.is_file())
assert root.name=='deepswe-rsi-harness' and not root.is_symlink()
assert all(p.stat().st_size<=100*1024**2 for p in files)
assert not any(p.is_symlink() for p in root.rglob('*'))
for p in files:
    if p.suffix=='.py':ast.parse(p.read_text(),filename=str(p))
    elif p.suffix=='.json':json.loads(p.read_text())
    elif p.suffix=='.toml':tomllib.loads(p.read_text())
    elif p.suffix=='.sh':subprocess.run(['bash','-n',str(p)],check=True)
    elif p.suffix=='.js' and shutil.which('node'):subprocess.run(['node','--check',str(p)],check=True)
config=tomllib.loads((root/'task.toml').read_text())
assert config['task']['name']=='rsi/'+root.name
assert config['agent']['timeout_sec']==172800 and config['verifier']['timeout_sec']==72000
assert config['environment']['gpus']==0 and config['environment']['workdir']=='/workspace'
assert os.access(root/'solution/solve.sh',os.X_OK) and os.access(root/'tests/test.sh',os.X_OK)
roster=json.loads((root/'tests/roster.json').read_text())
assert len(roster['development'])==len(set(roster['development']))==34
assert len(roster['all'])==len(set(roster['all']))==113
assert set(roster['development'])<set(roster['all'])
assert set(json.loads((root/'environment/development.json').read_text()))==set(roster['development'])
expected='2c3178146ae5d5e4dce988691e90e79c608fcc9d2ea0c9f20ac96e137f73b94b'
assert hashlib.sha256((root/'tests/upstream.tar.gz').read_bytes()).hexdigest()==expected
with tarfile.open(root/'tests/upstream.tar.gz') as archive:
    configs={}
    names=set(archive.getnames())
    for m in archive:
        assert not m.name.startswith('/') and '..' not in Path(m.name).parts
        if m.isfile() and m.name.endswith('/task.toml'):
            v=tomllib.loads(archive.extractfile(m).read().decode());name=m.name.split('/')[-2]
            configs[name]=v
            for f in ('instruction.md','tests/test.sh','tests/grader.py','tests/config.json'):
                assert m.name.removesuffix('task.toml')+f in names,(name,f)
            assert v['agent']['timeout_sec']==10800 and v['verifier']['timeout_sec']==1800
            assert len(v['verifier']['collect'])==1 and v['verifier']['collect'][0]['timeout_sec']==300
            assert v['environment']['cpus']==2 and v['environment']['memory_mb']==8192
    assert set(configs)==set(roster['all'])
with tarfile.open(root/'environment/pier.tar.gz') as archive:
    assert not any('/tests/' in m.name or '/solution/' in m.name for m in archive)
    lock=tomllib.loads(archive.extractfile('uv.lock').read().decode())
    assert any(p['name']=='harbor' and p['version']=='0.5.0' for p in lock['package'])
    # Check adapter overrides against the pinned abstract interface as AST data.
    tree=ast.parse(archive.extractfile('src/pier/environments/base.py').read().decode())
    required={n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and any(isinstance(d,ast.Name) and d.id=='abstractmethod' for d in n.decorator_list)}
    delivered=ast.parse((root/'tests/managed.py').read_text())
    actual={n.name for n in ast.walk(delivered) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    assert required<=actual,required-actual
assert not (root/'OVER_BUDGET.flag').exists()
assert not (root/'tests/final-plan.json').exists()
# Resumed final records must use the same corrected evaluator revision in
# both the trusted checkpoint writer/reader and operator driver.
revisions=[]
for path in ('tests/evaluate.py','operator/final.py'):
    tree=ast.parse((root/path).read_text())
    revisions.append(next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='EVALUATOR_REVISION' for t in n.targets)))
assert revisions==[2,2]
assert all(os.access(root/'environment/public'/p,os.X_OK) for p in ('reference.py','research.py','validate_candidate.py'))
# Import reachability is inspected without executing the candidate, evaluator,
# Pier, or isolation launcher. Baked package imports are verified at execution.
launch=ast.parse((root/'tests/launch.py').read_text())
assert any(isinstance(n,ast.ImportFrom) and n.module=='evaluate' for n in ast.walk(launch))
assert "sys.path.insert(0, \"/tests\")" in (root/'tests/launch.py').read_text()
harness=root.parents[1]/'public-evidence/RSI-Harness'
if harness.is_dir():
    client=ast.parse((harness/'src/rsi_harness/integrations/sandbox_client.py').read_text())
    methods={n.name for n in ast.walk(client) if isinstance(n,ast.FunctionDef)}
    assert {'image_pull','follow_job','env_create','env_start','wait_env','exec_start','exec_wait','follow_exec','exec_kill','upload_stage','download_stage','copy_in','copy_out','env_destroy','image_release'}<=methods
    runtime=(harness/'src/rsi_harness/runtime/production.py').read_text()
    assert all(x in runtime for x in ('SandboxBroker(', 'docker_env_runtime(', 'SandboxLifecycle()'))
print(f'PASS: parsed {len(files)} files; exact 113/34 assets, immutable archive, locked Pier, adapter interface, shell syntax, size and static contract checks. No task code executed.')
