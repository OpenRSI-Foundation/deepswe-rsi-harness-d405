---
name: cluster-rsi-task-runner
description: Discover, run, monitor and recover a validated Harbor task with a read-only RSI-Harness through an LSF, Slurm, Kubernetes, PBS or PJM site profile, including single-node allocations, and publish its trajectories.
---

# Cluster RSI Task Runner

Run the repository's validated task with its accepted cluster profile. Like
`rsi-task-runner`, an invocation without arguments discovers the co-located
task and Harness. This stage does not generate tasks or silently redo accepted
baseline validation.

## Science route

Choose only the accepted task's running procedure:
- Metric Benchmark: [Benchmark run](references/benchmark-run.md).
- Discovery or an existing model-access rubric task: [Discovery run](references/discovery-run.md).

Both reuse the Harness execution/recovery workflow below. Run only after matching
backend validation and research authorization. Preserve confirmed budgets and
explicit deferrals; keep Harness and the accepted site profile read-only. Keep task and trajectory artifacts
local unless publication is authorized. Before launch, resolve the
[candidate-retention handoff](references/scientific-reverification.md#before-the-run)
or its explicit deferral. After research and accepted Judge work
finish, invoke `<task>/operator/trajectory-auditor/` (or the sibling skill), reading
its SKILL.md and references/science-final-integrity.md to select the route policy. Missing audit evidence remains
pending, not a clean result. Then initiate
[independent scientific re-verification](references/scientific-reverification.md)
in a fresh reviewer context before the completion report; report any unperformed
checks explicitly. These rules override generic upload instructions.

Select by execution backend: a single-node LSF, Slurm, Kubernetes, PBS or PJM allocation uses this
skill; an SSH host running Linux Docker uses `rsi-task-runner`. Use
`cluster-harbor-task-validator` for missing or invalidated baseline
acceptance on the selected profile, within the requested scope.

For model-access Science, resolve the independent rubric Judge credentials using
[Science Judge authentication](references/cluster-execution.md#science-judge-authentication)
before planning or launch; keep the accepted Judge model independent of Work.

Read [run-workflow.md](references/run-workflow.md) completely before execution.
Use [site-profile.md](references/site-profile.md) for discovery and cluster
selection, and [cluster-execution.md](references/cluster-execution.md) for
transport, allocation evidence and recovery.

On a new or restricted site, start with the compute-node check in
[Restricted sites and bounded allocations](references/cluster-execution.md#restricted-sites-and-bounded-allocations).
Site settings do not relax validation or add budget.

1. Discover task/Harness roots and record initial changes. Match accepted
   task/image/Harness/profile/sandbox-policy evidence and verified source
   publication; a refresh of only the bundled Harness and Skills keeps that
   acceptance. Missing or invalidated acceptance goes to
   `cluster-harbor-task-validator` before the experiment, within the user's
   requested scope.
2. Run the bundled environment/compiler/profile preflight. Resolve credentials
   by name/presence only, site binaries, shared storage and exact Work/Judge
   placement. Keep Harness and canonical profiles read-only.
3. Present the run card below, resolving only authority or information not
   already supplied. Default to the task's submission budget and the
   validated saved Agent budget. An explicit user model, timeout or submission
   cap wins.
4. Verify host publication prerequisites as the Harness execution user. Launch
   the exact normal Harness command, retaining its true controller PID and
   binding the actual run ID to its recorded scheduler job IDs.
5. Start the bundled host watcher: upload every **1800 seconds (30 minutes)**
   independently of Agent hooks, using the unchanged single-node publisher and
   lossless **80 MiB** splitter. Monitor the experiment and publisher separately.
6. Inspect durable results, submissions, reward and cleanup. Perform only
   authorized task-local repairs; revalidate and push source separately, then
   validation logs separately, before a fresh formal attempt.
7. After Harness and all Work/Judge allocation writers stop, verify the final
   trajectory upload and remote commit. Report experiment and publication
   outcomes separately; preserve logs when upload fails.
8. For Science, complete the final trajectory audit and scientific re-verification
   above, then issue the completion report. Keep their reports separate from run logs.

```text
Task / read-only Harness: <absolute paths>
Cluster profile / scheduler: <accepted path and fingerprint; LSF, Slurm, Kubernetes, PBS or PJM>
Work/Judge resources: <declared totals and profile-derived pools>
Agent/model/reasoning/auth: <choices; credential names/presence only>
Task runtime variables: <required names and present/missing>
Sandbox policy: <path and fingerprint, reviewed> | none
Agent time budget: <seconds and duration; explicit override or task.toml>
Submission budget: <unlimited or the task's `max_submissions`, unless the user explicitly requested N>
Stop behavior: <Agent budget includes blocking Judge; setup/cleanup may extend duration>
Science post-run review (omit for General): <reviewer/context and authorized resources, or deferred; separate from Agent time>
Data/log roots: <resolved paths>
Publication: <host user, confirmed remote/branch; 30-minute and final trajectory uploads,
              80 MiB parts, separate validated source and validation-log commits;
              or explicitly requested local-only>
Repair/cleanup scope: <existing authorization and retained resources>
Command: <exact Harness CLI command>
```

Use the [model, authentication and budget rules](references/run-workflow.md#resolve-the-exact-run):
explicit choices win; otherwise use the validated saved budget and the task's
submission budget. Never encode effort in the model name or expose secrets. No local
Docker `--gpus` option applies to cluster runs.

Report Run ID, status, budgets, submissions, best score, artifacts, repairs,
source/validation/run-log commits and last verified upload with its destination.
An uploaded trajectory does not establish a successful experiment.

For Science, include the scientific outcome summary specified in the sibling
[rsi-task-runner completion report](../rsi-task-runner/SKILL.md#completion-report).
