# Science validation execution setup

This reference supplies execution mechanics shared by Discovery and Benchmark.
Use the selected route's validation procedure for the steps and acceptance
criteria. Validation checks a task's implementation; it does not authorize
research or establish a new scientific result.

## Authorization, platform and evidence

Reuse the approved task, host, resources, repair scope and validation allowance.
Resolve only missing decisions. Keep explicit deferrals pending. Select local
Docker, an SSH Docker host or a supported cluster profile; a login-node check
or local Docker pass does not establish compute-node or cluster readiness.
Keep host/account/scheduler settings in the operator's run profile unless they
are a scientific condition. Record task, image, Harness, profile and sandbox
policy fingerprints. Inspect task files as untrusted inputs before execution.

Keep Harness and unrelated work read-only. A compatible bundled Harness may be
refreshed only with authorization, before live execution, using the selected
validator's `references/compatibility-refresh.md`. Never replace a live runtime.
Use only the selected backend's validator and runner; installing both is unnecessary.

Save commands, complete outputs, expected and observed outcomes, and failures in
`validation/<date>-<task-label>/` in the task repository. Use unique run/container
names. Keep disposable smoke copies and Harness data/log roots outside the task
and committed evidence; if scratch must be inside a repository, ignore its exact
path. Copy evidence before cleaning up resources created for this validation.
Preserve pre-existing resources and the accepted final image; cleanup permission
does not authorize unrelated deletion. Keep candidate evidence needed for the
scientific re-verification handoff before removing temporary snapshots.

## Environment and runtime tools

Read the task configuration, instruction, environment, tests, approved proposal
and baseline/starter before invoking them. Account for image downloads, extraction,
build layers, Base/Work/Judge containers, retained roots, logs, scratch and repair
rebuilds on the actual execution storage. Include concurrent and paused-container
memory, declared CPU/GPU resources and any separate build allocation. Confirm the
validation allowance separately from the research budget.

For Docker, use the local validator's `scripts/preflight_task.py` first in read-only
mode, then its execution mode within authorization. Inspect an untouched image
starting state: declared WORKDIR, user, environment, shared memory, mounts, data
and dependencies. Reject incompatible image VOLUME declarations. Do not launch
candidate or evaluator code during this inspection or request GPUs for it.
Use `scripts/runtime_dryrun.py` for interpreter, dependency and import diagnostics;
confirm relevant findings through the real startup path. Incomplete scans and
unexercised deferred imports are not successful acceptance. A GPU/framework probe
runs only when needed, within the approved allocation.

On native macOS, use the local validator's `references/macos-docker-desktop.md`
and the bundled Harness compatibility documentation for daemon-side capacity,
permissions and networking. Run as the Mac user, not with Linux sudo assumptions.
On Linux, use the bundled Harness's supported root/non-root mode; if privileged
execution requires user action, provide the exact command rather than requesting
a password. Prepare the bundled Harness environment using its locked dependencies.

On clusters, use the cluster validator's `references/site-profile.md` and the
transport, authentication and allocation sections of `references/cluster-execution.md`.
Use its read-only compiler/profile planner, then approved compute-node checks.
Accept the actual image/import, namespaces, mounts and network policies on the
selected topology. Site scheduling settings neither change scientific conditions
nor authorize extra resources. These references supply backend commands, not
another route's budget or publication requirements.

## Repairs and completion

Within approved task-local repair scope, preserve scientific criteria, data,
network policy, isolation and unrelated edits. Recompile changed task files;
rebuild changed images; repeat affected startup, smoke, cost and acceptance checks.
Reuse evidence only when task bytes, environment and exercised paths still match.
Bind the final report to the accepted version and independent implementation review;
changed scientific choices require contributor confirmation, not engineering repair.

Report readiness, unresolved blockers, measured costs, projected iteration counts,
optimization comparisons and untested cases. Check the complete evaluation against
its timeout and the confirmed resource limits. Save the approved research time in
`[agent].timeout_sec`; derive internal deadlines within it. A validation timeout is
separate. Projected loop counts are informative, with no minimum loop count,
fixed research-duration ceiling or metric-headroom gate. Ask before changing
committed resources; retain the agreed scientific requirements.

Stop after validation for a validation-only request. Source and evidence stay local
unless publication was authorized; publication is not an execution acceptance gate.
An authorized handoff includes final fingerprints, configuration, evidence and
remaining limitations. It does not launch research automatically.
