# Execution validation

This reference defines the seven validation steps for one complete
RSI-Harness Harbor task. Readiness requires the Environment and final Judge
checks plus the step-5 judgments. Task repairs require approval of the initial
envelope; RSI-Harness and unrelated repositories remain out of scope, except
the bounded compatibility refresh at intake described below.

## Science execution overrides

Follow the Science execution and authorization overrides in `../SKILL.md`.
For a model-access Science task in either Judge visibility mode, its
Science execution-validation reference governs acceptance.

## Shared rules

- Treat the task, image, candidate workspace, Solution, and evaluator as
  untrusted.
- Preserve the task's declared Judge network contract. `no-network` is the
  default; an explicit `allowlist` or `public` policy is valid when the fixed
  evaluation requires it. Do not broaden, narrow, or silently rewrite it during
  validation.
- Use collision-free names. Never overwrite or reuse pre-existing Docker
  objects, run directories, or outputs without explicit authorization.
- Keep publishable evidence in `<repository>/validation/<YYYYMMDD>-<label>/`:
  commands, planner/build logs, dry-run reports, smoke/calibration/acceptance
  stdout/stderr, reward copies, timings, and the projection. Write complete
  output to files; use short excerpts only in conversation.
- Keep disposable smoke tests, candidate copies, checkpoints, and caches in a
  separately approved `<scratch-dir>` outside the evidence, task, and Harness
  directories. Record its path; if it is inside the repository, add an
  exact-path ignore rule. Scratch state is never part of the log commit.
- Initial authorization covers all seven steps, task-local repairs and reruns
  within the disclosed envelope, step-5 task changes under the two judgments,
  and cleanup of superseded resources created by this validation run. It does
  not authorize deleting pre-existing or final retained resources.
- Never invent a baseline score, runtime, or successful result.

### Existing-task compatibility refresh

Read [the shared intake refresh procedure](compatibility-refresh.md) when the
bundled runtime or installed Skills lack a required capability. It is a bounded
validator operation, not permission to regenerate the task or upgrade a live run.

### Native macOS Docker Desktop

Read [the native Mac capability and validation procedure](macos-docker-desktop.md)
before planning or executing on a Mac. Its limits, capacity evidence and
credential acceptance apply to both validation and running.

### Oracle runs

Smoke, calibration, and acceptance Judges run the task on the production path
of the task repository's bundled RSI-Harness, with the task's
`solution/solve.sh` as the Agent:

Omit `sudo -E` from run and cleanup commands on the supported Mac backend
(follow the native Mac procedure above) and for a Linux run without root.
Public model-access Science also follows its Science execution reference for
scientific acceptance. Linux uses the command below.

```bash
sudo -E <harness>/.venv/bin/rsi-harness run /absolute/path/to/task \
  --agent oracle [--gpus <approved pool>] [--sandbox-policy <reviewed policy>] \
  --data-root <scratch-dir>/harness-data --logs-root <scratch-dir>/harness-logs
```

