#!/usr/bin/env python3
"""Check required Harbor runtime environment templates and the sandbox policy
without exposing values."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path
from typing import Any


TEMPLATE = re.compile(r"^\$\{([^}:]+)(?::-(.*))?\}$")


def _table(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _missing_by_phase(config: dict[str, Any]) -> list[dict[str, Any]]:
    environment = _table(config.get("environment"))
    common = _table(environment.get("env"))
    verifier = dict(common)
    verifier.update(_table(_table(config.get("verifier")).get("env")))

    phases_by_name: dict[str, set[str]] = {}
    for phase, values in (("agent", common), ("verifier", verifier)):
        for value in values.values():
            if not isinstance(value, str):
                continue
            match = TEMPLATE.fullmatch(value)
            if match is None:
                continue
            name, default = match.groups()
            if default is None and name not in os.environ:
                phases_by_name.setdefault(name, set()).add(phase)

    return [
        {"name": name, "phases": sorted(phases)}
        for name, phases in sorted(phases_by_name.items())
    ]


def _sandbox_policy(config: dict[str, Any], policy: Path | None) -> str | None:
    """Return the policy problem, if any, for a task's sandbox request."""
    rsi_harness = _table(_table(config.get("metadata")).get("rsi_harness"))
    if "sandbox" not in rsi_harness:
        return None
    if policy is None:
        return "the task has a sandbox table: pass --sandbox-policy <reviewed policy>"
    if not policy.is_file():
        return f"sandbox policy is not a readable file: {policy}"
    return None


def _load(task_dir: Path) -> dict[str, Any]:
    path = task_dir.resolve() / "task.toml"
    try:
        with path.open("rb") as stream:
            value = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"cannot read task.toml: {error}") from None
    if not isinstance(value, dict):
        raise ValueError("task.toml root must be a table")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_dir", type=Path)
    parser.add_argument(
        "--sandbox-policy",
        type=Path,
        help="operator-reviewed policy; required when the task has a sandbox table",
    )
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = _load(args.task_dir)
    except ValueError as error:
        print(f"Runtime environment preflight error: {error}", file=sys.stderr)
        return 1
    missing = _missing_by_phase(config)
    policy = _sandbox_policy(config, args.sandbox_policy)
    ok = not missing and policy is None

    if args.json_output:
        payload: dict[str, Any] = {"missing": missing, "ok": ok}
        if policy:
            payload["sandbox_policy"] = policy
        print(json.dumps(payload, sort_keys=True))
    elif ok:
        print("Runtime environment preflight: ready")
    else:
        if missing:
            print("Runtime environment preflight: missing required host variables")
            for item in missing:
                print(f"- {item['name']} ({', '.join(item['phases'])})")
            print("Configure these variables in the host shell, then rerun this check.")
            print("Do not paste secret values into chat, task files, commands, or logs.")
        if policy:
            print(f"Runtime environment preflight: {policy}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
