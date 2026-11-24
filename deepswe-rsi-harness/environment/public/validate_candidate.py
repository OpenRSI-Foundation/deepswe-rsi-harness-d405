#!/usr/local/bin/python3 -I
"""Read-only public manifest and dependency-declaration check; no inference."""
import argparse
import json
import os
import stat
from pathlib import Path


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value: raise ValueError('Duplicate JSON field: '+key)
        value[key] = item
    return value


def invalid_constant(value):
    raise ValueError('Non-finite JSON constant: '+value)


def validate(root=Path('/workspace')):
    errors = []
    def fail(code, path, field, condition):
        errors.append(dict(code=code, path=str(path), field=field, condition=condition))
    mp = root / 'candidate.json'
    for p in root.iterdir():
        if p.name not in {'candidate', 'candidate.json', 'research'}:
            fail('scope_path', p, '', 'Only candidate/, candidate.json and research/ may exist in WORKDIR.')
    for name in ('candidate', 'research'):
        p = root / name
        if not p.is_dir() or p.is_symlink():
            fail('directory_type', p, '', 'Must be an ordinary directory.')
    if not mp.is_file() or mp.is_symlink() or mp.stat().st_size > 1048576:
        fail('manifest_file', mp, '', 'Must be an ordinary JSON file at most 1 MiB.')
        return None, errors
    try:
        m = json.loads(mp.read_text(), object_pairs_hook=unique, parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        fail('manifest_json', mp, '', f'Valid bounded UTF-8 JSON required: {type(exc).__name__}.')
        return None, errors
    if not isinstance(m, dict):
        fail('manifest_object', mp, '', 'The manifest must be a JSON object.')
        return None, errors
    if type(m.get('version')) is not int or m['version'] != 1:
        fail('manifest_version', mp, 'version', 'Must equal integer 1.')
    if m.get('mode') not in ('noop', 'custom'):
        fail('manifest_mode', mp, 'mode', 'Must be noop or custom; invalid custom candidates never become noop.')
    argv = m.get('entrypoint')
    if not isinstance(argv, list) or len(argv) > 128 or any(not isinstance(x, str) or '\0' in x or len(x) > 16384 for x in argv):
        fail('entrypoint_argv', mp, 'entrypoint', 'Must be a bounded string argument vector.')
    elif m.get('mode') == 'custom':
        if not argv or not argv[0].startswith('/workspace/candidate/'):
            fail('entrypoint_scope', mp, 'entrypoint[0]', 'Executable must live under /workspace/candidate/. Use a shebang for a baked interpreter.')
        else:
            p = root / Path(argv[0]).relative_to('/workspace')
            try:
                inside = p.resolve().is_relative_to((root/'candidate').resolve())
            except (OSError,RuntimeError):
                inside = False
            if not inside:
                fail('entrypoint_escape', p, 'entrypoint[0]', 'The resolved executable must stay inside candidate/.')
            elif not p.is_file() or not os.access(p, os.X_OK):
                fail('entrypoint_executable', p, 'entrypoint[0]', 'Must exist and be executable.')
    elif argv:
        fail('noop_entrypoint', mp, 'entrypoint', 'Noop requires an empty entrypoint vector.')
    deps = m.get('dependencies')
    if not isinstance(deps, list) or len(deps) > 100000 or any(not isinstance(x, str) or x in ('', '.', '..') or '/' in x or '\\' in x for x in deps):
        fail('dependency_list', mp, 'dependencies', 'List every top-level candidate entry by its basename.')
    elif (root / 'candidate').is_dir() and set(deps) != {p.name for p in (root / 'candidate').iterdir()}:
        fail('dependency_closure', mp, 'dependencies', 'Declared dependencies must equal all top-level candidate entries, including the executable.')
    providers = m.get('providers')
    if not isinstance(providers, list) or len(providers) > 32:
        fail('provider_list', mp, 'providers', 'Must be a list with at most 32 declarations.')
    else:
        for i, d in enumerate(providers):
            if not isinstance(d, dict) or d.get('provider') not in ('openai', 'anthropic') or not isinstance(d.get('model'), str) or not 1 <= len(d['model']) <= 256 or not isinstance(d.get('settings'), dict):
                fail('provider_declaration', mp, f'providers[{i}]', 'Declare provider, nonempty model and a settings object.')
    provenance = m.get('provenance')
    if not isinstance(provenance, list) or len(provenance) > 10000:
        fail('provenance_list', mp, 'provenance', 'Must be a bounded list of source/use declarations.')
    else:
        for i, d in enumerate(provenance):
            if not isinstance(d, dict) or any(not isinstance(d.get(k), str) or not d[k] or len(d[k]) > 8192 for k in ('source', 'use')):
                fail('provenance_declaration', mp, f'provenance[{i}]', 'Each entry requires nonempty source and use strings; generated data also require a source description.')
    count = 0
    for name in ('candidate', 'research'):
        base = root / name
        for parent, dirs, files in os.walk(base, followlinks=False):
            for filename in dirs + files:
                p = Path(parent) / filename
                count += 1
                if count > 100000:
                    fail('artifact_entries', base, '', 'At most 100000 entries are supported.'); return m, errors
                mode = p.lstat().st_mode
                if stat.S_ISLNK(mode):
                    try:
                        contained = p.resolve().is_relative_to(base.resolve()) and p.exists()
                    except (OSError,RuntimeError):
                        contained = False
                    if not contained:
                        fail('dependency_escape', p, '', 'Symlinks must resolve inside the same candidate-owned tree without cycles.')
                elif not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                    fail('artifact_type', p, '', 'Only regular files, directories and contained symlinks are supported.')
    return m, errors


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--json', action='store_true'); ap.parse_args()
    _, errors = validate()
    print(json.dumps({'status': 'candidate_invalid' if errors else 'structurally_valid', 'errors': errors, 'limits': 'Declarations and paths only; no runtime, contamination or inference proof.'}))
    raise SystemExit(bool(errors))