`<harness>` is the bundled Harness; `uv sync --frozen` there creates its
`.venv`. It must provide the oracle (its README has "Validate a task's Judge
with the oracle") and `rsi-isolate` (`src/rsi_harness/judge_agent/rsi-isolate`).
If it does not, use **Existing-task compatibility refresh** above. Pin and
verify the source before refreshing; include the validated change in the task
commit. Do not blindly overwrite a task's patched or running Harness.

The oracle copies `solution/` to `/solution` in Work, runs `solve.sh` in
WORKDIR as the Work user, deletes `/solution`, and submits once. Images,
firewall, GPU plan, sandbox grant, `rsi-isolate`, and reward are those of an
Agent run, so the Judge's declared user, network, resources, timeout, and
read-only `/tests` need no hand setup.

- On Linux, run as root when `sudo -n` works. Otherwise use the bundled
  Harness's README section "Run without root": the same commands without
  `sudo -E`, for a user with Docker access, Docker Engine 26 or later and no
  sandbox table; its results belong to that user. Only when neither applies,
  give the user the exact `sudo -E` command and continue from its output;
  never request a sudo password. After a root run, copying the root-owned
  results and removing superseded scratch roots also need root: include them
  in that command, or run them with `sudo -n`, then `chown` the copies to the
  validator user. Recheck an earlier `BLOCKED` for missing sudo against this
  rule.
- Omit `--gpus` when Work and Judge both declare zero GPUs. Otherwise pass the
  approved pool; it also serves Work's declared count, which the oracle
  allocates although `solve.sh` does not use it.
- Pass `--sandbox-policy` only with a sandbox table, naming the policy approved
  at intake. Pull the approved pre-pull images by digest before the first run.
- Omit `--max-submissions` and `--cooldown`. Omit `--timeout` unless
  `[agent].timeout_sec` is shorter than the solve time plus
  `[verifier].timeout_sec`.

Exit 0 means only that `solve.sh` exited 0 and one round ran with status
`completed`; otherwise the CLI prints `Oracle check failed: <reasons>` and
exits 1. Read the result under `<logs-root>/runs/<run-id>/<task-id>/`:

- `submissions/agent-1/report.json`: the round's `status`, `score`,
  `exit_code` of `test.sh`, `runtime_seconds` (snapshot, Judge start,
  `test.sh`, and reward), and `error`;
- `submissions/agent-1/test_output.txt` and `verifier/agent-1/reward.json`:
  the Judge's output and reward;
- `final_result.json`: `best_score`, `agent_exit_code` (`solve.sh`'s),
  `agent_runtime_seconds`, and `first_submission_seconds`;
- `agent_output.txt`: `solve.sh` and `rsi-submit` output; and
- `engine_error.json`: present only after an infrastructure failure.

The Harness builds a task Dockerfile again as `rsi-harness-base:<digest>`
with Docker's classic builder, sharing no cache with step 2. A `solve.sh` or
Judge failure is a task defect to repair, as is a Base build failure or setup
refusal the task causes (for example BuildKit-only Dockerfile syntax such as
`RUN --mount`). Any other host, Docker, or Harness failure is `BLOCKED`,
including zero rounds with `rsi-submit exited` in `agent_output.txt` and any
other CLI `Error:` line.

Copy `final_result.json`, `run-plan.json`, `agent_output.txt`, and the round's
`report.json`, `test_output.txt`, and `reward.json` (root-owned after a root
run) into the step's evidence directory; the roots stay in scratch. Then remove the run's
retained Work rootfs and workspace:

```bash
sudo -E <harness>/.venv/bin/rsi-harness cleanup <run-id> --delete-workspace --yes \
  --data-root <scratch-dir>/harness-data --logs-root <scratch-dir>/harness-logs
```

### Repair and revalidation

Repair reproduced task defects within the approved envelope; step 5 also
permits the listed protocol adjustments. Preserve unrelated user changes and
keep integrity and failure-detection checks intact.

A Judge that isolates candidate code by switching users itself (`setuid`,
`setgid`, or `setgroups` calls, `su`, `runuser`, `setpriv`, `chroot`, or
`chown` of its files to the isolated identity) works only as root and crashes
on a cluster, where Judge is not root. Treat it as a task defect found at
intake, even though a root Judge passes locally, and include its repair in the
step-1 envelope. Migrate that code to RSI-Harness's `rsi-isolate`, following
the `rsi-isolate` section of the bundled Harness's
`docs/harbor-task-authoring/task-toml.md`:

- grant only what the isolated code uses: `--read` its trusted modules,
  inputs, and candidate files, and `--write` its scratch. Do not grant all of
  `/tests` or other hidden inputs merely because the old identity could read
  them;
- keep its network policy, timeout, and environment; and
- remove the Judge's `chown` to the isolated identity, and stop a call with
  `SIGTERM`, not `SIGKILL`.

Then validate as usual.

After any repair or adjustment:

- Re-run syntax checks and RSI-Harness compilation for changed task code or
  configuration. Rebuild only when image inputs changed, then recheck step 2.
- Repeat only affected dry-run checks (step 3) and smoke paths (step 4).
  Runtime, workload, or compute-resource changes require remeasuring the
  affected costs. A timeout-only adjustment using existing timings requires
  recompilation and recalculating step 5, not another dry-run or smoke.
- Refresh any affected scratch copy from the repaired task. Keep unaffected
  evidence, recompute the judgments, and apply step 6's final-version
  acceptance/reuse rule. Do not restart the whole workflow by default.

## 1. Intake and envelope

Read the full task before running task code: `task.toml`, the Environment
(Dockerfile, compose, requirements, staged assets), `tests/`, `solution/`,
`instruction.md`, `README.md`, and `operator-policy.toml` when present. Note
the fixed workload constants (epochs, steps, samples, evaluation episodes),
the declared GPU counts for Work and Judge, the timeouts, and whether
producing a candidate requires Work-side compute. A missing or non-regular
`solution/solve.sh` is a task defect found at intake: repair it within the
envelope (a no-op or restore baseline) or report `FAIL`.

Check for a task-owned `OVER_BUDGET.flag` beside `task.toml`, recording a
contributor-confirmed proposal estimate of fewer than 10 loops in 48 hours.
Include that exception and its actual total budget in the initial approval;
the marker alone does not authorize resources. Otherwise plan 24 hours by
default, with normal extension up to 48 hours. These are research-run budgets,
not a deadline for the entire build/validation workflow.

Calculate peak Docker headroom from evidence rather than a round guess:

1. inspect the local or registry-reported uncompressed base-image size;
2. total declared model, dataset, checkpoint, source, package, and build-context
   assets from manifests or authoritative remote metadata;
3. include download/extraction duplication, temporary build layers and caches,
   the final image, the Harness's own Base image (a second full build of the
   same Dockerfile, also counted in build time), its Work image (and Judge
   snapshot when `clean_image = false` or WORKDIR is `/`), one retained Work
   rootfs per oracle run until its cleanup, sandbox child images, the smoke
   scratch copy of the task, inspection state, smoke and baseline logs, and
   one repair rebuild when plausible; and
4. state the calculation, uncertainty, safety margin, Docker data root, and
   current free space.

Also disclose build/pull hosts and unresolved endpoints, runtime network modes,
credentials or licenses, CPU/memory/shm needs, and the build timeout. For each
planned framework probe, Work-side smoke, and Judge phase, state its devices
(zero GPUs is valid), timeout, and expected duration. Name the evidence/scratch
paths and Docker resources, and whether the bundled Harness needs a refresh.
With a sandbox table, name the policy for `--sandbox-policy`: the task's
`operator-policy.toml` after reviewing what its header lists, or the
operator's own, plus the images to pre-pull. Approval must
cover all seven steps, task-local repairs and step-5 protocol adjustments,
validator-owned intermediate cleanup, retained state, and the final task and
validation-log commits/push.

Run only the read-only planner in this response:

```bash
python3 <skill-dir>/scripts/preflight_task.py /absolute/path/to/task \
  --required-free-gb <calculated-peak-headroom>
```

Reuse existing authorization for the complete envelope. Ask only for missing
choices or an expanded scope; do not repeat an already resolved approval.

### Select the execution target before planning a build

Read existing proposal/session decisions first. Summarize Work and Judge CPU,
RAM and GPU requirements, their peak combined residency, storage needs and
known time estimates. Container limits are caps, not measured consumption;
report insufficient capacity for the declared envelope separately from an
observed runtime failure. Paused Work may retain memory.

If no validation location is confirmed, ask one focused question:

> Where should this task be validated: local Docker, an SSH server, or a
> supported cluster backend? Provide a host alias or an existing cluster profile,
> or say that no compute is available yet. I will check it and prepare the jobs.

Reuse an already selected target and resource limits without asking again.
Do not infer permission to use another accessible machine. If no resources are
available, report the missing prerequisite and keep execution pending.

Inspect the chosen target read-only: actual CPU/RAM/GPU capacity, disk space
and quota, container/build tools, access permissions and required authentication
(presence only, never credential values). For SSH, resolve the remote workspace;
for a cluster, resolve partition/account, scheduler limits, shared storage and
compute-node requirements from an existing profile or site configuration. Ask
only for settings that cannot be established from authorized context. A login
node check is not evidence of compute-node capacity or isolation.

Choose the procedure for that target before mutation:

- Native macOS Docker Desktop: follow the native Mac procedure above; public
  model-access Science also uses its Science execution reference. The planner
  can explicitly measure daemon backing-store capacity with a trusted cached
  probe image and `--acknowledge-authorized`. Its default stays read-only.
- Local or remote Linux Docker: run the bundled planner on the Docker host.
  Docker Desktop/remote daemon paths may be inside a VM or another host;
  measure disk capacity there, not at a same-named client path. If the helper
  cannot inspect that filesystem, record the limitation and obtain equivalent
  host-side evidence; do not report its preflight as passed.
- LSF, Slurm, Kubernetes, PBS or PJM: use `cluster-harbor-task-validator` with the
  selected Harness and site profile. Its transport and acceptance procedure governs; the Docker
  helpers do not validate a cluster. Keep unmet checks pending and report a
  missing capability rather than substituting a Docker pass. Build and compute
  checks run through the scheduler, not on a login node.

The Agent prepares commands/job scripts and internal timeouts. The contributor
chooses the execution location and total resource/cost limits, not every job
flag. Record the validation wall-time/cost allowance separately from the future
research budget; reuse an existing allowance or propose one from the checks.
Do not turn the research timeout into permission to spend that much validating.
If resources are insufficient, offer another target or explicitly limited
validation; do not silently shrink the task or mark partial checks EXECUTION READY.

## 2. Environment acceptance (gate)

Execute the approved preflight:

```bash
python3 <skill-dir>/scripts/preflight_task.py /absolute/path/to/task \
  --required-free-gb <same-approved-headroom> \
  --execute --acknowledge-authorized
```

The preflight must:

- fail before mutation when Docker free space is below the approved headroom;
- build the task Dockerfile or pull exactly the approved image;
- reject image-declared volumes that break Harness snapshot ownership;
- create a private internal bridge and one untouched inspection container
  without requesting GPUs or launching a GPU workload;
- mount task-owned `tests/` read-only and honor the effective absolute WORKDIR,
  user, shared environment, and Compose shm settings; and
- retain the image, container, and bridge for Agent-led inspection.

Inside that fresh container, perform task-specific, read-only diagnostics.
Exercise the public pre-scoring starting-state and editable-scope gates without
running the evaluator or importing candidate-controlled code. Confirm that the
untouched post-build workspace, dependencies, assets, ignored/untracked install
products, generated metadata, compiled caches, `.egg-info`, and logs are
accepted. A Git commit alone is not starting-state evidence.

GPU device files may remain visible because of an image or host default
runtime. Inherited device visibility is informational, not a gate failure.
Step 2 must not request or reserve GPUs, launch GPU processes, or materially
consume GPU memory.

Step 2 passes only when the image and untouched starting state satisfy every
applicable check. A build failure is a task defect: repair the Environment
(build backend, missing system library, unpinned dependency, install layout)
and rebuild.

## 3. Runtime dry-run

Find dependency, layout, and framework failures before expensive evaluation.
Use the step-2 image without the evaluator, training, Solution, or reward path.
Ordinary import/library/preflight checks do not request GPU work. Imports that
require GPU or framework initialization belong in the conditional launch
probe below instead.

Run the bundled diagnostic against the runtime entry points and supporting
Python sources. A source directory is scanned recursively, excluding nested
virtualenvs and caches; development tests may introduce dependencies not used
by the verifier. Use the task's actual Python interpreter and environment
(mount `tests/` read-only; public tooling is already in the image):

```bash
docker run --name <dryrun-name> --network none \
  -v /absolute/path/to/task/tests:/tests:ro \
  -v <skill-dir>/scripts/runtime_dryrun.py:/tmp/runtime_dryrun.py:ro \
  <image> <task-python> -I /tmp/runtime_dryrun.py --sources /tests <public-tool-dirs...> \
  --ldd-roots <site-packages> <other-lib-roots...> \
  [--import-path <source-roots used by the real launcher>] \
  [--ignore-modules <modules only importable after a framework launch>] \
  --report /tmp/dryrun.json
docker cp <dryrun-name>:/tmp/dryrun.json <validation-dir>/dryrun.json
docker rm <dryrun-name>
```

The report is copied out, not written through a host bind: container root
cannot write a root-squashed home.

The report separates evidence from uncertainty:

- Ordinary top-level external imports are tried in isolated subprocesses,
  including the requested submodule or `from ... import ...` symbol. Relative,
  source-local, conditional, type-checking and delayed imports are inventoried
  with source locations and deferred to real startup. Common explicit dynamic
  import calls are recorded, not evaluated. This is not a complete call graph.
- `--import-path` supplies known launcher search roots; it does not execute
  bootstrap code or reproduce arbitrary framework initialization. Use
  `--ignore-modules` to defer framework-owned imports (exact names and their
  descendants, no wildcards). Deferred imports remain visible in the report.
- `ldd` checks ELF shared objects matching the interpreter's ABI. Non-ELF files
  and foreign-architecture objects are recorded as skipped. Missing-library
  groups prioritize investigation; they do not establish that a task uses a
  library or that it is safe to omit. If a same-named native ELF candidate was
  found during the scan, `found_under_scanned_roots` records its candidate
  paths and referencing objects (`needed_by`), marked `loader path unverified`.
  These entries are counted separately from the missing-library groups, not
  hidden or considered resolved: file presence does not prove loader access.

Import/library findings are **advisory**, not automatic task defects. Exit 0
means the diagnostic scan completed, not that the environment or task passed.
Missing/empty inputs, unreadable files, syntax errors, unavailable tools and
timeouts produce an incomplete scan with a nonzero exit; fix the invocation
or record the check limitation and obtain evidence from the real runtime path.
Do not label an incomplete check as completed.

Confirm relevant findings using the task's interpreter, working directory,
environment and launcher. A failing isolated import does not justify changing
a working task. Existing preflight/launch probes and the mandatory Smoke and
Full Judge runs establish actual runtime validity. If no standalone preflight
exists, use those Judge runs; do not require a new task interface or invent an
unsafe generic bootstrap. A successful scan never replaces them.

Then, still without the evaluator:

- run only the evaluator's preflight/bootstrap stage (candidate scope, pinned
  source revisions, package identity, byte checks, asset and reference
  manifests) when the task exposes it as a callable module, and fix any check
  that cannot pass on the untouched image;
