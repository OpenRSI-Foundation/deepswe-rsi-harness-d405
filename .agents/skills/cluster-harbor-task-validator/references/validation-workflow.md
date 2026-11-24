# Validate an existing cluster task

Use the seven-step single-node validation contract below. Cluster execution
uses the [cluster transport](cluster-execution.md); science, baseline acceptance,
budget decisions, repair scope and publication semantics stay the same.

### Existing-task compatibility refresh

Read [the shared intake refresh procedure](compatibility-refresh.md) when the
bundled runtime or installed Skills lack a required capability. It is a bounded
validator operation, not permission to regenerate the task or upgrade a live run.

## 1. Inspect and resolve the envelope

Read `task.toml`, `instruction.md`, `README.md`, Environment, dependencies,
assets and `tests/`. Inspect Solution and its baseline provenance. Use native
Oracle for a Slurm, Kubernetes, PBS or PJM topology supported by the bundled Harness; otherwise use the
accepted operator-side baseline route in the cluster reference.
Record task/Harness/profile fingerprints and immutable source/data refs. Resolve
the baseline candidate from the untouched post-build starting state or the
task's approved baseline artifact, never a previous experiment checkpoint.

Run the read-only planner using the selected Harness environment:

```bash
PYTHONDONTWRITEBYTECODE=1 <harness-python> <skill-dir>/scripts/preflight_task.py \
  /absolute/task --harness-root /absolute/RSI-Harness \
  --cluster /absolute/site.toml [--sandbox-policy /absolute/policy.toml] --json
```

The script performs Harness compilation and profile/resource planning;
it does not build, allocate, execute or establish live readiness. Reuse the
existing task review and inspect execution-relevant issues; do not apply the
generator's README/headings/canary conventions as execution gates. Preserve an
explicit task Judge network exception. Missing runtime variable names are
reported as pending so offline planning needs no credentials; resolve them
before live execution. An optional
`--timeout` represents an explicit user override. Without it, require the
validated `[agent].timeout_sec`; never silently accept the Harness 60-second
fallback. A README `--max-submissions` value is not a formal-run cap.

If the legacy Judge isolates candidate code by switching users or chowning to
another identity, check that path under the cluster's non-root identity. Repair
that incompatibility within intake using the selected Harness's documented
`rsi-isolate` interface. Grant only the required trusted inputs/candidate reads
and scratch writes; preserve timeouts, network policy and hidden-data boundaries.
Do not grant all of `/tests`, replace isolation with direct execution, or change
the task user to bypass it. Revalidate the affected failure checks and baseline.
Use the bundled Harness authoring docs for exact flags; no sibling Skill is
required for these migration steps.

With a sandbox table in `task.toml`, pass `--sandbox-policy` with the operator's
reviewed policy, kept outside the task like the site profile: the task's
proposed `operator-policy.toml` plus a remote `[environments.host] backend`
(`"e2b"`, `"modal"` or `"daytona"`) and that backend's table, e.g.
`[environments.host.e2b]`. The planner checks it with the Harness, refuses a
Judge grant on a multi-node plan, and records the flag and the policy digest.
What the backend cannot run is refused when the env is defined; see the
operator guide's "Remote backends" section. Runs need the Harness environment
synced with that backend's extra, e.g. `uv sync --frozen --extra e2b`.

Disclose Work/Judge GPU counts and topology, per-node CPU/memory/tmp, shared
storage, build and runtime networks, endpoints, credential **names**, SIF/cache
paths, exact-run cleanup and retained resources. Calculate peak build/cache/
workspace headroom from image, data, checkpoint, source and package manifests,
download/extraction duplication and a plausible repair rebuild. Verify the
actual filesystems have this headroom before mutation.

Name `<repository>/validation/<YYYYMMDD>-<label>/` for publishable evidence and
an approved scratch directory outside task/Harness/evidence for temporary
copies, checkpoints and drivers. Ignore the exact scratch path if in Git.
Record commands and complete stdout/stderr to files, not conversation excerpts.

Resolve one envelope covering the seven steps, minimal task repairs, protocol
calibration within the approved science, cleanup of resources this validation
created, final task/environment publication and separate validation-log
publication. Existing explicit authorization is sufficient; do not ask again.
An undisclosed resource/science change needs new authority. Normally plan a
24-hour research budget, extensible to 48 hours. A contributor-confirmed
`OVER_BUDGET.flag` records an exception and its actual authorized total budget;
the file itself grants no resources.

## 2. Environment acceptance

Use the Harness compute-node image build/cache contract and the exact approved
Dockerfile/base digest. Validate the SIF checksum; never patch cached SIFs.
Reject image-declared volumes that break workspace snapshot ownership. Inspect
an untouched workspace seeded from that image, with task tests read-only,
effective WORKDIR/user/shared environment, correct phase binds and network
policy. Build and inspection launch no GPU workload; normally request no GPUs.
If the site requires a GPU allocation for image builds, use the supported
`[scheduler.build]` override described in `cluster-execution.md`, record its
resources and QOS, and keep the task Work/Judge allocation unchanged.

Check the task's public pre-scoring starting-state and editable-scope gates
without running the evaluator or importing candidate-controlled code. Include
installed/ignored/untracked metadata, `.egg-info`, bytecode, compiled products,
logs and caches. A Git commit or successful image build is insufficient.
Repair confirmed Environment defects within the envelope and rebuild affected
inputs. Retain the accepted image and evidence, keeping scratch out of Git.

## 3. Runtime diagnostics

In the accepted SIF, using the task interpreter, working directory and launcher
import paths, bind the bundled script read-only and run:

