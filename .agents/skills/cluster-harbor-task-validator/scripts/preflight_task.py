#!/usr/bin/env python3
"""Plan a task on an explicitly selected LSF, Slurm, Kubernetes, PBS or PJM profile without changing state."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tomllib
from datetime import datetime
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from check_runtime_env import _missing_by_phase, _table


NO_SANDBOX_SUPPORT = "bundled Harness lacks cluster sandbox support"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _load_harness(harness_root: Path) -> dict[str, Any]:
    root = harness_root.resolve()
    source = root / "src"
    if not (source / "rsi_harness/task/compiler.py").is_file():
        raise ValueError(f"RSI-Harness source not found under {root}")
    source_text = str(source)
    if source_text not in sys.path:
        sys.path.insert(0, source_text)

    # The adapters share this logical Work/Judge planner. Importing it does not
    # launch a scheduler or require the unselected backend.
    from rsi_harness.cluster import config as cluster_config
    from rsi_harness.cluster.bluevela.resources import derive_resource_plan
    from rsi_harness.models import CompileOptions
    from rsi_harness.task.compiler import HarborTaskCompiler

    return {
        "root": root,
        "source": source,
        "CompileOptions": CompileOptions,
        "HarborTaskCompiler": HarborTaskCompiler,
        "derive_resource_plan": derive_resource_plan,
        "load_cluster_profile": cluster_config.load_cluster_profile,
        "resolve_cluster_profile_path": getattr(cluster_config, "resolve_cluster_profile_path", None),
        # Compatibility with older Harness checkouts; profile names stay owned
        # by Harness rather than a second registry in the Skills.
        "packaged_profiles": getattr(cluster_config, "_PACKAGED_PROFILES", {}),
    }


SCHEDULERS = {("bluevela", "lsf"), ("slurm", "slurm"), ("kubernetes", "kubernetes"), ("pbs", "pbs"), ("pjm", "pjm")}
# Adapters whose every job runs on one node.
ONE_NODE = {"kubernetes": "Kubernetes runs use one Pod", "pbs": "PBS runs use one job", "pjm": "PJM runs use one job"}
# Profile fields an allocation fallback may change, per scheduler.
FALLBACK_FIELDS = {
    "lsf": {"queue", "group", "exclusive", "excluded_hosts"},
    "slurm": {"queue", "group", "exclusive", "excluded_hosts", "qos"},
    # Not the namespace: it selects the claims, secrets and policies a Pod gets.
    "kubernetes": {"node_selector", "tolerations", "excluded_hosts", "priority_class"},
    # queue is PJM's resource group; group is PBS's account (-A).
    "pbs": {"queue", "group", "project", "exclusive"},
    "pjm": {"queue", "group", "exclusive"},
}
# Exact default job evidence: a Kubernetes Job name, a full PBS job ID
# ("96979.server"), otherwise a numeric job ID.
JOB_IDS = {
    "kubernetes": (r"[a-z0-9]([a-z0-9-]{0,50}[a-z0-9])?", "the exact default Job name"),
    "pbs": (r"[1-9][0-9]*(\.[A-Za-z0-9][A-Za-z0-9_.-]*)?", "the exact default PBS job ID"),
}


def _kubectl_args(scheduler: Any) -> list[str] | None:
    if scheduler.kind != "kubernetes":
        return None
    args = []
    if scheduler.kubeconfig is not None:
        args += ["--kubeconfig", str(scheduler.kubeconfig)]
    if scheduler.context is not None:
        args += ["--context", scheduler.context]
    return args + ["--namespace", scheduler.namespace]


def _profile_path(harness: dict[str, Any], cluster: str | Path) -> Path:
    resolver = harness["resolve_cluster_profile_path"]
    if resolver is not None:
        return Path(resolver(cluster)).resolve()
    candidate = Path(cluster).expanduser()
    if candidate.is_file():
        return candidate.resolve()
    packaged = harness["packaged_profiles"].get(str(cluster))
    if packaged is not None:
        package, filename = packaged
        return Path(str(resources.files(package).joinpath(filename))).resolve()
    # A Harness from before the packaged-profile registry: its examples.
    example = harness["source"] / "rsi_harness/cluster" / str(cluster) / "profile.toml"
    if "/" not in str(cluster) and example.is_file():
        return example.resolve()
    raise ValueError(f"selected Harness cannot resolve packaged profile {cluster!r}; pass an explicit TOML path")


def _covered(path: PurePosixPath, target: PurePosixPath) -> bool:
    return path == target or target in path.parents


def _validate_asset_binds(definition: Any, profile: Any) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    for asset in definition.assets:
        binds = (
            profile.apptainer.work_binds
            if asset.phase == "work"
            else profile.apptainer.judge_binds
        )
        if not any(_covered(asset.path, item.target) for item in binds):
            missing.append({"phase": asset.phase, "path": str(asset.path)})
    return missing


def _scheduler_policy(
    profile: Any,
    *,
    policy: str,
    allocation_evidence: str | None,
    base_profile: Any = None,
) -> dict[str, object]:
    backend = profile.scheduler.kind
    if (profile.adapter, backend) not in SCHEDULERS:
        raise ValueError(
            "select adapter=bluevela/scheduler.kind=lsf, adapter=slurm/scheduler.kind=slurm, "
            "adapter=kubernetes/scheduler.kind=kubernetes, adapter=pbs/scheduler.kind=pbs "
            "or adapter=pjm/scheduler.kind=pjm"
        )
    if not profile.scheduler.queue.strip():
        raise ValueError("the site profile must declare a queue, partition, resource group or namespace")
    if policy == "default":
        if base_profile is not None:
            raise ValueError("--base-cluster is valid only for allocation-fallback")
        if allocation_evidence:
            raise ValueError(
                "allocation evidence is valid only for allocation-fallback"
            )
        evidence = None
    elif policy == "allocation-fallback":
        if base_profile is None:
            raise ValueError("allocation-fallback requires --base-cluster")
        if getattr(base_profile.scheduler, "launch", "submit") == "allocation":
            raise ValueError('launch = "allocation" submits no jobs to fall back from: '
                             "move the controller job to another queue instead")
        if (base_profile.adapter, base_profile.scheduler.kind) != (profile.adapter, backend):
            raise ValueError("fallback must keep the same adapter and scheduler")
        original = base_profile.model_dump(mode="json")
        fallback = profile.model_dump(mode="json")
        allowed = FALLBACK_FIELDS[backend]
        original.pop("name")
        fallback.pop("name")
        changes = {key for key in allowed if original["scheduler"][key] != fallback["scheduler"][key]}
        for key in allowed:
            original["scheduler"].pop(key)
            fallback["scheduler"].pop(key)
        if original != fallback:
            raise ValueError("fallback may change only approved scheduling fields, not resources, paths, binds, builder or constraints")
        if not changes:
            raise ValueError("fallback must change a scheduling field from the base profile")
        raw_evidence = (allocation_evidence or "").strip()
        if not raw_evidence:
            raise ValueError(
                "allocation-fallback requires observed allocation evidence"
            )
        evidence = _parse_allocation_evidence(raw_evidence, backend=backend)
    else:
        raise ValueError(f"unknown scheduler policy: {policy}")
    return {
        "name": policy,
        "allocation_evidence": evidence,
        "full_task_resources_required": True,
        "reduced_resources_require_explicit_user_instruction": True,
        "completed_run_is_final": True,
        "default_rerun_required": False,
        "shared_profile_mutation_forbidden": True,
        "confirm_default_inactive_before_fallback": policy == "allocation-fallback",
        "fallback_must_be_pre_authorized": policy == "allocation-fallback",
        "allocation_evidence_requirements": (
            "same full-size default job in two timestamped observations "
            "separated by the declared wait window, or an allocation-specific "
            "terminal scheduler reason"
            if policy == "allocation-fallback"
            else None
        ),
    }


def _parse_observed_at(value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("allocation evidence observed_at must be an ISO timestamp")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        observed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(
            "allocation evidence observed_at must be an ISO timestamp"
        ) from error
    if observed.tzinfo is None:
        raise ValueError("allocation evidence timestamps must include a timezone")
    return observed


def _parse_allocation_evidence(raw: str, *, backend: str) -> dict[str, object]:
    try:
        evidence = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("allocation evidence must be a JSON object") from error
    if not isinstance(evidence, dict):
        raise ValueError("allocation evidence must be a JSON object")
    job_id = evidence.get("default_job_id")
    pattern, described = JOB_IDS.get(backend, (r"[1-9][0-9]*", "a numeric default_job_id"))
    if not isinstance(job_id, str) or re.fullmatch(pattern, job_id) is None:
        raise ValueError(f"allocation evidence requires {described}")

    terminal_states = {"BOOT_FAIL", "CANCELLED", "DEADLINE", "FAILED", "NODE_FAIL",
                       "OUT_OF_MEMORY", "PREEMPTED", "REVOKED", "SPECIAL_EXIT", "TIMEOUT"}

    if backend == "lsf":
        terminal_states = {"EXIT"}
    elif backend == "kubernetes":
        # The states the Harness reports for a Job (``rsi-harness`` output).
        terminal_states = {"CANCELLED", "FAILED", "TIMEOUT"}
    elif backend in {"pbs", "pjm"}:
        # The Slurm states the Harness reports for a PBS or PJM job.
        terminal_states = {"CANCELLED", "FAILED", "OUT_OF_MEMORY", "TIMEOUT"}
    pending_state = "PEND" if backend == "lsf" else "PENDING"

    observations = evidence.get("observations")
    terminal = evidence.get("terminal")
    if isinstance(observations, list):
        wait_seconds = evidence.get("declared_wait_seconds")
        if (
            isinstance(wait_seconds, bool)
            or not isinstance(wait_seconds, (int, float))
            or not math.isfinite(wait_seconds)
            or wait_seconds <= 0
        ):
            raise ValueError(
                "pending allocation evidence requires positive "
                "declared_wait_seconds"
            )
        if len(observations) < 2:
            raise ValueError(
                "pending allocation evidence requires at least two observations"
            )
        timestamps: list[datetime] = []
        for item in observations:
            if not isinstance(item, dict):
                raise ValueError("allocation observations must be JSON objects")
            if str(item.get("status", "")).upper() != pending_state:
                raise ValueError(f"allocation observations must have status {pending_state}")
            if not str(item.get("reason", "")).strip():
                raise ValueError("allocation observations require scheduler reasons")
            timestamps.append(_parse_observed_at(item.get("observed_at")))
        if timestamps != sorted(timestamps) or (
            timestamps[-1] - timestamps[0]
        ).total_seconds() < float(wait_seconds):
            raise ValueError(
                "allocation observations must span the declared wait window"
            )
        inactive = evidence.get("inactive_confirmation")
        if not isinstance(inactive, dict) or inactive.get("job_id") != job_id:
            raise ValueError("pending fallback requires inactive_confirmation for the exact default job")
        if str(inactive.get("status", "")).upper() not in terminal_states or not str(inactive.get("reason", "")).strip():
            raise ValueError("inactive_confirmation requires an unsuccessful terminal scheduler status and reason")
        if _parse_observed_at(inactive.get("observed_at")) < timestamps[-1]:
            raise ValueError("inactive_confirmation must follow the pending observations")
    elif isinstance(terminal, dict):
        if terminal.get("allocation_specific") is not True:
            raise ValueError(
                "terminal allocation evidence must be allocation-specific"
            )
        status = str(terminal.get("status", "")).upper()
        if status not in terminal_states:
            raise ValueError(
                "terminal allocation evidence requires an unsuccessful terminal scheduler status"
            )
        if not str(terminal.get("reason", "")).strip():
            raise ValueError(
                "terminal allocation evidence requires scheduler reason"
            )
        _parse_observed_at(terminal.get("observed_at"))
    else:
        raise ValueError(
            "allocation evidence requires observations or terminal outcome"
        )
    return evidence


def _harness_contract_sha256(harness_root: Path, *, sandbox: bool = False) -> str:
    roots = (
        harness_root / "src/rsi_harness/task",
        harness_root / "src/rsi_harness/cluster",
    )
    digest = hashlib.sha256()
    for root in roots:
        if not root.is_dir():
            raise ValueError(f"missing Harness contract directory: {root}")
        subtree = _tree_sha256(root).encode()
        digest.update(root.name.encode())
        digest.update(subtree)
    paths = [
        harness_root / "src/rsi_harness/cluster/config.py",
        harness_root / "src/rsi_harness/models.py",
    ]
    if sandbox:
        # The sandbox rules live outside task/ and cluster/.
        paths += [
            harness_root / "src/rsi_harness/runtime/sandbox_policy.py",
            harness_root / "src/rsi_harness/runtime/sandbox_contracts.py",
        ]
    for path in paths:
        digest.update(path.name.encode())
        digest.update(_sha256(path).encode())
    return digest.hexdigest()


def _resource_envelope(resource_plan: Any) -> dict[str, Any]:
    if resource_plan.multi_node is not None:
        resources = resource_plan.multi_node
        return {
            "mode": "multi_node",
            "gpus_per_node": resources.gpus_per_node,
            "work_gpus": resources.work.gpu_count,
            "work_nodes": resources.work.node_count,
            "judge_gpus": resources.verifier.gpu_count,
            "judge_nodes": resources.verifier.node_count,
            "total_nodes": resources.total_nodes,
            "total_gpus": (
                resources.work.gpu_count + resources.verifier.gpu_count
            ),
            "cpu_slots_per_node": resources.cpu_slots_per_node,
            "memory_mb_per_node": resources.memory_mb_per_node,
            "node_tmp_mb": resources.node_tmp_mb,
            "shared_workspace_mb": resources.shared_workspace_mb,
            "build_walltime": resources.build_walltime,
            "run_walltime": resources.run_walltime,
            "pool_policy": "ordered disjoint Work prefix and Judge suffix",
        }
    resources = resource_plan.single_node
    assert resources is not None
    return {
        "mode": "single_node",
        "gpus_per_node": None,
        "work_gpus": resources.work_gpus,
        "work_nodes": 1,
        "judge_gpus": resources.verifier_gpus,
        "judge_nodes": 1,
        "total_nodes": 1,
        "total_gpus": resources.total_gpus,
        "cpu_slots_per_node": resources.cpu_slots,
        "memory_mb_per_node": resources.memory_mb,
        "node_tmp_mb": resources.local_tmp_mb,
        "shared_workspace_mb": resources.local_tmp_mb,
        "build_walltime": resources.build_walltime,
        "run_walltime": resources.run_walltime,
        "pool_policy": "legacy single-node Harness behavior",
    }


def judge_auth_plan(config: dict, agent: str, mode: str | None,
                    api_key_env: str | None, codex_home: str | None) -> dict:
    """Plan credential routing without reading secrets or claiming authentication."""
    if mode not in {None, "api", "codex-login"}:
        raise ValueError("invalid Judge authentication mode")
    if api_key_env is not None and mode != "api":
        raise ValueError("--judge-llm-api-key-env requires --judge-llm-auth api")
    if codex_home is not None and mode != "codex-login":
        raise ValueError("--judge-llm-codex-home requires --judge-llm-auth codex-login")
    judge = config.get("metadata", {}).get("rsi_harness", {}).get("verifier", {})
    model = judge.get("judge_model")
    if mode is not None and model is None:
        raise ValueError("Judge authentication requires task judge_model")
    if model is None:
        return {"status": "not-required", "flags": [], "blocking": False}
    if mode is None:
        return {"status": "verify-codex-lending" if agent == "codex" else "missing-independent-auth",
                "model": model, "effort": judge.get("judge_model_effort", "medium"),
                "flags": [], "blocking": True}
    flags = ["--judge-llm-auth", mode]
    if api_key_env is not None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", api_key_env):
            raise ValueError("Judge API credential must be an environment variable name")
        flags.extend(["--judge-llm-api-key-env", api_key_env])
    if codex_home is not None:
        flags.extend(["--judge-llm-codex-home", str(Path(codex_home).expanduser().resolve())])
    return {"status": "configured-not-verified", "model": model,
            "effort": judge.get("judge_model_effort", "medium"),
            "flags": flags, "blocking": False}


def build_plan(
    task_dir: Path,
    *,
    harness_root: Path,
    cluster: str | Path,
    scheduler_policy: str = "default",
    allocation_evidence: str | None = None,
    base_cluster: str | Path | None = None,
    agent: str = "codex",
    agent_auth: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    judge_llm_auth: str | None = None,
    judge_llm_api_key_env: str | None = None,
    judge_llm_codex_home: str | None = None,
    sandbox_policy: Path | None = None,
    disable_stop_hook: bool = False,
    timeout: float | None = None,
    max_submissions: int | None = None,
    primary_reward: str | None = None,
    score_direction: str | None = None,
    controller_executable: Path | None = None,
) -> dict[str, object]:
    """Validate and plan without allocating, building, or mutating state."""

    task = task_dir.resolve()
    if (task / "cluster").exists():
        raise ValueError(
            "portable RSI-Harness task contains a task-owned cluster control plane"
        )
    harness = _load_harness(harness_root)
    try:
        readme = (task / "README.md").read_text()
    except FileNotFoundError:
        readme = ""
    primary_match = re.search(r"--primary-reward\s+([^\s`]+)", readme)
    direction_match = re.search(r"--score-direction\s+(maximize|minimize)\b", readme)
    primary = primary_reward or (primary_match.group(1) if primary_match else "reward")
    direction = score_direction or (direction_match.group(1) if direction_match else "maximize")
    if direction not in {"maximize", "minimize"}:
        raise ValueError("score_direction must be maximize or minimize")
    # A README --max-submissions value is not the user's submission policy.
    if agent not in {"codex", "claude-code"}:
        raise ValueError("agent must be codex or claude-code")
    if agent_auth not in {None, "local"}:
        raise ValueError("agent_auth must be local when explicitly set")
    if max_submissions is not None and (type(max_submissions) is not int or max_submissions < 1):
        raise ValueError("max_submissions must be a positive integer when explicitly set")
    with (task / "task.toml").open("rb") as stream:
        config = tomllib.load(stream)
    configured_timeout = config.get("agent", {}).get("timeout_sec")
    effective_timeout = timeout if timeout is not None else configured_timeout
    if (isinstance(effective_timeout, bool) or not isinstance(effective_timeout, (int, float))
            or not math.isfinite(effective_timeout) or effective_timeout <= 0):
        raise ValueError("provide a positive --timeout or validated [agent].timeout_sec; no implicit 60-second budget")
    missing = _missing_by_phase(config)
    has_sandbox = "sandbox" in _table(_table(config.get("metadata")).get("rsi_harness"))
    if sandbox_policy is not None and not has_sandbox:
        raise ValueError("--sandbox-policy is only for a task with a sandbox table")
    if has_sandbox and sandbox_policy is None:
        raise ValueError('a sandbox task needs --sandbox-policy <operator policy with '
                         '[environments.host] backend = "e2b", "modal" or "daytona">')
    judge_auth = judge_auth_plan(config, agent, judge_llm_auth, judge_llm_api_key_env, judge_llm_codex_home)
    model = model or ("gpt-6-astra" if agent == "codex" else "claude-opus-5-5")
    reasoning_effort = reasoning_effort or "max"
    submissions = max_submissions
    options = harness["CompileOptions"](
        agent_name=agent,
        agent_timeout_seconds=effective_timeout,
        primary_reward=primary,
        score_direction=direction,
        max_submissions=submissions,
        disable_stop_hook=disable_stop_hook,
    )
    try:
        definition = harness["HarborTaskCompiler"]().compile(task, options)
        profile_file = _profile_path(harness, cluster)
        profile = harness["load_cluster_profile"](
            profile_file,
            environ={**os.environ, "USER": os.environ.get("USER", "operator")},
        )
        adapter_file = harness["source"] / f"rsi_harness/cluster/{profile.adapter}/adapter.py"
        if not adapter_file.is_file():
            raise ValueError(f"Harness lacks the selected {profile.adapter} adapter")
        if definition.gpu_requirement.count == 0 and (
            profile.adapter not in {"slurm", "kubernetes", "pbs", "pjm"}
            or getattr(definition, "require_disjoint_phase_nodes", False)
            or definition.verifier.gpu_count > profile.resources.gpus_per_node
        ):
            raise ValueError("CPU Work (Work gpus = 0) needs a single-node Slurm, Kubernetes, PBS or PJM plan")
        policy = None
        if has_sandbox:
            # Imported lazily: older bundled Harness copies lack these.
            try:
                from rsi_harness.runtime.sandbox_policy import (
                    load_sandbox_policy, resolve_env_grant, validate_cluster_sandbox, validate_sandbox_policy)
            except ImportError:
                raise ValueError(NO_SANDBOX_SUPPORT) from None
            if getattr(definition, "sandbox", None) is None:
                raise ValueError(NO_SANDBOX_SUPPORT)
            policy = load_sandbox_policy(sandbox_policy)
            # The adapter's _compile check; it must precede resolve_env_grant.
            validate_sandbox_policy(definition.sandbox, policy, "cluster")
        if getattr(definition.verifier, "clean_image", True) is False:
            raise ValueError("cluster Judges always start clean; run this clean_image = false task on local Docker")
        if "allowlist" in (
            definition.agent.network.mode,
            definition.verifier.network.mode,
        ):
            raise ValueError('clusters refuse "allowlist" networking; use "public" or "no-network"')
        resource_plan = harness["derive_resource_plan"](definition, profile)
        if profile.adapter in ONE_NODE and resource_plan.multi_node is not None:
            raise ValueError(f"{ONE_NODE[profile.adapter]} on one node; this task needs several nodes")
        # The grant the adapter freezes, from the public functions it calls.
        sandbox_grant = None if policy is None else resolve_env_grant(definition.sandbox, policy, {}, 1, 1)
        if sandbox_grant is not None:
            validate_cluster_sandbox(definition.sandbox, sandbox_grant, multi_node=resource_plan.multi_node is not None)
        base_file = _profile_path(harness, base_cluster) if base_cluster is not None else None
        if base_file == profile_file:
            raise ValueError("fallback must be a run-private copy, not the base profile")
        base_profile = harness["load_cluster_profile"](base_file) if base_file is not None else None
    except Exception as error:
        raise ValueError(str(error)) from error

    missing_assets = _validate_asset_binds(definition, profile)
    if missing_assets:
        detail = ", ".join(
            f"{item['phase']}:{item['path']}" for item in missing_assets
        )
        raise ValueError(f"profile does not bind declared task assets: {detail}")

    scheduler_contract = _scheduler_policy(
        profile,
        policy=scheduler_policy,
        allocation_evidence=allocation_evidence,
        base_profile=base_profile,
    )

    with (task / "task.toml").open("rb") as stream:
        config = tomllib.load(stream)
    metadata = config.get("metadata", {})
    baseline_status = (
        metadata.get("baseline_status") if isinstance(metadata, dict) else None
    )
    external_baseline_authority_required = (
        isinstance(baseline_status, str)
        and "certif" in baseline_status.lower()
        and "required" in baseline_status.lower()
    )
    resource_envelope = _resource_envelope(resource_plan)
    task_gpu_count = resource_envelope["work_gpus"]

    executable = harness["root"] / ".venv/bin/rsi-harness"
    cluster_argument = (
        str(profile_file)
    )
    run_command = [
        str(executable),
        "run",
        str(task),
        "--cluster",
        cluster_argument,
        "--primary-reward",
        primary,
        "--score-direction",
        direction,
    ]
    run_command.extend(["--agent", agent, "--model", model, "--reasoning-effort", reasoning_effort])
    if agent_auth is not None:
        run_command.extend(["--agent-auth", agent_auth])
    run_command.extend(judge_auth["flags"])
    if policy is not None:
        run_command.extend(["--sandbox-policy", str(sandbox_policy.resolve())])
    if disable_stop_hook:
        run_command.append("--disable-stop-hook")
    if timeout is not None:
        run_command.extend(["--timeout", str(timeout)])
    if submissions is not None:
        run_command.extend(["--max-submissions", str(submissions)])
    evidence = scheduler_contract["allocation_evidence"]
    if evidence is not None:
        if evidence.get("base_profile_sha256") != _sha256(base_file):
            raise ValueError("allocation evidence does not match the base profile digest")
        for phase in ("work_gpus", "judge_gpus"):
            if type(evidence.get(phase)) is not int or evidence[phase] != resource_envelope[phase]:
                raise ValueError(f"allocation evidence must use the task's full {phase}")
    return {
        "task": str(task),
        "workflow": "existing_task_validate_and_run",
        "runtime": {
            "missing_environment": missing,
            "environment_ready": not missing and not judge_auth["blocking"],
            "judge_auth": judge_auth,
            "disable_stop_hook": disable_stop_hook,
            "agent": agent,
            "agent_auth": agent_auth,
            "model": model,
            "reasoning_effort": reasoning_effort,
            "timeout_source": "explicit override" if timeout is not None else "task.toml [agent].timeout_sec",
            "submission_policy": "unlimited" if submissions is None else "explicit finite cap",
        },
        "publication": {
            "interval_seconds": 1800,
            "source_run_dir": str(profile.storage.logs_root / "runs" / "<run-id>"),
            "run_info": str(profile.storage.run_root / "<run-id>" / "RUN_INFO.json"),
            "destination_path": "logs/runs/<run-id>",
            "status_binary": getattr(profile.scheduler, "status_binary", None)
            or getattr(profile.scheduler, "kubectl", None),
            # The publisher's --kubeconfig/--context/--namespace for Kubernetes.
            "kubectl_args": _kubectl_args(profile.scheduler),
            "accounting_binary": getattr(profile.scheduler, "accounting_binary", None),
            "scheduler": profile.scheduler.kind,
            "remote_and_branch": "use the confirmed existing destination",
            "validated_task_push_before_run": True,
            "validation_logs_separate_commit": True,
        },
        "fingerprints": {
            "task_sha256": _tree_sha256(task),
            "harness_contract_sha256": _harness_contract_sha256(harness["root"], sandbox=policy is not None),
            "profile_sha256": _sha256(profile_file),
            "base_profile_sha256": _sha256(base_file) if base_file is not None else None,
            "sandbox_policy_sha256": _sha256(sandbox_policy) if policy is not None else None,
        },
        "task_contract": {
            "schema_version": config.get("schema_version"),
            "task_id": definition.task_id,
            "work_gpus": task_gpu_count,
            "judge_gpus": definition.verifier.gpu_count,
            "agent_timeout_sec": definition.agent.timeout_seconds,
            "verifier_timeout_sec": definition.verifier.timeout_seconds,
            "primary_reward": primary,
            "score_direction": direction,
            # The run's budget: an explicit cap, else the task's own
            # max_submissions (Harnesses that read it); None is unlimited.
            "max_submissions": getattr(definition.verifier, "max_submissions", submissions),
            "baseline_status": baseline_status,
            "external_baseline_authority_required": (
                external_baseline_authority_required
            ),
            "assets": [
                item.model_dump(mode="json") for item in definition.assets
            ],
            "sandbox_phases": [
                phase for phase in ("work", "judge")
                if sandbox_grant is not None and getattr(sandbox_grant.environments, phase) is not None
            ],
        },
        "profile": {
            "name": profile.name,
            "source": str(profile_file),
            "adapter": profile.adapter,
            "scheduler_kind": profile.scheduler.kind,
            "queue_or_partition": profile.scheduler.queue,
            "group_or_account": profile.scheduler.group,
            "project": getattr(profile.scheduler, "project", None),
            "qos": getattr(profile.scheduler, "qos", None),
            "constraint": getattr(profile.scheduler, "constraint", None),
            "exclusive": profile.scheduler.exclusive,
            "excluded_hosts": list(profile.scheduler.excluded_hosts),
            "gpus_per_node": profile.resources.gpus_per_node,
            # PBS/PJM: "allocation" runs the jobs inside the controller's own job.
            "launch": getattr(profile.scheduler, "launch", None),
            "node_machine": getattr(profile.resources, "node_machine", None),
            "run_root": str(profile.storage.run_root),
            "image_cache": str(profile.storage.image_cache),
            "logs_root": str(profile.storage.logs_root),
        },
        "resource_plan": resource_envelope,
        "scheduler_policy": scheduler_contract,
        "static_validation": {
            "errors": 0,
            "generation_review": "reuse existing review; generator formatting is not an execution gate",
            "live_ready": False,
            "ready_for_live_checks": True,
            "compiler": "passed",
            "profile_asset_coverage": "passed",
        },
        "commands": {
            "dry_run": [*run_command, "--dry-run"],
            "run": [str(controller_executable or executable), *run_command[1:]],
        },
        "live_gates": [
            "PROFILE_READY",
            "IMAGE_READY",
            "ALLOCATION_READY",
            "ENVIRONMENT_ACCEPTED",
            "RUNTIME_DIAGNOSED",
            "SMOKE_JUDGE_PASSED",
            "BUDGET_APPROVED",
            "FULL_BASELINE_JUDGE_PASSED",
            "EXECUTION_READY",
            "VALIDATED_TASK_PUBLISHED",
            "EXPERIMENT_COMPLETED",
            "FINAL_LOGS_PUBLISHED",
        ],
        "conditional_baseline_authority": {
            "required": external_baseline_authority_required,
            "acceptance": (
                "fresh uninterrupted rewardless certification followed by one "
                "normal finite-reward baseline run"
                if external_baseline_authority_required
                else "one normal scoreable baseline run"
            ),
        },
        "execution_policy": {
            "canonical_profile_mutation_forbidden": True,
            "task_mutation_after_freeze_forbidden": True,
            "fallback_must_keep_task_resource_totals": True,
            "resource_reduction_requires_explicit_user_instruction": True,
            "completed_fallback_requires_no_duplicate_default_run": True,
            "interrupted_certification_stitching_forbidden": True,
        },
        "approval_scope": (
            "named fingerprints, data preparation, SIF build/cache, exact final "
            "allocation, in-envelope source-controlled repairs/fresh retries, and "
            "cleanup of exact resources created by this validation"
        ),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", type=Path)
    parser.add_argument("--harness-root", type=Path, required=True)
    parser.add_argument(
        "--cluster",
        required=True,
        help="site profile path or a packaged profile name supported by the selected Harness for offline planning",
    )
    parser.add_argument("--agent", choices=("codex", "claude-code"), default="codex")
    parser.add_argument("--agent-auth", choices=("local",),
                        help="explicit Work login source, forwarded to Harness; omit for API credentials")
    parser.add_argument("--primary-reward")
    parser.add_argument("--score-direction", choices=("maximize", "minimize"))
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort")
    parser.add_argument("--judge-llm-auth", choices=("api", "codex-login"))
    parser.add_argument("--judge-llm-api-key-env")
    parser.add_argument("--judge-llm-codex-home")
    parser.add_argument("--sandbox-policy", type=Path,
                        help="operator-reviewed remote-backend policy; required when the task has a sandbox table")
    parser.add_argument("--disable-stop-hook", action="store_true", help="fixed-submit validation only when explicitly selected")
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--max-submissions", type=int, help="explicit user cap only; default unlimited")
    parser.add_argument(
        "--scheduler-policy",
        choices=("default", "allocation-fallback"),
        default="default",
    )
    parser.add_argument("--allocation-evidence")
    parser.add_argument("--base-cluster", help="unchanged approved profile to compare against a run-private fallback")
    parser.add_argument("--controller-executable", type=Path,
                        help="rsi-harness for commands.run when the controller runs on nodes of another architecture")
    parser.add_argument("--json", action="store_true", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        plan = build_plan(
            args.task,
            harness_root=args.harness_root,
            cluster=args.cluster,
            scheduler_policy=args.scheduler_policy,
            allocation_evidence=args.allocation_evidence,
            base_cluster=args.base_cluster,
            agent=args.agent,
            agent_auth=args.agent_auth,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            judge_llm_auth=args.judge_llm_auth,
            judge_llm_api_key_env=args.judge_llm_api_key_env,
            judge_llm_codex_home=args.judge_llm_codex_home,
            sandbox_policy=args.sandbox_policy,
            disable_stop_hook=args.disable_stop_hook,
            timeout=args.timeout,
            max_submissions=args.max_submissions,
            primary_reward=args.primary_reward,
            score_direction=args.score_direction,
            controller_executable=args.controller_executable,
        )
    except (FileNotFoundError, OSError, ValueError, tomllib.TOMLDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(plan, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