- when framework initialization is needed to check the task's runtime path,
  launch it once headless with the task's launcher, then shut it down without
  training. Use the approved devices for that path: CPU-only tasks use no GPU;
  GPU paths use their required count, not a blanket one-GPU default. If this
  needs resources outside the envelope, stop for approval;
- consult [known-pitfalls.md](known-pitfalls.md) for a matching symptom or
  configuration. Confirm the cause before applying a fix; framework presence
  alone does not justify a task change.

Record findings and use the shared repair/revalidation rule above.

## 4. Smoke Judge

Purpose: exercise the complete Solution and evaluator path — `solve.sh`,
submission, evaluator preflight, training or computation, evaluation, reward
write — in minutes, so that every path defect is fixed before the full run.

Method:

1. Read the evaluator and identify its fixed workload constants (epochs, steps,
   samples, evaluation episodes or batches, model or data sizes) and where the
   evaluator's own accounting checks derive from them.
2. Make a **scratch copy** of the task under `<scratch-dir>`. In the copy's
   `tests/` only, shrink the constants to the smallest values the evaluator
   accepts while keeping its accounting consistent (for example two epochs and
   the matching step count; a `selected_epoch` inside the shrunk range; one
   evaluation batch when the evaluator allows it). Change nothing else. Record
   the changed constants in the evidence directory. If no constant can shrink
   without breaking the Solution's contract, or the full Judge already takes
   minutes, run the copy unchanged and record why.
