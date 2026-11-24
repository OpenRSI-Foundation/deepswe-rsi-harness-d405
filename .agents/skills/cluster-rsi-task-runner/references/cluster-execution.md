# Cluster transport and allocation evidence

The cluster profile owns queue/group, partition/account/QoS/constraint (PBS:
queue/account/project; PJM: resource group/group), exclusivity, host
exclusions, GPUs per node, site binds, builder resources and run/log/image roots.
Use an explicitly configured profile, not the packaged example's placeholder
site values. Work/Judge GPU totals remain task-owned. Do not modify single-node
skills or the canonical profile while validating/running a task. Harness is
read-only except an authorized validator intake refresh, before live execution;
follow [compatibility refresh](compatibility-refresh.md). A runner hands upgrade needs
back to validation; it does not replace Harness during a run.

## Science Judge authentication

Keep the Work Agent/model, integrity-audit backend and task-owned rubric Judge
model distinct. Audit uses the selected Work Agent through `rsi-agent exec`;
rubric scoring uses `task.toml`'s `judge_model` / `judge_model_effort` through
`rsi-agent llm`. Do not change the Judge model to match Work.

Resolve scoring credentials independently before launch. A Codex Agent can lend
an eligible OpenAI API credential or ChatGPT login, but a custom endpoint is not
proof of eligibility. Claude cannot lend its credential to the OpenAI Judge.
Reuse a confirmed operator configuration; otherwise resolve only the missing
choice: `--judge-llm-auth api` (default variable `RSI_JUDGE_LLM_API_KEY`, or
`--judge-llm-api-key-env NAME`) or `--judge-llm-auth codex-login` (optionally
`--judge-llm-codex-home /absolute/path`). Pass these options through the planner
and retain them in the final Harness command. Preserve any additional reviewed
Judge endpoint/proxy settings explicitly in that command. Record variable names
and presence only; never read or print credentials. For cluster Codex login,
check the Harness's shared-path/refresh requirements on the selected host.

Planner `runtime.judge_auth` is an offline routing result, not authentication
verification. `missing-independent-auth` blocks launch; `verify-codex-lending`
requires actual credential-source verification before omitting independent auth.
`configured-not-verified` still requires host credential availability checks.
Record the resolved source in the run card separately from Work authentication.
For Science fixed-submit validation, pass `--disable-stop-hook` with the explicit
validation timeout so the Agent can exit after its one submission. Formal
research retains the default stop hook unless the user explicitly overrides it.

## Baseline validation transport

This Oracle procedure applies to compatible general baseline tasks. For public
model-access Science, follow the standalone Discovery fixed-submit
acceptance procedure; native Oracle does not provide its integrity-audit model access.

For Slurm, Kubernetes, PBS and PJM, use native Oracle when the bundled Harness supports
the task's allocation: single-node CPU/GPU, or (Slurm only) the existing
multi-node GPU-pool model.
Oracle runs `solution/solve.sh` in Work and submits through the real Engine and
independent Judge without a research model. First check the bundled version:

```bash
PYTHONDONTWRITEBYTECODE=1 <harness-python> -m rsi_harness.cli run /absolute/task \
  --agent oracle --cluster /absolute/site.toml \
  [--sandbox-policy /absolute/policy.toml] --dry-run
```

Record the resolved Work/Judge allocation and Harness fingerprint. If that
checkout rejects Oracle for the topology, report the version limitation and use
[the authorized intake refresh](compatibility-refresh.md) or an accepted legacy
route below. A newer Skill does not upgrade the pinned Harness; do not remove
its guard or call an external driver native Oracle.

For multi-node Oracle, `solve.sh` runs once on the controller and dispatches Work
ranks through the Harness's `torchrun`. It must wait for those commands before
returning. The disposable `/solution` is available only to Work, including remote
ranks, and is removed before Judge. Judge uses a separate node pool and frozen
candidate: two Work nodes plus one Judge node require three allocated nodes.
This is not arbitrary MPI, CPU-only distributed execution or cross-cluster
scheduling. Before a full baseline run, validate a short baseline on the
intended site's full topology; local tests or `--dry-run` alone do not validate
cluster execution.

