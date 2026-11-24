# Run and publish a cluster experiment

## Resolve the exact run

Read the task and validation report. Require matching accepted task/image/
profile evidence, saved time budget and verified task/environment publication.
Reuse valid checks. Repairs invalidate only affected checks, but must pass
validation and be committed/pushed before the next formal attempt. Publish
their standalone validation logs separately. Keep Harness and canonical site
profiles read-only throughout.

Record the exact task/Harness paths, Git revisions and initial changes,
profile/resources, credential names/presence, expected duration, Agent/model,
timeout source, submission policy, run/log roots, repair/cleanup envelope,
publication user and existing remote/branch. Respect existing authorization;
resolve only missing fields. Do not invent a publication destination or silently
create a branch. Preserve unrelated local changes.

Use the read-only `preflight_task.py` plan and then inspect its exact command.
For Science, follow [Judge authentication](cluster-execution.md#science-judge-authentication);
include resolved Judge flags and inspect `runtime.judge_auth` before launch.
Defaults match the single-node runner:

| Agent | Model | Reasoning effort |
| --- | --- | --- |
| `codex` | `gpt-6-astra` | `max` |
| `claude-code` | `claude-opus-5-5` | `max` |

Explicit user choices override these defaults. For Claude, use long-lived
`CLAUDE_CODE_OAUTH_TOKEN` through `RSI_AGENT_EXTRA_ENV`; do not use
`--agent-auth local`. Credentials are copied at startup, not automatically
rotated. For Codex using a local login on a supported backend, pass
`--agent-auth local` to `preflight_task.py`; it forwards the choice to both
Harness commands. Leave it unset for API credentials. Kubernetes requires
exported credentials rather than local login. Harness's dry-run verifies the
selected auth route. Never print or copy secrets into task files, command
arguments, chat or logs.

No `--max-submissions` means the task's `max_submissions`, else unlimited. Add
it only for an explicit user cap; never inherit a README cap or use a cap as a
substitute for time. A cap above 1 rejects further submissions without itself
terminating the Agent; a budget of 1 is one final judge (Harness
`docs/harbor-task-authoring/task-toml.md#max_submissions`). User `--timeout` overrides `[agent].timeout_sec`; otherwise use the final
validated value. Missing both is a blocker. The Agent budget includes blocking
Judge time, not all image setup/queue/teardown time, and is an upper bound rather
than a guarantee of continuous activity. The planner uses the resolved timeout
in resource/walltime planning too.

Check required runtime templates with the bundled `check_runtime_env.py` in the
same environment as Harness, passing the planner's `--sandbox-policy` for a
sandbox task. Report missing names and phases only. Inspect
actual profile binaries and site paths; do not substitute local Docker flags.

## Publication preflight and launch

Use the login/controller host execution user that owns Harness and can read its
shared logs. Check that this user has Git identity and access to the confirmed
remote/branch, and that host credentials stay outside Work. The bundled
publisher respects repository-local identity before global identity. Do not
chown unreadable logs or switch users merely to bypass a permission problem.

Before launching, run a read-only publication preflight. Here the placeholder
paths may be used because the actual run has not been assigned yet:

```bash
python3 <skill-dir>/scripts/publish_cluster_logs.py preflight \
  --scheduler <lsf|slurm|kubernetes|pbs|pjm> \
  --repo <task-repository> --remote <confirmed-remote> --branch <confirmed-branch> \
  --run-dir <profile-logs-root>/runs/planned-run \
  --run-info <profile-run-root>/planned-run/RUN_INFO.json
```

This checks branch existence/read access and identity, not push permission.
Resolve failures before launch unless the user explicitly requested local-only.
Retain any task/validation publication evidence already obtained.

Run the resolved `commands.run` from the planner in an attached or supervised
host process. Keep its true process identity; `exec` a wrapper into Harness if
needed so the PID belongs to the actual Harness CLI, not a shell/tee/Agent/
batch-worker process. Keep full console output in files and provide concise
progress from durable status and logs. The selected scheduler manages the allocation through
Harness; do not detach only `bsub`/`sbatch` and discard the controller.
Where the controller must run on a compute node (see
[Restricted sites](cluster-execution.md#restricted-sites-and-bounded-allocations)),
one job runs `commands.run` and the watcher beside it with that host's Harness
PID; the node then needs the scheduler's status command and Git access. That
job's walltime covers queue waits plus the run (PBS/PJM `launch = "allocation"`:
see [Formal experiment](cluster-execution.md#formal-experiment)). A controller
job that ends (walltime, or the scheduler's cancel) cancels its run job;
continue with `rsi-harness resume RUN_ID --cluster PROFILE` from a new
controller job.

Once the **actual** run ID is bound to this invocation's job IDs and
`RUN_INFO.json` as described in [cluster-execution.md](cluster-execution.md),
start one separate managed host publisher process:

```bash
python3 <skill-dir>/scripts/publish_cluster_logs.py watch \
  --scheduler <lsf|slurm|kubernetes|pbs|pjm> \
  --repo <task-repository> --remote <confirmed-remote> --branch <confirmed-branch> \
  --run-dir <profile-logs-root>/runs/<actual-run-id> \
  --run-info <profile-run-root>/<actual-run-id>/RUN_INFO.json \
  --pid <actual-harness-cli-pid> --interval-seconds 1800 \
  --status-binary <profile-status-binary>
```

Use the exact profile binaries, including absolute paths when configured.
For Slurm add `--accounting-binary <profile-sacct>`; for LSF add
`--history-binary <site-bhist>` if `bhist` is not on PATH; for PBS and PJM the
status binary is the profile's `qstat` or `pjstat`; for Kubernetes it is the
profile's `kubectl`; add the plan's
`publication.kubectl_args` (`--namespace`, and `--kubeconfig`/`--context` when
set) to every publisher command, `preflight` included.
Pass additional credential variable **names** via repeatable `--secret-env`.
The helper checks configured actual secret values; it never dumps environment
variables. Review permitted artifacts before publication; secret detection is
not a reason to collect extra private state.

The bundled `publish_run_logs.py` and splitter are byte-identical to the
single-node runner. Its watch loop runs independently of Agent hooks, assistant
polls and context lifetime. It tracks Linux PID start time, ignores SIGHUP,
coalesces missed ticks, prevents duplicate watchers and attempts publication
every 30 minutes. A final-result file alone does not end monitoring while the
Harness PID remains alive. Keep the same user/state directory on restart.

Monitor publisher output and
`<repository>/.rsi-harness/log-publication/<run-id>/last-attempt.json` along with
Harness. Publication failure does not kill an otherwise useful experiment;
surface the blocker and retain all logs for retry. Do not start competing
publishers. For slow Git transfers raise `--transfer-timeout-seconds` (default
900 per fetch/push) rather than altering the Agent time budget.

## Run completion and recovery

Inspect durable `final_result.json`, submission reports, finite scalar reward,
`evolve_state.json`, Work/Judge cleanup and exact scheduler termination evidence. Shell exit
zero, an Agent exit, a checkpoint or a pushed commit alone is insufficient.
Report Agent status, scientific score and infrastructure failure separately.
A non-null `agent_provider.error` in `final_result.json` and an `Agent stopped:`
result line mark a stop by the model provider, not a task or Harness failure:
[resume](cluster-execution.md#planned-research-interruption-and-explicit-resume)
the run once the provider recovers. With `error` null, `retries` and
`wait_seconds` only record retries that succeeded.

Final upload waits for the full Harness process to exit with final artifacts.
Require a matching terminal `RUN_INFO.json` and termination evidence for every
build/run ID, following the [scheduler rules](cluster-execution.md#formal-experiment).
Failed allocations can publish final evidence without becoming successful runs;
missing or delayed accounting blocks finalization. The shared watcher retries
final publication at most three times, then reports a blocker.

After controller interruption without final artifacts, the watcher publishes
progress and returns nonzero. Inspect recovery and remote Judge writers; do
not label progress as final. Once all writers have stopped and the matching
manifest is terminal, finalize explicitly with the same state/user/destination:

```bash
python3 <skill-dir>/scripts/publish_cluster_logs.py once --final \
  --scheduler <lsf|slurm|kubernetes|pbs|pjm> \
  --repo <task-repository> --remote <confirmed-remote> --branch <confirmed-branch> \
  --run-dir <profile-logs-root>/runs/<actual-run-id> \
  --run-info <profile-run-root>/<actual-run-id>/RUN_INFO.json \
  --status-binary <profile-status-binary>
```

A blocked final attempt retains the logs and publication state; `once` without
`--final` can still publish progress. Never delete job IDs or fabricate final
artifacts to satisfy the gate. Preserve final evidence and record the verified
remote hash; if no upload succeeded say so explicitly.

## Artifact scope, splitting and Git behavior

External shared logs are projected into `logs/runs/<run-id>/` at the confirmed
remote, with stable paths across snapshots. Publish raw trajectory/prompt,
Agent console output, run metadata/final result, feedback, submission reports
and evaluator output/rewards. Do not publish caches, Work trees, model/data
assets, checkpoints, private controller state, credentials or unrelated runs.
The exact run manifest is used locally to verify allocation termination; it is
not automatically added to the public log scope.

The shared publisher snapshots readable logs, losslessly splits files over
80 MiB, records checksums/manifests and uses a private Git cache/index. It never
changes active checkout HEAD/index, captures local unpublished source changes,
force-pushes or rewrites remote history. It preserves unrelated remote updates,
blocks conflicting edits to the same run, verifies pushes and creates no empty
commits for unchanged snapshots. Preserve original oversized files locally.

For finalized validation evidence, use ordinary separate Git commits with the
same credential/permission checks. Run the bundled splitter's `split` command
on each oversized file, commit its entire parts directory including the
generated `.gitattributes`, and add an exact ignore entry for the retained
original. Use `restore` to verify byte-identical restoration before publishing:

```bash
python3 <skill-dir>/scripts/split_run_log.py split <large-log>
python3 <skill-dir>/scripts/split_run_log.py restore <large-log>.parts --output <restored-log>
```

Do not truncate, gzip or replace logs with Git LFS. The 80 MiB limit is per file,
not the total trajectory. Validation logs and validated source use separate
commits from the formal experiment's periodic/final log commits. Preserve
unrelated staged work for manual evidence commits; never use blanket staging.
An explicit local-only request skips pushes/watchers while retaining all local
validation and run evidence and recording the chosen publication policy.