3. Run the copy as in Oracle runs.
4. Apply the step-6 checks to the result: the workload completed, stdout
   exposes only the promised feedback, the finite scalar was written exactly
   once, failure paths are not misreported, processes exited and GPUs were
   released.

When smoke exposes a defect, repair the **task**, not the scratch copy alone,
and follow the shared repair/revalidation rule. Continue until the path is clean
within the approved budget.

Also run one smoke pass with the maximum number of parallel candidates the
evaluator supports when it supports more than one, so that the aggregation and
the multi-GPU path are exercised; in the copy, make `solution/solve.sh`
materialize that many baseline candidates.

Record from the clean smoke run:

- unit cost `u` of the workload (seconds per epoch, per step, or per sample)
  and the fixed overhead `o` (Judge start, evaluator startup, evaluation) as
  measured from the round's output and `runtime_seconds`;
- `W`, the minimum Work-side machine time the Agent needs to produce one
  scoreable candidate. Count only the computation the task mandates, not the
  Agent's reasoning, editing, or optional local trials:
  - deliverable is data, configuration, or code only (a reward graph, a
    playbook, a manifest): `W = 0` beyond the public validation tool;
  - deliverable contains a trained artifact (checkpoint, fine-tuned weights):
    run the task's public Work tool or the instruction's fixed training
    command once at smoke scale in a disposable `docker run --rm` of the
    step-2 image under the declared Work resources and network (covered by
    the step-1 approval), take its unit cost `u_w`, and extrapolate
    `W = u_w × full units + overhead` on the declared Work GPUs;
  - deliverable needs an expensive non-training computation (generation,
    indexing): same method with that tool.
  `W` is a floor — real Agents iterate and evaluate locally — so projected
  loop counts are upper bounds. Allow research and operational margin rather
  than claiming these projections guarantee actual Agent loops.