For a supported version, after the resource limits are settled, run:

```bash
PYTHONDONTWRITEBYTECODE=1 <harness-python> -m rsi_harness.cli run /absolute/task \
  --agent oracle --cluster /absolute/site.toml \
  [--sandbox-policy /absolute/policy.toml] --timeout <baseline-plus-judge-seconds>
```

Oracle submits N times: `--max-submissions`, else the task's
`max_submissions`, else 1; with a budget of 1 the Harness judges after
`solve.sh`. Use an explicit N only
when repeated evaluations are needed, and allow time for baseline Work plus
all N blocking Judge rounds. Do not pass Docker `--gpus`, Work authentication,
or a reasoning effort. A separate task-declared Judge model still needs its
own supported Judge authentication. Multi-node plans currently reject both
`model_access` and `judge_model`; model-assisted Science Judges therefore need a
single-node plan. Oracle has no research model and cannot validate a Judge that
requires `model_access`. Use the Science scripted-Agent validation for that
contract instead; do not remove its audit or change its Judge model.

Accept native transport only when the exact run job completed successfully,
`solve.sh` exited zero, the expected number of rounds completed, and the native
reports and final result are present. Oracle's zero exit checks transport, not
scientific success: separately compare each reward and evidence with the task's
baseline acceptance requirements. Preserve failure logs, including a failing
Solution that still submits for diagnosis. A dry run proves no execution.

Image building/import, user namespaces, site GPU/QoS limits, disk and isolation
remain prerequisites. Never use sudo or assume that installing these skills
provides a working Apptainer environment. LSF Oracle, Oracle resume and segmented
Oracle runs remain unsupported. Isolation modes that forbid multi-node execution
still do so; Oracle does not bypass their restrictions.

### Other cluster backends and older bundles

For LSF or an explicitly accepted legacy bundle without native Oracle for its
topology, the operator-side baseline route below remains available. Report
exactly which route was used.
It does not establish native Oracle support. Do not invent `rsi-harness validate`,
a fake Agent, or a one-submission research run to stand in for acceptance.

Use a task-specific, operator-side driver under approved scratch/evidence,
outside the portable task and Harness checkout. Inspect the selected Harness
version's APIs before constructing it. Reuse these existing contracts:

- `cluster/bluevela/image.py`: image plan, compute-node build driver, checksum
  sidecar and cache validation. The builder is submitted through the selected scheduler.
- `cluster/bluevela/resources.py`: compile-derived logical resources, exact
  node arithmetic, Work/Judge allocation and timeout margins.
- `cluster/schedulers/lsf.py` (`LSFJobSpec`/`LSFScheduler`) or
  `cluster/schedulers/slurm.py` (`SlurmJobSpec`/`SlurmScheduler`) owns submission,
  wait and exact-job cancellation. Record numeric build and runtime job IDs.
- LSF reads `LSB_MCPU_HOSTS` through `cluster/bluevela/allocation.py`; Slurm uses
  `cluster/slurm/allocation.py` and `scontrol show hostnames`. Reuse the common
  allocation probe/partition contract to verify GPU visibility, shared storage,
  SIF checksum, local tmp and network on every node, then freeze Work/Judge pools.
- `cluster/bluevela/runtime.py`, `multinode.py`, `judge_controller.py` and
  `remote_worker.py`: inspect the worker templates, broker, phase binds,
  torchrun shim, snapshot/candidate authority, Judge control and process-group
  cleanup used by the formal runtime. Reuse that worker/Judge transport in the
  validation driver; adapt only task-specific baseline/evaluator entry points.

Driver sequence: accept the image/untouched seed; start required transport on
the owned allocation; prepare the approved baseline on Work only if needed;
freeze the candidate and stop Work compute; invoke `/tests/test.sh` on the
planned Judge pool using its network, read-only tests and phase-scoped assets;
retain stdout/stderr/reward/timing; drain worker/process groups and record the
allocation's terminal result. For a one-node resolution preserve the shared
runtime's one-node resource separation. For multi-node resolution every rank
uses the frozen node pools and approved world sizes. Never flatten multi-node
Judge into a login-node subprocess or bypass isolation by letting the Judge
write the Work tree or read it while Work runs.

