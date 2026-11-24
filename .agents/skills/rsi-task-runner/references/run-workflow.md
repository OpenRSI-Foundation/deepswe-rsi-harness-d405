# Local RSI-Harness run workflow

Use this procedure for one local Harbor task beside one RSI-Harness checkout.
RSI-Harness remains read-only; only task-local repair is permitted.

Resolve publication separately from permission to run. Science task repairs,
validation evidence, and run logs stay local unless the user explicitly
authorizes their publication. For other tasks, use the runner's confirmed
automatic-publication default; honor any local-only request. Apply that resolved
scope throughout this workflow. Local-only execution needs no publication
destination, Git credentials, publisher preflight, watcher, or final upload.

## Contents

- [Discover and bind the roots](#1-discover-and-bind-the-roots)
- [Inspect before mutation](#2-inspect-before-mutation)
- [Confirm the execution contract](#3-confirm-the-execution-contract)
- [Run and observe](#4-run-and-observe)
- [Diagnose and repair](#5-diagnose-and-repair)
- [Recovery and cleanup](#6-recovery-and-cleanup)
- [Publish the run logs](#7-publish-the-run-logs)

## 1. Discover and bind the roots

Resolve the supplied repository once. Identify the Harness by
`pyproject.toml` plus `src/rsi_harness/`. Identify the task outside that tree by
the complete `task.toml`, `instruction.md`, and `tests/test.sh` marker set.
Reject ambiguous discovery instead of choosing the first match.

Record:

- absolute repository, Harness, and task roots;
- Harness commit, branch, `git status --short`, and tracked diff;
- task Git status when the task is versioned;
- the task repository's branch, upstream remote, and existing staged changes;
- the executable selected for this run.

Prefer `<Harness>/.venv/bin/rsi-harness` when it exists. Otherwise use the
project's documented environment without installing into or editing
RSI-Harness. Run `rsi-harness run --help`, `recover --help`, and `cleanup
--help` from that exact checkout; do not rely on remembered flags.

## 2. Inspect before mutation

Read the task's instruction, `task.toml`, README run command, Compose/Dockerfile
inputs, and `tests/test.sh`. Carry the README's `--primary-reward` and
`--score-direction` into the exact command; the Harness otherwise scores as
`maximize`. Science uses maximize for rubric-count scoring. Before any Docker or GPU mutation, run:

```bash
python3 <skill-dir>/scripts/check_runtime_env.py <absolute-task-directory> \
  [--sandbox-policy <reviewed policy>]
```

The check resolves required `${NAME}` templates from `[environment.env]` and
the effective `[verifier.env]` overlay. A `${NAME:-default}` template is ready
without a host value. It reports names and affected phases only; never inspect,
print, persist, or ask the user to paste a value.

With a sandbox table in `task.toml`, the check also requires
`--sandbox-policy`. The user reviews the task's proposed `operator-policy.toml`
(its header lists what to check) or supplies their own; pass the same file to
`rsi-harness run`.

If the check reports missing variables, stop. Tell the user which names must be
configured in the host shell used to launch RSI-Harness, explain that `sudo -E`
must preserve them for a root launch, and wait for the user to say the
configuration is complete. Do not start a build, allocate GPUs, change the
task, or substitute a different provider. Re-run the same check after the user
responds and again immediately before launch in the exact launch environment.

After the runtime-variable check passes, check Docker reachability, free disk,
local Agent authentication, and the selected backend's firewall authority.
Linux runs as root or uses the bundled Harness's README section "Run without
root": the same commands without `sudo -E`, for a user with Docker access,
Docker Engine 26 or later and no sandbox table. Native macOS Docker Desktop
runs as the Mac user, without sudo, using the Harness's trusted Linux-daemon
helper.

For macOS, follow [the shared Mac capability and validation procedure](macos-docker-desktop.md)
and require matching task/environment/credential acceptance from validation.
If an upgrade is needed, return to the validator. Do not use a runner launch to
substitute for missing environment, isolation, capacity or Judge acceptance.

For Science, the Science Mac acceptance reference also governs this workflow.

Resolve the Agent, model, effort, and credential per `SKILL.md` "Agents"
before the user confirms.

Read Work `[environment].gpus` and Judge
`[metadata.rsi_harness.verifier].gpus` independently. When both are zero, record
GPU selectors as `not required`, omit `--gpus`, and skip `nvidia-smi`, GPU
availability, and NVIDIA runtime checks. If either count is positive, check
`nvidia-smi`, the NVIDIA container runtime, and availability of the requested
GPU pool. With GPU Work, use explicit or confirmed automatic pool selection.
For Work=0/Judge>0, supply an explicit `--gpus` pool; automatic selection is
unavailable. `--gpus 0` selects physical GPU index 0.

Do not use a local cluster or Blue Vela adapter. Do not call Harbor directly;
the RSI-Harness CLI owns task parsing and execution.

Resolve the run budgets:

- A user-supplied CLI `--timeout` overrides `[agent].timeout_sec`; otherwise use
  the task value, including the final total budget saved by validation, not a
  single-round or Judge duration from its report. When validation timings are
  available, explain any reduction in projected loop capacity from an override.
- If both are absent, stop and ask the user for an Agent time budget. Never
  silently accept the current Harness's 60-second fallback.
- Resolve the submission budget per `SKILL.md`.
- `[verifier].timeout_sec` remains task-owned. It is a per-submission Judge
  timeout, not a run-time choice or the Agent time budget.


On Linux, if `sudo -n true` and the required non-mutating authority probes succeed, the
agent may launch the confirmed command as root. Otherwise, when the non-root
mode above applies, the agent launches it without `sudo -E`. Only when neither
applies, print one shell-safe `sudo -E ...` command for the user and wait for
the result; never request a password.

## 3. Confirm the execution contract

Before a build or run, show the confirmation card from `SKILL.md`. Translate
seconds into a human duration and identify each value's source. State plainly:

- when the Agent will be terminated;
- the resolved submission budget, its source, and whether it stops the Agent
  (only a budget of 1 does, per `SKILL.md`);
- that setup and teardown can extend total command duration;
- where retained state and run artifacts will be written;
- whether artifacts stay local (the Science default), or publication is
  authorized for the following artifacts and destination;
- when run-log publication is enabled, logs will be committed and pushed to the displayed task
  repository remote/branch every 30 minutes and once after completion, with
  lossless 80 MiB parts for large files;
- when task-repair publication is enabled, validated repairs will be committed and pushed separately
  after their affected validation passes, before launching the next run; and
- when validation-log publication is enabled, those logs will be published in their own
  commit, separate from task changes and formal run logs.

Only when publication is enabled, resolve a missing or ambiguous destination
instead of inventing a remote or choosing a different repository. Authorization
to publish a proposal or task does not also authorize publishing its run logs.

List required task runtime variable names and `present` status in the card.
Never include values. If any required variable is missing, do not present the
run as ready for confirmation.

Require separate explicit confirmation for this resolved card. A vague earlier
request to "run the task" is not confirmation of previously undisclosed
budgets. Do not ask the user to choose a submission cap when no finite cap was
requested; present the resolved budget for confirmation.

## 4. Run and observe

For automatic publication, use the same host execution user as Harness: the
normal user for ordinary runs, **root for root/sudo runs**, whose verifier
round directories are private (`0700`). Run `preflight`, `watch`, and
`once --final` consistently as that user. From a normal shell, prefix all three
commands below with `sudo -n -E` for root publication; an existing root shell
needs no prefix. If noninteractive sudo is unavailable, provide the exact
interactive command for the user to run; never request a password.

For automatic publication, check the confirmed destination in that execution environment before launching
Harness. This read-only command needs no run artifacts; `preflight` below is
only a placeholder directory name and is not created:

```bash
python3 <skill-dir>/scripts/publish_run_logs.py preflight \
  --repo <absolute-repository> --run-dir <absolute-logs-root>/runs/preflight \
  --remote <confirmed-remote> --branch <confirmed-branch>
```

A missing branch is reported separately from remote access failures. Resolve
the destination before launch; do not automatically create a branch or choose
a base. This checks branch existence/read access, not permission to push.
The watcher repeats the check on startup, before its first 30-minute interval.

Keep runtime state outside RSI-Harness. Unless the user selected external
locations, use `<repository>/.rsi-harness` and `<repository>/logs`. Pass both as
absolute `--data-root` and `--logs-root` arguments so the result does not depend
on the shell's current directory. Preserve other Harness defaults unless the
task or user requires an override; beyond the README's scoring flags, do not
add `--primary-reward`, `--disable-stop-hook`, cooldown, or destructive flags
by habit.

Treat
`<repository>/logs/runs/<run-id>/<task-id>/agent_output.txt` as the raw
trajectory. Keep it with `run_agent.log`, `final_result.json`, submission
reports, and Judge feedback under the repository log root. Do not create a
second trajectory copy for monitoring. The publication step may split an
oversized file while retaining the local original. Report the trajectory path
as soon as the Run ID is known.

Keep the original process attached. If your session cannot outlive the run,
start it instead with `setsid nohup <command> > <logs-root>/console-<timestamp>.log
2>&1 &`, use that PID as the Harness CLI PID, and follow the console log.
Report the Run ID and resolved log path as
soon as they appear. During a long image build or Agent phase, provide concise
status based on process and Docker evidence rather than claiming it is healthy
from silence alone.

For automatic publication, start this helper in a separate managed host process
as soon as the Run ID is known; keep it running alongside the attached Harness:

```bash
python3 <skill-dir>/scripts/publish_run_logs.py watch \
  --repo <absolute-repository> --run-dir <absolute-logs-root>/runs/<run-id> \
  --remote <confirmed-remote> --branch <confirmed-branch> \
  --pid <actual-host-Harness-CLI-PID>
```

Use the **whole run directory** and the actual Harness CLI PID, not the Agent,
container, sudo wrapper, or monitoring shell PID. The helper checks kernel PID start
time on Linux or macOS, attempts publication every 1800 seconds, and outlives Agent exit
while Harness drains Judge. Slow transfers do not overlap; missed ticks are
coalesced. Do not implement the timer through Agent hooks or
the supervising model remembering to poll. Local-only mode skips the helper.
For automatic publication, confirm the effective Git identity and authentication for the selected
publication user. Repository-local `user.name`/`user.email` take precedence;
falling back to that user's global Git configuration is allowed. Missing either
effective value blocks startup. Root may have different global settings and
credentials from the caller; check them under the same root/sudo environment
used for publication, without copying secrets into commands. Keep
publication credentials on the host, outside Work. Pass additional required
credential variable names via `--secret-env NAME`, never values. The helper
blocks a snapshot only when it contains the exact value of a secret-named host
variable or a `--secret-env` variable; it does not pattern-match credential
shapes, so Harness redaction markers never block publication. Scanning is a
safety check, not proof that arbitrary task output is safe to disclose. Review the
publication scope before launch. Do not dump the environment to inspect it.

Monitor the helper's output and
`<repository>/.rsi-harness/log-publication/<run-id>/last-attempt.json` alongside
run status. A failed upload does not stop training: logs stay local and the next
interval retries. Report an exited helper, credential/permission problem, or
remote log conflict promptly; resolve it before restarting the same command.
Do not run duplicate publishers. Keep the same publication user and private
state directory on retry, and use one publication user for the repository's
shared cache; do not silently alternate root and non-root cache writers.
For unusually large/slow transfers, increase the helper's
`--transfer-timeout-seconds` (900 seconds per fetch/push by default); this does
not change the Agent time budget.

At termination, inspect the durable `final_result.json`, submission reports,
lease/recovery state, and console summary. A zero shell status is not sufficient:
`no_valid_submission` is a distinct unsuccessful task outcome even when the
CLI itself exits successfully.

## 5. Diagnose and repair

First classify the owner using logs and durable artifacts:

- task packaging or compatibility;
- Agent solution or ordinary verifier feedback;
- host/Docker/GPU/infrastructure;
- Harness defect.

Automatically repair only minimal, evidence-backed task-local execution or
compatibility defects that preserve task semantics. Examples include local
Dockerfile/Compose packaging, missing runtime dependencies, path corrections,
permissions or executable bits, `shm_size`, task timeouts, supported field
formatting, and obvious RSI-Harness compatibility.

Require separate approval before changing any instruction, candidate or
editable surface, data or baseline, Verifier logic, scoring or reward,
declared GPU counts, network policy, submission policy, or research question.
Treat uncertainty as semantic and ask.

If evidence indicates a Harness defect, stop and report the reproducer,
artifacts, and likely boundary. Do not patch RSI-Harness. After any permitted
task repair, rerun only the affected preparation/run path and disclose the
task diff before execution.

### Publish validated task repairs

Apply this section only to artifacts covered by the resolved publication scope.
Otherwise retain the validated task diff and evidence locally, report their
paths/version, and continue the authorized workflow without requiring a push.

Once the affected validation passes, commit and push approved task-local
repairs in a dedicated task commit, separate from run logs, before launching
the next run. If validation needs a real run, publish after that run establishes
the repair works; do not claim a repair is validated before observing evidence.
This also applies to validated repairs handed over from an earlier validation
stage: review their diff and validation evidence and confirm their publication
scope before including them. Do not rerun an unrelated full validation suite.
After the validation writers stop, publish associated standalone validation
logs, including baseline acceptance logs, in a separate validation-log commit
after the task commit. Keep them under
`<repository>/validation/<YYYYMMDD>-<label>/`, not the formal run directory.
Apply section 7's secret/permission checks, lossless large-log splitting, and
remote verification to this exact validation directory. If the validator
already published it, verify and record that commit rather than duplicating it.

Review the exact task diff for secrets and include only approved task files.
Keep RSI-Harness, logs, checkpoints, caches, and unrelated user changes out of
this commit, including unrelated files already staged. Preserve those changes.
Use the confirmed remote/branch without force-pushing or rewriting history;
verify it contains the task commit and record its hash with this run's notes.
If there are no task changes, do not create an empty task commit. Honor an
explicit local-only request and report the unpublished task version. If checks
fail or publication is blocked, retain the changes and report the blocker;
do not claim publication succeeded or silently launch another run with an
unpublished repair. Ask whether to resolve the blocker or proceed local-only.

## 6. Recovery and cleanup

Normal runs clean up their transient resources. Use `recover RUN_ID` only after
an interruption, host restart, infrastructure failure, or durable
`recovery_required` state. Preserve the same data/log roots and privilege
boundary used by the original run.

Run ordinary `cleanup RUN_ID` only when requested. Never pass
`--delete-workspace --yes` without fresh explicit confirmation naming the exact
Run ID and retained state being destroyed. Do not delete logs automatically.

Runs never remove images their sandboxes pulled. For a sandbox task, report
them as retained state; `rsi-harness sandbox prune-images --dry-run` lists the
ones sandboxes first brought to this host, and pruning runs only when
requested.

Before reporting completion, verify that RSI-Harness Git status and tracked
diff match the initial record. Report every task-local change, final status,
submission count, best score, log location, retained state, and recovery need.

## 7. Publish the run logs

Skip this section for local-only run logs, including Science runs without
explicit log-publication authorization. Report the retained local paths.

Publication runs during execution and at completion, including failed or
timed-out runs; uploading evidence does not make an experiment successful.
The helper snapshots already written bytes without stopping writers. Each
snapshot replaces the same remote `logs/runs/<run-id>/` paths, not a new dated
copy. Final publication waits for the whole Harness process to exit with final
artifacts; Agent exit or a final-result file alone does not end monitoring.
After an interrupted run without final artifacts, check recovery and active
Judge writers first. Once they have stopped, retry/finalize with:

```bash
python3 <skill-dir>/scripts/publish_run_logs.py once --final \
  --repo <absolute-repository> --run-dir <absolute-logs-root>/runs/<run-id> \
  --remote <confirmed-remote> --branch <confirmed-branch>
```

The initial confirmation covers periodic uploads and final retries. The watcher
retries final upload at most three times, then reports it blocked; retain logs
and publication state for a later explicit retry. Never report an upload as
successful from a local commit alone.

This run-log commit covers the actual RSI experiment run. Standalone validation
and baseline-acceptance logs are published separately as described in section 5;
keep the actual run's submission, Judge feedback, and verifier logs included.

The helper publishes the raw trajectory, prompt, run metadata/final result,
completed submission reports, captured Judge output (`feedback/*.log` and
`submissions/*/test_output.txt`), the durable per-submission
`verifier/*/reward.json`, plus run-root `launch.log`/`console.log` when
present. It excludes verifier scratch trees, dot-temporaries, model/data files,
runtime state and unrelated runs. Completed Judge output appears only after the
Harness has durably published it. Inspect any task-specific evidence outside
this layout and publish reviewed extras separately after its writers stop;
never silently claim the helper included them. External log roots are supported
as read-only sources; remote paths remain `logs/runs/<run-id>/`.

Before staging, check the exact run files for credentials and unreadable paths.
Do not publish secrets or silently omit inaccessible evidence. Read sudo-owned
logs with the root publisher described in section 4; do not automatically
chmod/chown verifier directories or drop `reward.json` to make an upload pass.
If access still fails, preserve the logs and report the blocker. Keep checkpoints, datasets,
runtime state, caches, and unrelated runs out of the log commit.

For formal runs, the publisher automatically copies a bounded log prefix to a
private snapshot, verifies it, and uses the existing splitter/restore check for
files larger than 80 MiB. No oversized original enters a commit, even when a
previously small log grows across the threshold. Local originals and existing
local `.parts` directories remain untouched; fresh snapshot parts replace remote
parts, so only changed Git objects need uploading. The 80 MiB cap is per file,
not a cap on the complete trajectory or push. Readers restore split logs with
the command below.

For separate finalized validation evidence, use ordinary Git with the same
secret/permission checks. Split files larger than 80 MiB using:

```bash
python3 <skill-dir>/scripts/split_run_log.py split <absolute-log-file>
```

It preserves the original and creates `<log-file>.parts/` with ordered chunks
of at most 80 MiB and a manifest containing byte counts and SHA-256 checksums.
Commit the whole parts directory, including the generated `.gitattributes`
that prevents Git newline conversion, not the oversized original. Add an
exact-path rule to a run-local `.gitignore` so a later `git add` cannot
accidentally stage the original; do not add a blanket ignore for logs. Record
this reconstruction command in a short run note, using a new output path:

```bash
python3 <skill-dir>/scripts/split_run_log.py restore <log-file>.parts --output <restored-log-file>
```

Verify the restored file matches the original before publication. Splitting
must preserve every byte; concatenate in manifest order, never summarize or
drop tool output. Readers needing a single trajectory, including a visualizer,
must restore it first. Leave an existing parts directory untouched; if it
exists, verify it against the source before reusing it.

The periodic publisher shares one private Git object cache per repository and
push URL under `<git-common-dir>/rsi-log-publication/`. The first fetch still
needs the destination history; later runs reuse it rather than storing another
full copy. Each run keeps its own index, locks and state under
`.rsi-harness/log-publication/<run-id>/`, with isolated fetch/retry references
inside the cache. Existing per-run caches are imported as needed, not deleted.
After a verified final upload, it attempts one locked, time-bounded repack per
final commit, preserving all objects. Busy-cache or compaction failures are
warnings, not upload failures; `once --final` can retry them. On upgrade, stop
old publishers before starting updated ones so all writers use the cache lock.
It never stages files or changes HEAD in the running repository, never includes
local unpushed code, and never force-pushes. Unrelated remote changes are preserved;
changes to this same run's remote logs block publication for review. Unchanged
snapshots create no empty commits. Each push is verified against the remote.
The local branch may consequently be behind; do not automatically pull/rebase
the active checkout. Report the final remote commit and leave synchronization
to normal repository handling. For manual validation/extra-evidence commits,
likewise isolate the index and include only reviewed paths, not unrelated staged
changes. Never use blanket `git add .`, publish secrets, or switch destinations
to work around a blocked upload.