The scratch copy never replaces or modifies the task and is not published
with the evidence.

## 5. Projection and judgment

Compute from the smoke measurements and the task declarations:

- `J = u × full workload + o` — projected wall-clock of one full Judge round;
- `T = [agent] timeout_sec` — the actual approved total research budget;
- `R24 = min(T, 86400) / (J + W)` — capacity in the first 24 hours;
- `R = T / (J + W)` — complete loop capacity across the total budget.
  Work remains paused throughout Judge in every GPU mode,
  including with disjoint GPUs or a CPU-only Judge; disjoint allocation keeps
  Work's GPU memory resident but does not overlap the two phases.

The bundled calculator prints these numbers, the two judgments, and the
applicable levers:

```bash
python3 <skill-dir>/scripts/project_budget.py \
  --unit-seconds <u> --full-units <N> --overhead-seconds <o> \
  --work-seconds <W> --agent-timeout <s> --verifier-timeout <s> \
  --work-gpus <n> --judge-gpus <n> [--disjoint] [--candidates-per-round <k>] \
  --baseline <score> [--score-max <ceiling>] [--over-budget]
```

Take `u` and `o` from the smoke timings, `W` from the task's candidate
requirements, the timeouts and GPU counts from `task.toml`, `k` from the
evaluator's candidate parallelism, and `--score-max` only for a bounded metric.
`--disjoint` labels the GPU allocation only; it never changes the serial
`J + W` cycle. Parallel candidates contribute to candidate-evaluation counts,
not additional adaptive loops. Use `--over-budget` only for the confirmed
task-owned marker recorded at intake, not a candidate-created file or a new
marker invented to bypass a failed check.
The calculator reports `pass`, `pending`, or `repair_required` in `--json`
output and corresponding text states. Exit 0 means all required judgments
passed, with confirmed reference-budget exceptions explicitly reported as
`EXCEPTION`, not `PASS`. Exit 1 means pending evidence or an unexcepted failure;
exit 2 means invalid numeric inputs. A known failure takes priority over a
pending baseline. Zero Work cost is valid; timings must be finite and the
projected Judge duration must be positive.