Give the Judge what the formal runtime's `run_judge` gives it: the task image,
run as the invoking user, not root; Work's paused workspace bound read-only at
WORKDIR, not a copy; read-only `/tests`; writable `/logs/verifier`; a per-round
writable copy of the image's `/tmp`; the profile's `judge_binds`;
`rsi-isolate`, installed by
`rsi_harness.judge_agent.install_judge_isolate` and bound read-only at
`/opt/rsi-isolate` with its launcher at `/usr/local/bin/rsi-isolate`; and
`RSI_JUDGE_ISOLATION_FALLBACK` set to the profile's
`apptainer.judge_isolation_fallback`. Like the Harness, refuse a submission,
without counting it against `max_submissions`, while WORKDIR holds a FIFO,
socket or device file, or a directory that cannot be opened. A node with
neither Landlock nor usable user namespaces fails `rsi-isolate isolation` with
`123`; that is a site prerequisite, so report it `BLOCKED`. The fallback is
the operator's profile choice, never a validation repair.

Inspect this driver before running task code. It may contain scheduler/site
logic because it is operator tooling; the task may not. Do not call Agent
initialization just to obtain a baseline workspace, since that may launch an
Agent/authentication smoke. If the selected Harness/site cannot provide the
required isolation/transport without a framework change, report the concrete
compatibility blocker instead of claiming validation or patching Harness.

## Restricted sites and bounded allocations

On a new site, first run the bundled read-only check inside an ordinary job on
a compute node: `bash <skill-dir>/scripts/site_check.sh` (`--help` lists
options). On Kubernetes that job is a Pod made like the profile's: copy the
`job.json` a real submission wrote under `<run_dir>/build/<job>/` (its passwd
and group files sit beside it; a dry run writes none), give it a new name, drop its `rsi-harness.io/name` label
and set its command to the check on a shared volume; its host-side probes need
python3 in the runner image. It requires GNU `timeout` with `--kill-after`; if unavailable it exits
before probes instead of running unbounded. Binaries are selected from `PATH` or
explicit `--apptainer`, `--podman`, `--conmon` and `--runtime` paths. If the
running Apptainer does not report a readable configuration, pass
`--apptainer-config FILE` naming the active site configuration (inspection only;
it does not select a different runtime configuration). Unknown configuration is
not reported as a pass.
It needs no sudo and changes no persistent settings; its `SUMMARY` maps each
`NEEDS`, `WARN` or `FAIL` result to a setting below or its consequence, and a
`FAIL` blocks runs.

Check optional settings against the **bundled** Harness's schema, dry-run and
README section **Run multi-node tasks on a cluster**. Unsupported settings need
[an authorized refresh](compatibility-refresh.md), not a silent patch or upgrade.
`[scheduler]` rows are Slurm-only unless they name another scheduler; other
rows apply to every scheduler. None is a default for every site.

