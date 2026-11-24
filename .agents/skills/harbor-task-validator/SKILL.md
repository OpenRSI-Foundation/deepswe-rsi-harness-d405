---
name: harbor-task-validator
description: Validate a complete RSI-Harness Harbor task's Docker environment, baseline Judge, and iteration budget on Linux Docker or a supported native macOS Docker Desktop backend before an Agent experiment.
---

# Harbor Task Validator

Validate one complete Harbor task's environment, baseline execution, and
iteration budget. Accept one absolute task directory; generation, static
checks, RSI-Harness compilation, and task review are assumed complete. For general
baseline tasks, Judge runs go through the task repository's bundled RSI-Harness with
`--agent oracle`, which submits the baseline that `solution/solve.sh`
materializes.

## Science route

Choose from the approved task metadata and read only its procedure:

- Metric Benchmark: [Benchmark validation](references/benchmark-execution-validation.md).
- Discovery or an existing model-access rubric task: [Discovery validation](references/discovery-validation-entry.md).

The selected Science procedure is complete. Continue there and stop reading this
entry's General workflow below. It includes backend selection, authorization,
acceptance and handoff; reuse backend tools without importing General budget or
publication requirements.

## General validation

Select by execution backend: Linux Docker (including over SSH) and the supported
native macOS Docker Desktop backend use this skill. For macOS, first read the
**Native macOS Docker Desktop** procedure in the required reference; support is
version-, task- and credential-dependent, not implied by a reachable daemon.
For an LSF, Slurm, Kubernetes, PBS or PJM site profile, use
`cluster-harbor-task-validator`, even for a single-node allocation. That skill
checks native `--agent oracle --cluster`
support for compatible general baselines on the bundled version and topology,
including multi-node limits. Discovery and existing rubric-runtime tasks retain their model-backed procedure. After
validation, use the runner for that backend only when execution was requested.

## Required reference

Read [references/execution-validation.md](references/execution-validation.md)
completely before planning or executing validation. It is the single source
for resource approval, checks, repair/revalidation rules, budget judgments,
calibration, and publication. Its **Existing-task compatibility refresh**
section covers old bundled Harness/Skills and task-local compatibility repairs;
no new proposal is needed merely to refresh a compatible task.

Consult [references/known-pitfalls.md](references/known-pitfalls.md) when an
observed failure or task configuration matches an entry. A framework name
alone is not a reason to modify a working task.

## Seven-step workflow

1. **Intake and envelope**: inspect the task, run the read-only planner, and
   obtain approval for the resource, repair, cleanup, and publication scope.
2. **Environment acceptance**: build or pull the image and inspect its untouched
   starting state without GPU work.
3. **Runtime dry-run**: collect dependency diagnostics and confirm findings on
   the real startup path; perform a framework launch probe only when needed,
   using its approved CPU/GPU path. Scan completion is not task acceptance.
4. **Smoke Judge**: run the oracle on a reduced scratch copy of the task and
   measure Judge and required Work costs.
5. **Projection and judgment**: apply the iteration-budget and bounded-metric
   headroom rules; repair and calibrate only as needed.
6. **Full Judge acceptance**: run the oracle on the final task version,
   reusing a qualifying calibration rather than repeating it.
7. **Result and handoff**: before reporting `EXECUTION READY`, write the final
   approved total budget `T` to `[agent].timeout_sec` in `task.toml`. Report the
   evidence and status; publish task changes and validation logs in separate
   commits.

## Boundaries

- Keep RSI-Harness and unrelated repositories read-only, except the
  bundled-Harness refresh in the reference. Make only task-local changes
  within the approved envelope; preserve unrelated user edits.
- Run Solution only through the oracle. Do not run a real Agent, a
  repeatability/variance study, or a separate test of the Harness's generic
  submission transport.
- Keep smoke copies out of the actual task and keep disposable runtime state
  out of the committed evidence directory, as specified in the reference.

The helpers use Python's standard library and the Docker CLI. Task assets,
RSI-Harness, `uv` (for its `.venv`), Docker, root or the bundled Harness's non-root mode on Linux (or the supported Docker Desktop backend), and approved network/credentials
are prerequisites; NVIDIA is needed only for GPU probes or phases. Publishing
oversized logs also uses the bundled log splitter from `rsi-task-runner`.