Judgments:

- **A. Iteration budget**: normal tasks require `R24 >= 6` (a cycle no longer
  than four hours), `R >= 10`, and `T <= 172800` (48 hours). Extending the
  total budget does not relax daily cadence. These are measured projections,
  not instructions to execute six or ten real Agent loops during validation.
  A confirmed `OVER_BUDGET.flag` excepts daily cadence and the 48-hour ceiling;
  use its approved actual `T` without clamping it. The total-loop requirement
  `R >= 10`, headroom, Judge timeout, and all execution checks still apply.
- **B. Headroom**, only for a bounded metric (a ceiling exists: success rate,
  accuracy, pass rate): `ceiling − baseline >= 20 points` on the metric's
  natural scale (0.20 on a 0–1 rate) — a margin so that improvements stay
  measurable, not a required improvement. Skip B for unbounded metrics.
- `J <= [verifier] timeout_sec`.

For a bounded metric with no current baseline, B stays `pending`, not passed
or skipped. If the time judgments pass, the planned step-6 Full Judge can
supply that baseline; missing B alone does not require an extra calibration.
For an unbounded metric, B is genuinely skipped.

**Calibration runs.** Calibrate only when a full-protocol measurement is needed
before settling the final task version — for example uncertain `J` or baseline
headroom needed to choose a protocol adjustment. Otherwise go straight to the
acceptance run in step 6. A calibration run is an oracle run exactly as in
step 6 on the current task version, recorded in the validation directory as
`calibration-<n>/`. Settle judgment A from the projection before calibrating,
so no full-length run is spent on a version A has already rejected. At most
three calibration runs per validation, in parallel when GPUs allow. A
calibration's score and `J` replace the projected values for the judgments.