| Symptom seen in logs | Cause | Profile setting |
| --- | --- | --- |
| Build preflight `this node cannot create net namespaces` (or `uts`), or `RUN`: `failed to unshare remaining namespaces: No space left on device` | Node allows no network/UTS namespaces (`max_net_namespaces`/`max_uts_namespaces` = 0) | `[builder] host_namespaces = ["network", "uts"]` |
| No Podman on the compute nodes, or `could not find a working conmon binary` | Podman is missing or does not find its own helpers | `[builder] podman_bundle` = a shared directory: Harness installs its pinned static Podman there before the first build. Or, for the site's Podman, `[builder] conmon` and `runtime` as absolute paths |
| `build hint: rootless overlay is unavailable`, or an overlay whiteout error | Rootless overlay storage is unavailable | `[builder] storage_driver = "vfs"` |
| `Failed to create network namespace: maximum number of network namespaces exceeded` | Apptainer cannot create a network namespace for a no-network phase | `[apptainer] network_isolation = "seccomp"`; needs a runtime without setuid |
| `Not virtualizing pid namespace by configuration`, or the isolation check's `Work sees the Engine's process` | `apptainer.conf` sets `allow pid ns = no` | `[apptainer] process_namespaces = "harness"` |
| Landlock unavailable and the Judge is not root | Kernel without Landlock | None: `rsi-agent`, `rsi-isolate` and Science Judge library 9.4+ use user namespaces (`userns`) automatically. `judge_isolation_fallback = "same-user"` stays an explicit operator choice |
| The scheduler rejects the GPU option (`--gres=gpu:N`) | Site accepts only `--gpus` | `[scheduler] gpu_option = "gpus"` |
| Slurm rejects `--tmp`; nodes report `TmpDisk=0` | No schedulable local-disk resource | `[scheduler] request_tmp = false`; scratch capacity and compute-node free-space checks still apply, so never set required storage to zero |
| Build job rejected by the run partition/account/QOS, or a GPU partition rejects a GPU-less build | Builds need other scheduling | `[scheduler.build]` `partition`, `account`, `qos`, `constraint` (PBS: `queue`, `account`, `project`; PJM: `resource_group`, `group`), `gpus`, `exclusive`; Work/Judge resources stay unchanged |
| Slurm, PBS, PJM: partition, queue or resource-group time limit below the research run's walltime | Per-job limit | `[scheduler] run_walltime_limit = "HH:MM"`, then explicit resume (below); it caps each single-node research allocation, not the accepted Agent budget |
| `cannot resolve network policy hostname` or `does not support an upstream proxy` on nodes whose only egress is an HTTP proxy | No direct egress or external DNS | Keep the job's `HTTPS_PROXY` (or set `RSI_HTTPS_PROXY`). A compatible Harness tunnels the Agent's and independent Judge model's allowed endpoints through their configured proxies; it needs no broader task network access |
| A no-network phase fails with `Failed to set flags on interface: Operation not permitted` | The setuid runtime cannot isolate a network inside the job | `[apptainer] binary` = an Apptainer or SingularityCE without setuid; reuse the deployed runtime or follow the selected Harness's runtime setup documentation |
| `a setuid SingularityCE cannot run with network_isolation = "seccomp"` | A setuid SingularityCE isolates the network only with `network_isolation = "namespace"` | `[apptainer] network_isolation = "namespace"` where the node allows network namespaces; otherwise `[apptainer] binary` = a runtime without setuid |
| A setuid SingularityCE refused `inside a user namespace` | Setuid cannot work inside a user namespace (such as a userns Kubernetes Pod), in any isolation mode | `[apptainer] binary` = a runtime without setuid |
| `Disk quota exceeded` under `/tmp` though the node has local scratch | Per-job `/tmp` quota | `[resources] node_tmp_variable` = the variable naming each job's node-local scratch |
| `cannot execute binary file: Exec format error` when a job starts the Engine | Submit and compute nodes differ in architecture; the Engine runs with the controller's Python | None: start `rsi-harness run` in a job on a compute node, from a Harness installed for its architecture |
| Kubernetes: submission refused because the Pod `would not see these paths` | A path the jobs use is in no shared volume | `[[scheduler.volumes]]` at the submit host's path, or `scheduler.image_paths` for paths the image provides |
| Kubernetes: a job ends with `cannot start its container` (`ErrImagePull`, `ImagePullBackOff`, `CreateContainerConfigError`) | The runner image or Pod configuration is unusable | `scheduler.image`, `image_pull_secrets`, volumes; the image needs bash, coreutils, util-linux, tzdata and non-setuid Apptainer |
| Kubernetes: `kubernetes preflight: this Pod cannot create user namespaces` | Pod security, or nodes with `kernel.apparmor_restrict_unprivileged_userns=1` (Ubuntu 23.10+) | `scheduler.pod_security`; on such nodes `scheduler.apparmor_profile`, a Localhost profile allowing user namespaces |
| Kubernetes: GPU job refused because privileged Pods `see every GPU on the node` | Privileged containers get every host device | `pod_security = "userns"`, or `privileged_devices = "allocated"` where the runtime sets `privileged_without_host_devices` |
| Kubernetes: `kubernetes preflight: this Pod cannot mount a fresh /proc` | Something mounts over `/proc`: an NVIDIA runtime or CDI hook, or a masked `/proc` | Inject GPUs with CDI from a spec without the `disable-device-node-modification` hook; for a masked `/proc`, see `scheduler.pod_security` |

`network_isolation = "seccomp"` and `process_namespaces = "harness"` refuse
multi-node runs and restrict some phases (see that README section).

A site is usable only when a real run's pre-search isolation check passes:
`isolation_check.json` beside `run-plan.json` and the `isolation` summary in
`RUN_INFO.json`. Any failure there stops the run and no setting skips it; the
site check and dry runs do not replace it.

Use an operator-owned profile copy within the agreed resource limits; preserve
the canonical profile. Re-run planning and invalidate affected acceptance when
changing a profile. Run the Skill planner's `commands.dry_run` through the bundled
Harness and preserve its output before allocation. That public CLI is the authority
for the resolved build/run requests, per-allocation cap and advance signal; the
Skill does not reconstruct scheduler requests from private adapter methods.
`resource_plan.run_walltime` remains the uncapped estimate and the accepted Agent
budget remains unchanged. Confirm build and run requests separately, including
the build's own GPU/QOS limits. The capped dry run must leave room for Work, the
full Judge timeout, the profile margin and Slurm's early-warning allowance. A
resume needs its own `resume --dry-run`. Planning does not establish
compute-node readiness.

`exclusive=false` does not impose a GPU quota. Configure the profile for the
site's allocatable capacity and inspect the final request against QOS limits,
including both Work and Judge. Do not reduce task phase requirements or change
required separation merely to fit a quota.

Treat a pre-submission capacity mismatch as profile selection to resolve, not
an immediate contributor blocker. Within existing authorization and budget,
choose a suitable queue/allocation in an operator-owned profile copy and rerun
ordinary planning and the Harness dry-run; no scheduler-job evidence is needed. Preserve
task phase requirements and Work/Judge topology, and keep capacity values
faithful to the queue. Ask only if no suitable configuration is available
within the existing resource, budget and permission scope.

If Apptainer exists only on compute nodes, check whether the bundled Harness
supports compute-node binary preflight. Use an absolute executable path valid on those nodes; check
submission commands and shared paths on the submit host. A dry run does not
prove Apptainer, user namespaces, image construction or Judge isolation work:
validate them through the actual compute-node jobs. Missing subuid/fakeroot or a
rootless Podman installation alone establishes neither readiness nor failure.
A separately built, validated SIF is an alternative where the bundled image
import contract supports it; none of these settings bypass site permissions.

### Planned research interruption and explicit resume

When a supported single-node research run exceeds the allocation cap, Harness
requests advance termination and reserves Judge timeout plus walltime margin
for draining accepted submissions. Slurm may warn up to 60 seconds early; too
little room is rejected. An interrupted attempt exits nonzero and may appear
as `FAILED` in Slurm even when the planned drain occurred. Inspect the cause;
do not call it completed research or assume every failure is an expected stop.

Inspect the resolved allocation and remaining-attempt plan during validation;
the bundled Harness enforces its attempt and resource-grant limits. Do not copy
a numeric ceiling from another release or manually extend grants to bypass a
refused continuation.

Before continuing, confirm the exact job is terminal, inspect native results,
accepted Judge rounds, cleanup and lease accounting, and ensure no controller
or worker is still writing. Preserve each attempt's evidence, used Agent time
and remaining budget. For an authorized continuation with remaining budget:

```bash
rsi-harness resume RUN_ID --cluster /absolute/site.toml --dry-run
rsi-harness resume RUN_ID --cluster /absolute/site.toml
```

Use the same bundled Harness and run ID, inspect the new allocation plan and
record the new attempt/job IDs. The previous watcher monitors the old controller
PID and exits when that attempt stops. After verifying it has exited, start one
watcher for the resumed controller PID using the same run, destination and
publication state. The publisher reopens finality for the new attempt and checks
all recorded attempt jobs before final publication. Keep old commits/evidence;
do not delete publication state, create duplicate writers or start a new research
run instead. Resume is explicit, not an
automatic resubmission loop. Do not add `--add-time` merely to cross a scheduler
boundary or silently replace the agreed total budget with a shorter one.
Harness charges recorded Agent time against the original budget. If accounting
is missing or the lease remains active, follow its recovery result and report
that limitation rather than inventing unused time.

Workspace and Agent home persist; process state and other files are not a
general checkpoint. Forced interruption or an unfinished Judge remains
unverified; reserved time cannot guarantee completion under preemption or node
failure. A supported single-node sandbox research run can be segmented, but a
Judge round in flight at the signal counts as a submission and has no score.
**Oracle, multi-node runs and image builds cannot be segmented.** Baseline Oracle
must fit its full Work and Judge sequence into a supported allocation. Use a
sufficiently long allocation or explicitly agree a resource/budget revision; never split an
Oracle baseline, resume Oracle, or stitch partial baseline attempts into a pass.

## Formal experiment

The formal experiment uses `rsi-harness run <task> --cluster <profile>` with
the selected research Agent; baseline validation may use the same command
with `--agent oracle` as described above.
Harness owns image build/cache, source freeze, allocation, discovery, broker,
Work/Judge execution and cleanup. Preserve the invoking controller process for
the entire run. When the site's architecture or execution rules require a
compute-node controller, use an authorized controller allocation and a compatible
Harness environment there. Budget that allocation separately, with enough
walltime for queue waits and build/run completion. Harness still submits its own
build and Work/Judge jobs; do not manually duplicate those allocations or assume
they reuse the controller's resources. The exception is PBS/PJM
`scheduler.launch = "allocation"` (the plan's `profile.launch`): to queue once,
set it in an operator-owned profile copy and start `commands.run` from a job
script on a compute node, which then runs the build and run jobs itself. That
job requests the plan's `resource_plan.total_gpus` and walltime for the dry
run's build (unless the image is cached) and run plus five minutes;
`[scheduler.build]` overrides do not apply.

Record the actual run ID by matching emitted build/run job IDs against
`<profile.run_root>/<run-id>/RUN_INFO.json`, the task/profile and expected logs.
The dry-run ID is illustrative and differs from the real run. Never choose the
newest directory: concurrent runs are possible. Logs live at
`<profile.logs_root>/runs/<run-id>`; the publisher projects them into the task
repository's `logs/runs/<run-id>/` without changing the active checkout.

For Kubernetes, `kubectl get job <name> -o json` must show the exact Job
`Complete`, or `Failed` (failure evidence), or `Suspended` with the
`rsi-harness.io/cancelled` annotation and no Pod left (a cancellation, also
failure evidence); a queue's suspension is not an end. Success needs
`Complete` and the Pod's exit code 0 as the Harness reports it. An older Job
(the build, an earlier attempt) removed after `ttl_seconds_after_finished`
counts as stopped when no Pod of it remains and the run's latest Job is still
found; publish final logs within that TTL.

For PBS, `qstat -x -f -F json <id>` (the full ID, `96979.server`; plain
`qstat -x -f` when its JSON is unreadable) must show `job_state` `F` (or `X`);
success needs `Exit_status` 0, and `substate` 91 is a `qdel`. For PJM,
`pjstat -v --choose jid,st,ec,pc,sn <id>` must no longer list the job and
`pjstat -H day=31` with the same options must show it ended (`ST` `EXT`, `CCL`
or `RJT`); success needs `EXT` with `PC` and `EC` 0 (`PC` 1 is `pjdel`, 11 the
elapse limit, 12 and 23 memory). `ERR` is a held job that history never lists:
the Harness deletes it (`pjdel`, then `CCL`). As on Kubernetes, an older job
the server no longer lists counts as stopped only while the run's latest job is
found; publish final logs within the server's job history (PJM: 31 days). Job
logs are `<run_dir>/{build,run}/pbs.<id>.out|err` (PJM: `pjm.<id>`); cancel
only exact owned jobs with `qdel` or `pjdel`. Under `launch = "allocation"` an
ID is `<batch job ID>.local-<token>`: that job has stopped once
`<run_dir>/{build,run}/<name>-<token>/end` exists or its batch job has ended,
and it is cancelled with its controller.

`bsub`/`sbatch` success acknowledges submission, and absence from `squeue` is not
completion. For Slurm success require the exact allocation record (not `.batch` or
`.extern`) in `sacct` to be `COMPLETED` with `ExitCode=0:0`, plus durable native
results. Accounting delay is pending evidence. A failed terminal allocation
may still publish its final logs, but remains a failed experiment.

For LSF, `bjobs -a -noheader -o "jobid stat" <id>` must show the exact job as
`DONE` or `EXIT` before final publication; `EXIT` is failure evidence. `UNKWN`,
`ZOMBI`, suspended and pending states are not confirmed termination. `bjobs`
retains completed records only for `CLEAN_PERIOD` (normally one hour), so the
publisher queries `bhist -a -l -n 0 <id>` for purged jobs. Its latest timestamped
record must confirm completion/exit for that exact job, then live state is
rechecked for requeue. Missing, ambiguous or unrecognized history blocks final
publication. Use the site's `bhist` path with `--history-binary` when needed.
Do not delete old build IDs merely because they disappeared from `bjobs`.

These checks follow IBM's [bjobs output](https://www.ibm.com/docs/en/spectrum-lsf/10.1.0?topic=options-o),
[retention](https://www.ibm.com/docs/en/spectrum-lsf/10.1.0?topic=o-) and
[bhist history](https://www.ibm.com/docs/en/spectrum-lsf/10.1.0?topic=reference-bhist)
and Slurm's [sacct allocation records](https://slurm.schedmd.com/sacct.html).
They establish stopped allocations, not scientific success.

## Allocation fallback and retries

Start with the approved default profile. Never reduce resources because a job
is pending. A pre-authorized scheduling fallback uses a private profile and
changes only queue/group or partition/account/QoS, exclusivity and evidenced host exclusions
(Kubernetes: node selector, tolerations, priority class and host exclusions; PBS: queue,
account, project and exclusivity; PJM: resource group, group and exclusivity). Keep resources,
assets, storage, builder and constraints unchanged. Before switching a pending
default job, recheck it has not started; cancel only that exact owned pending
job and confirm its terminal accounting. Do not allocate both concurrently.

The read-only planner supports `--scheduler-policy allocation-fallback`,
`--base-cluster <unchanged-base-profile>`, `--cluster <private-fallback>` and
`--allocation-evidence '<JSON>'`. Evidence contains `default_job_id`,
`base_profile_sha256`, `work_gpus`, `judge_gpus` and either:

- `declared_wait_seconds` and two timezone-aware `observations` with
  `observed_at`, `status: PEND` (LSF) or `PENDING` (other schedulers), `reason`, separated by that wait window;
  plus later `inactive_confirmation` with the same `job_id`, `observed_at`,
  terminal `status` and `reason`; or
- a `terminal` object with `observed_at`, unsuccessful terminal `status` (`EXIT` for LSF;
  `FAILED`, `TIMEOUT` or `CANCELLED` for Kubernetes, whose `default_job_id` is the Job name;
  these or `OUT_OF_MEMORY` for PBS, whose `default_job_id` is the full job ID, and PJM),
  `reason` and `allocation_specific: true`.

This input records evidence, not permission. A completed full fallback run
supplies final evidence; do not duplicate it on the default partition. Diagnose
source defects separately from transient node/storage/scheduler faults. Keep
every failed attempt. Use a fresh run ID and clean baseline state for baseline
retries; never stitch partial checkpoints into a successful baseline. Planned
research continuation follows the same-run explicit resume route above. Resource,
science or endpoint changes outside the envelope require new authority.

## Controller loss and final upload

Do not stop a live Judge or useful Work because monitoring disappeared. Follow
[run completion and recovery](run-workflow.md#run-completion-and-recovery),
checking every writer and the recorded jobs before final upload. Preserve job
IDs, logs and publisher state; missing termination evidence blocks finalization.