```text
<task-python> -I /validation-tools/runtime_dryrun.py
  --sources /tests <public-runtime-sources>
  --ldd-roots <site-packages> <native-library-roots>
  --report /validation/dryrun.json
```

The operator-side LSF/Slurm/Apptainer driver supplies those paths and phase-specific
binds. Ordinary imports/library checks use no GPUs, evaluator, training,
Solution or reward path. Conditional framework probes use exactly their
approved devices and stop before training; do not default to one GPU.

Import and `ldd` findings are advisory. Confirm a relevant failure with the
real launcher before changing working task code. Exit zero means the scan
completed, not task readiness. Context-dependent imports and loader paths stay
pending until actual startup. An incomplete scan is recorded as incomplete.
Use an existing task preflight when exposed; otherwise the Smoke and Full Judge
establish runtime validity. Do not invent a task bootstrap interface.

## 4. Smoke Judge

Make a fresh scratch copy. Reduce only fixed workload constants and matching
accounting checks in that copy so the entire evaluator path can finish in
minutes: candidate/preflight, necessary baseline computation, snapshot or
handoff required by that task, independent Judge, evaluation and reward write.
Keep the original unchanged and preserve integrity/failure checks, Work/Judge
GPU totals, topology, networks, assets and candidate authority boundaries.

On a supported Slurm, Kubernetes, PBS or PJM topology, run this scratch copy with native Oracle as
in the cluster reference, including its multi-node acceptance limits. Solution prepares the baseline in Work and the normal
submission path freezes it for Judge. On other backends or accepted legacy
bundles, use the operator-side driver with the same frozen pools and isolation.
Record baseline Work time `W` and Judge time separately. Do not run a research
model or add an independent generic transport test.

Measure workload-unit time `u`, fixed Judge overhead `o` (including applicable
snapshot, startup/reload/reshard/evaluation costs), and baseline Work cost `W`.
Check all ranks, checkpoint shards and complete handoff where relevant. A
shortened test proves only its exercised path, not the full protocol.

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
acceptance run in step 6. A calibration run is
the full Judge exactly as in step 6 (same image, constraints, unchanged
baseline candidate) on the current task version, recorded in the validation
directory as `calibration-<n>/`. Settle judgment A from the projection before
calibrating, so no full-length run is spent on a version A has already
rejected. At most three calibration runs per validation, in parallel when
GPUs allow. A calibration's score and wall clock replace the projected values
for the judgments.

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

For cluster execution, recompile/replan after resource changes and preserve
whole-node arithmetic and Work/Judge isolation. Any scheduling fallback keeps
the task's approved resource totals; queue pressure never justifies a smaller
task. Request only authority not already covered by the resolved envelope.

## 6. Full final-version baseline Judge

Use one native Oracle run on a supported Slurm, Kubernetes, PBS or PJM topology; use the documented
operator driver on other backends or accepted legacy bundles. Run the full
unshortened Judge on the final task's clean baseline starting
state, exact resources, networks and independent Judge authority. Require the
complete protocol, all declared ranks/shards/reload paths, nonempty logs and
the declared finite scalar reward written once to `/logs/verifier/reward.json`.
Native Oracle must return zero with the expected completed rounds; independently
check the score/evidence against the task baseline, since a completed round can
have a failing scientific score. Respect Judge timeout, read-only tests and
failure classification. Confirm
allocation completion and cleanup of owned remote processes/resources.

Reuse a successful byte-identical final-version calibration as this acceptance;
do not repeat it. An Agent-timeout-only change requires compilation and budget
reprojection, not another baseline Judge. A change to image, evaluator,
workload, resources, assets or baseline invalidates its affected evidence.
Rerun only affected diagnostics/smoke paths, then obtain final-version acceptance.

If the task expressly requires external baseline certification, obtain its
fresh uninterrupted rewardless certification first and then the normal
scoreable baseline. Preserve one source/image/profile/allocation lineage;
never stitch interrupted checkpoints into authority. This branch is not a
requirement for ordinary scoreable baselines.

## 7. Verdict and automatic publication

Return `EXECUTION READY` only when Environment, final Full Judge and both budget
judgments pass. `FAIL` means a reproducible task defect remains after safe
in-scope repair is exhausted. `BLOCKED` means a missing external prerequisite
or an exhausted budget/headroom adjustment process with a judgment still failing. Retain evidence for all
attempts. Record final budget, score, timings, resource/driver identities,
fingerprints and accepted/reused checks. A static pass alone is never ready.

After validation, automatically publish within the resolved destination:

1. Review and stage only validated task/environment source changes, including
   the final budget and any approved bundled Harness/Skills compatibility
   refresh and README changes. Commit and push those changes first. Verify the remote
   contains the commit; record its hash. If a preceding step already published
   it, verify that commit; if there are no changes, make no empty commit.
2. In a separate commit, publish finalized validation evidence under
   `validation/<YYYYMMDD>-<label>/`: planner/build/runtime logs, smoke/full Judge
   outputs, reward copies, timings and budget calculations. Include the
   inspected operator-side driver for reproducibility, with no credentials or
   site secrets. Exclude scratch candidates, datasets, weights, checkpoints,
   caches and SIFs. Use the [run workflow's splitting procedure](run-workflow.md)
   for every file above 80 MiB, then push and verify.

Use the confirmed upstream; preserve unrelated staged/unstaged work and remote
updates. No force push, blanket staging, invented branch or empty commit. “Push
env” is source-controlled task/Environment publication, not a container registry
operation. Outside the approved intake refresh, keep the Harness unchanged;
canonical site profiles remain read-only. A failed push is
a publication blocker; retain the changes/logs and do not start a formal run
with an unpublished fix. Honor an explicit local-only instruction instead.