All required judgments pass: record `J`, `R24`, `R`, `T`, the baseline, and any
confirmed exception in the validation report; do not change the contract or
shrink an accepted heavy task solely to meet an excepted reference budget.

If only the total-loop count is short, extend `T` within the approved envelope
to cover at least `10 × (J + W)` plus research/operational margin: normally at
most 48 hours, or the confirmed exception's approved budget. Recompile and
reproject; this alone needs no new smoke or Judge run. For example, a four-hour
cycle fits six loops in 24 hours but needs over 40 hours including margin to
support ten. Approval of a proposal without a flag is not measured acceptance:
a 4.5-hour cycle can fit ten complete loops in 48 hours at proposal stage but
still fails the normal validator cadence. Do not manufacture a flag to bypass
that check.

A judgment fails: adjust the task within the approved envelope, using these
levers in order and the shared repair/revalidation rule after each change:

1. Non-contract levers, any order:
   - let Judge score several candidates per round in parallel across its
     declared GPUs when the evaluator trains or evaluates one candidate per
     device, but count only measured cycle-time savings toward loop cadence;
   - align the Work and Judge GPU declarations with what the evaluator can
     actually use (an evaluator pinned to one device gains nothing from four);
   - remove fixed per-round costs that repeat identical work (a baseline that
     is re-measured every round can be measured once and recorded);
   - align `[verifier] timeout_sec` with `J`, and CPU/memory/shm declarations
     with measured use.
2. Contract levers, smallest scientific impact first:
   - evaluation size (episodes, batches, samples), keeping it large enough
     that the metric's resolution is finer than the improvements the task asks
     for;
   - fixed training or computation budget (epochs, steps, transitions, tokens);
   - environment difficulty constants (randomization ranges, episode length,
     tolerances) when B fails because the baseline saturates;
   - model or data scale.

Every contract change must be written into `instruction.md` and `README.md`
(the fixed protocol, the changed constant, and the baseline measured for it)
and listed in the report. When the levers are exhausted, or three calibrations
have not met all required judgments, stop with `BLOCKED` and report the
measurements.

## 6. Full Judge (gate)

This is the acceptance run: exactly one oracle run on the **final** task
version. When the final version is byte-identical (tests, environment, task
metadata) to the version of the last calibration run, that calibration run is
the acceptance run and is not repeated. A change only to `[agent].timeout_sec`
does not invalidate otherwise qualifying acceptance evidence after recompilation
and reprojection. Other changes require a new acceptance run.

Run the final task as in Oracle runs. For a networked Judge, verify that only
the contract-declared evaluation service is used, required runtime credential
variables are available without exposing values, and no dependency, data,
package, checkpoint, or tool fetch is hidden in evaluation.

Capture the CLI's complete output and exit status. After completion verify:

