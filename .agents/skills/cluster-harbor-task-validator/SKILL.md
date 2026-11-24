---
name: cluster-harbor-task-validator
description: Validate an existing RSI-Harness Harbor task's environment, baseline Judge and iteration budget through an LSF, Slurm, Kubernetes, PBS or PJM site profile, including single-node allocations, then publish accepted task changes and validation evidence.
---

# Cluster Harbor Task Validator

Validate one complete task on the selected cluster. Accept a task path and an
external cluster profile; no proposal or regeneration is required. Select the
route below, using Harness's cluster scheduler and Apptainer transport.

## Science route

Choose from the approved task metadata and read only its procedure:

- Metric Benchmark: [Benchmark validation](references/benchmark-execution-validation.md).
- Discovery or an existing model-access rubric task: [Discovery validation](references/discovery-validation-entry.md).

The selected Science procedure is complete. Continue there and stop reading this
entry's General workflow below. It includes backend selection, authorization,
acceptance and handoff; reuse backend tools without importing General budget or
publication requirements.

## General validation

Select by execution backend: a single-node LSF, Slurm, Kubernetes, PBS or PJM allocation uses this
skill; an SSH host running Linux Docker uses `harbor-task-validator`. Use the
repository's bundled RSI-Harness and the configured external site profile.
For compatible general baselines, use native `--agent oracle --cluster` on a
Slurm, Kubernetes, PBS or PJM topology supported by the bundled Harness. Model-access Science uses its separate procedure above. The cluster reference covers multi-node acceptance limits and the
operator-side route for other backends or accepted legacy bundles.

Read [validation-workflow.md](references/validation-workflow.md) completely
before planning, including **Existing-task compatibility refresh** when an old
bundle needs updating. Read [cluster-execution.md](references/cluster-execution.md)
before live work and [site-profile.md](references/site-profile.md) for discovery
and scheduler selection. All helpers are bundled for independent installation.

On a new or restricted site, start with the compute-node check in
[Restricted sites and bounded allocations](references/cluster-execution.md#restricted-sites-and-bounded-allocations).
Site settings do not relax validation or add budget.

1. Inspect the task and run the read-only compiler/profile planner. Resolve
   resource, repair, cleanup and publication scope using existing authorization.
2. Build/accept the image and inspect its untouched starting state. Use no GPU
   workload; declare any site-required build GPU allocation separately.
3. Collect runtime diagnostics; confirm relevant findings on the real launcher.
4. Exercise a Smoke Judge on a reduced scratch copy, preserving GPU totals,
   isolation, assets and network policy. Measure required Work and Judge costs.
5. Apply the unchanged single-node budget/headroom helper. Calibrate only as
   permitted by the scientific contract and save the approved total budget to
   `[agent].timeout_sec`.
6. Accept the final version's full baseline Judge, reusing qualifying evidence.
7. Report `EXECUTION READY` only after the environment, baseline and budget
   gates pass. Automatically commit/push validated task/environment source,
   then validation evidence in a separate commit; verify both remote commits.

“Push environment” means task/environment source, not an image-registry upload.
Use lossless 80 MiB log splitting. Honor an explicit local-only request. A failed
push is a publication blocker, even when the baseline passed.

Do not run a research model or invoke Solution outside the selected baseline
validation route. Do not add a separate test of generic submission transport. Keep smoke/scratch state outside the actual task and
committed evidence. Keep Harness read-only except the authorized intake refresh;
canonical profiles and unrelated work remain read-only.

Pass the accepted task/image/Harness/profile/sandbox-policy fingerprints, saved
budget, baseline evidence and publication hashes to `cluster-rsi-task-runner`.
Continue only when experiment execution was requested; changing skills does not
require repeating an already resolved approval. Profile, sandbox policy or task
changes invalidate the affected evidence rather than silently reusing acceptance
from another cluster.