- the round's status is `completed` and the full declared workload finished
  within timeout;
- stdout exposes the promised feedback and no hidden examples, answers,
  per-example decisions, or protected evaluator details;
- the declared finite scalar is written exactly once to
  `/logs/verifier/reward.json` or the supported scalar fallback, and the
  round's `score` is that value;
- the score matches the baseline the task documents (or the Solution is
  designed to reach); an unexpected score is a defect to investigate, not a
  baseline;
- incomplete, infrastructure, timeout, or malformed-reward paths did not get
  misreported as success; and
- Judge processes exited and any allocated GPUs were released.

The round's `runtime_seconds` is the final `J`; its score is the recorded
baseline.
Recompute step 5 with this actual `J` and baseline before reporting readiness,
including any previously pending B. A successful Judge alone cannot clear a
failed or pending budget judgment; apply step 5's repair rules if needed.
Write both into the task documentation when the task states a baseline. When
the run fails, follow the shared repair/revalidation rule before retrying
acceptance. Do not repeat a passing acceptance run under a second label.

## 7. Result and handoff

Before reporting `EXECUTION READY`, write the final approved total research
budget `T` (including research and operational margin) to `[agent].timeout_sec`
in `task.toml` and reread it. Keep the report and task commit aligned with this
saved value; `rsi-task-runner` uses it by default. A timeout-only adjustment
requires recompilation and reprojection using existing timings, without
repeating the accepted Judge.

Return one status:

- `EXECUTION READY`: steps 2 and 6 passed after any reported repairs, and both
  step-5 judgments hold under any explicitly reported budget exception;
- `FAIL`: a reproducible task defect remains after safe in-scope repair is
  exhausted; or
- `BLOCKED`: an external prerequisite is missing, or the step-5 levers are
  exhausted with a judgment still failing.

Report in this shape, and nothing else that the contributor did not ask for:

```
Status: EXECUTION READY | FAIL | BLOCKED
Task: <absolute task dir> @ <commit>
Image: <tag> = <image id> (<size>)

Step 2 (environment): built <duration>; starting state OK (<one line of what was checked>)
Step 3 (dry-run): scan <complete/incomplete>; findings/deferred checks: <summary and real-runtime evidence>; repairs: <list or "none">
Harness: <bundled path> @ <commit> (refreshed: yes/no); sandbox policy: <path, reviewed> | none
Step 4 (smoke Judge): <n> oracle runs; repairs: <list or "none">; unit cost u = <s per unit>, overhead o = <s>, W = <s>
Step 5 (projection): J = <h>, T = <h>, R24 = <rounds>, R = <loops>; A cadence <PASS/FAIL/EXCEPTION>, total loops <PASS/FAIL>, budget limit <PASS/FAIL/EXCEPTION>; B <PASS/FAIL/skipped>; task changes: <none, or what was changed and why>
Step 5 calibrations: <n> runs (<version: score, J> ...) or "none"
Step 6 (acceptance): run <run id>, round <status>, test.sh exit <code>, J = <runtime_seconds>; baseline = <score>; reward.json written once; GPUs released
Commits: <task repairs hash> (task), <validation logs hash> (validation/<dir>), pushed to <remote/branch>
Retained: <image, container, network, Harness roots, oracle rsi-harness-work/rsi-harness-base images, sandbox-pulled images, evidence dir, scratch dir with sizes>
```

Handoff, two commits in this order, both pushed to the task repository's
confirmed branch:

1. **Task commit**: only the task changes (repairs, including a
   bundled-Harness refresh and an intake `rsi-isolate` migration, and any
   step-5 contract changes with their documentation). Message names the
   status, the repairs, and the contract changes.
2. **Validation commit**: only reviewed evidence from
   `<repository>/validation/<YYYYMMDD>-<label>/`. Exclude scratch state,
   checkpoints, datasets, and caches; logs larger than 80 MiB go
   through the run-log splitter from the `rsi-task-runner` skill.

Report both commit hashes and the push status; if a push is rejected, keep the
commits local and report the blocker. With no task changes, make only the
validation commit.
