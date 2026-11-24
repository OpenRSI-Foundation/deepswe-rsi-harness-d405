# Discovery and existing rubric-runtime execution validation

This procedure applies to Scientific Discovery (public rubrics/Judge) and existing rubric-scored
Benchmark tasks (hidden rubrics/Judge), not new verified-metric Benchmarks. For an
existing hidden rubric task, use the Judge-shaped validation
container for `/tests/judge.py`
commands, not a Work container with secretly added tests. Work itself must have
no `/tests` and no Judge implementation. Never change task visibility just to
make validation pass.


Use this complete Discovery procedure with the selected local or cluster validator's
backend tools. Read [execution setup](science-validation-setup.md) for resource
authorization, environment tools, evidence storage and repair rules. No General
validation workflow is required.

Static and compiler checks come before this and use the `science-task-agent`
skill's `scripts/validate_task.py` during generation with an RSI-Harness that has
public Judge and model-access (`rsi-agent`) support, never `harbor-task-agent`'s validator,
which rejects a science package. A bundle's own checker (such as a
`check-bundle.py` for shipped legacy packages and archive bindings) never
validates a new task. Structural checks establish neither scientific truth
nor evaluation throughput, and an environment-only request does not
authorize a research campaign.

## Execution host and filesystem permissions

Local or SSH-controlled Linux Docker execution needs a rootful Docker daemon,
with the Harness run as root or in its non-root mode. LSF, Slurm, Kubernetes,
PBS and PJM execution follows the cluster validator. The bundled
Harness also has an experimental native macOS controller for Docker Desktop;
read its `docs/macos-docker-desktop.md` before selecting that backend. Use the
local Docker validator/runner as the Mac user, not `sudo`, and do not provision
a separate VM when native control is selected. This does not establish Colima,
GPU or sandbox-task support. Record the actual Docker context, daemon version,
architecture and resources; a Python process on Mac and a Linux container are
separate parts of the execution environment.

For macOS, accept only Linux-owned private Judge logs, daemon-side firewall
enforcement, working controller connectivity, exported artifacts and complete
submission/feedback behavior. Keep the actual permission probe below. The
Harness exports private logs before reward reading and retains failed exports
for recovery; do not replace its private volume with a host-shared bind.
Use the selected task's bounded fixed-submit Science acceptance, including its
real integrity audit and rubric review. A generic Oracle test or a one-prompt
model connectivity test is not full Science acceptance.

The Docker capacity planner stays read-only and prints a plan even when capacity
is pending. Follow the selected validator’s Mac capacity procedure: an authorized probe
measures VM free space,
and an explicit path from Docker Desktop's configured disk location identifies
the host backing filesystem. Use the smaller available capacity; do not guess a
default disk location or substitute the daemon data-root path on the Mac. Missing
measurements block execution, not planning. This small capacity probe does not
build or run the scientific task.

Standalone `--judge-llm-auth codex-login` renewal still requires Linux and is
refused on the native Mac path. A Judge API credential or a Codex Work Agent's
lent login is a separate path; validate the exact selected one. The live Mac
login smoke uses root Work. Do not infer non-root Work login readiness from it;
report an authentication-permission failure rather than changing the task user
to bypass acceptance. Validation authority does not authorize formal research.

Some host-shared mounts ignore container uid permissions. A directory marked
`0700` or file marked `0600` is not sufficient evidence of isolation. Use the
**actual logs mount and mount type** planned for the run in the stub Judge
acceptance. Do not replace a failing host bind mount with tmpfs for validation
and then launch with the original mount.

## Filesystem permission acceptance

With library v9.3 or later, a root Judge checks all five configured roots: `logs_dir`,
`tmp_dir`, `tests_dir`, `trajectory_dir`, and `workdir`. Each distinct writable
filesystem (`st_dev`) receives real low-UID reads, writes and traversal checks,
with positive controls. Input mounts confirmed readonly by the kernel are
recorded without creating scratch files. A failed probe stops candidate code
and model calls and produces no reward. Non-root Landlock acceptance is unchanged;
v9.4 `userns` routes keep the Judge's uid, so they rely on the box, not this probe.

| Location | Required protection in the actual Judge |
| --- | --- |
| logs and tmp | Private captures, model state and isolated copies must resist unauthorized reads/writes. Probe each writable device. |
| tests | Public procedure remains readable, but routes/model UIDs must not modify it. The Docker Harness stages `/tests` on writable tmpfs, so check actual ownership plus device permissions; do not assume a readonly bind. |
| trajectory | Engine-authored evidence must not be writable by routes or model UIDs. Check the actual readonly mount or DAC boundary. |
| WORKDIR | The submission snapshot must remain unchanged. Check the actual readonly mount and nested mounts. Public readability is not an integrity failure. |

Exercise the final mounted filesystems with root and representative route/model
UIDs, including an expected-denial fixture, and record each path, `st_dev`,
readonly status and result. On readonly fixtures, attempted write-open without
truncation must fail; compare input hashes before/after. On writable private
fixtures, run both positive controls and denied-access operations; separately
exercise the writable `/tests` tmpfs. Use bounded synthetic fixtures in the
actual task layout. A published task does not depend on the Judge library's
unbundled development test suite.
A capability probe does not certify every existing file's permissions, nested
mounts, or differing mount options on the same device. Do not loosen permissions
or scientific requirements to make validation pass.

Historical release hashes remain in the registry for provenance. New execution
requires a track-compatible Judge release, an explicit track, and revalidation; an older registered
hash alone does not make a task ready to run.
Non-root Judges retain their existing Landlock acceptance.

## Discovery validation steps

1. **Intake and resource limits.** Bind the approved contract and `tests/coverage.md`
   to the task version and implementation review. Follow the execution setup for
   the selected platform, evidence directory and authorization. Include CPU and
   memory for recomputation, `review_workers` concurrent `rsi-agent` calls and,
   for fixed-submit acceptance, the model Agent and its credential source.
2. **Environment acceptance.** Build or pull the image and inspect its untouched
   starting state using the setup's backend tools. Check declared dependencies,
   WORKDIR, mounts, user and resources without running research. Check that the
   image defines no `passwd` or `group` entry for uids 61000 to 61015 or the
   Judge's route uid block, and that `<WORKDIR>/candidate` contains the starter.
   Complete the filesystem permission acceptance below on the selected backend.
3. **Runtime dry-run.** Collect runtime diagnostics and confirm relevant findings
   on the actual computation path. In public mode, run `python3 /tests/judge.py
   --recompute <WORKDIR>/candidate` in a Work-shaped container (`tests/` read-only
   at `/tests`, `[environment.env]` set). In hidden mode, run recompute in the
   Judge-shaped container and verify the separate Work boundary below. Check
   [selected numerical backend readiness](#selected-numerical-backend-readiness)
   for required paths the starter does not exercise, and apply
   [CPU optimization checks](#cpu-optimization-checks) to adopted optimizations.
4. **Smoke Judge.** Use the [Judge-shaped container](#judge-shaped-container)
   with a stub `rsi-agent` and exercise the [required assertions](#required-assertions).
   Measure recompute, audit and review costs. Scripted verdicts establish handling,
   not scientific accuracy; retain the required real-model calibration below.
5. **Cost and feasibility.** Count Work time, a complete Judge round (recompute,
   audit and review), and operational margin per submission. Check the full Judge
   against `verifier.timeout_sec` and confirmed per-evaluation and total limits.
   Report projected iterations without imposing a minimum. An unsolved starter,
   including zero passed rubrics, is expected; rubric count is not a headroom
   requirement. Resolve a measured budget conflict without silently expanding
   resources or weakening scientific conditions.
6. **Full Judge acceptance.** Execute the bounded fixed-submit [end-to-end run](#end-to-end)
   on the final configuration with the accepted model settings. Reuse qualifying
   evidence rather than repeating the same acceptance run. A real research
   campaign is not part of this step.
7. **Result and handoff.** Close every required coverage row with its outcome and
   evidence or an explicit blocker. Report startup, recompute, integrity audit
   and scientific review separately, plus costs, configuration comparisons and
   limitations. An incomplete candidate may receive a valid partial rubric count;
   a runtime error or non-clear audit receives none. Complete the setup's version,
   budget and evidence handoff. Set `launch_ready` only after `EXECUTION READY`
   with empty `launch_blockers`; pending required acceptance prevents readiness.

## Close the authoring handoff

At intake, reconcile every execution obligation in the source contract with
the validation table in `tests/coverage.md`. Each needs an executable procedure
or fixture, an expected observable result, an owning stage and a result artifact.
Carry pending checks forward; neither a static validator pass nor the absence
of a runtime result counts as execution evidence. Reuse existing evidence only
when task bytes, environment and the exercised path match; record that binding.
If no supported procedure exists, record a launch blocker instead of silently
dropping the condition or asking the contributor to implement it.

For implemented scientific calculations, exercise the applicable
[semantic coverage cases](semantic-coverage.md) prepared during authoring through
the actual consuming path. A helper-only result does not establish that every
caller uses it correctly. Keep the original scientific criteria and expected
outcomes fixed, and record helper-only coverage as such. These are bounded
validation fixtures, not permission to run research or solve the open problem.

Confirm source review's checker evidence coverage against the actual configuration
and model input. Exercise necessary computations and check that their outputs,
errors and capture limits reach the relevant rubric reviewers. Missing required
verification prevents execution readiness. Keep advisory diagnostics and accepted
alternative proof routes distinct; do not add unconditional acceptance conditions.
Scientific verdicts come from the LLM, without automatic checker vetoes.

At completion, every required row must have an observed outcome and its evidence,
or an explicit unresolved disposition that prevents `EXECUTION READY`. A known
invalid fixture's expected rejection is a successful validation assertion, not a
scientific success. A research question remaining unsolved is not a failed
validation check. Bind the report to the final task file/hash manifest and the
independent review of that version. A later change needs affected revalidation
and targeted re-review before readiness can be claimed.

## Research conduct and access acceptance

Before declaring execution ready, check the actual Work instruction against the
contract and `integrity.md`: starting data, papers and code, additional-source
permissions, network policy and final-audit consequences must agree. Use the
selected backend's existing access probes to check the declared network boundary;
an instruction forbidding internet access is not network enforcement. Do not
change network defaults or weaken the boundary to pass validation.

Inspect the actual Work image, mounts and projected feedback for the selected
track. Scientific Discovery's permitted public Judge access is not a violation. Benchmark
must not expose internal rubrics, Judge materials or reference answers through
its packaged inputs or feedback. This does not certify that equivalent answers
are absent from the public internet or the model's prior knowledge.

Confirm that the assembled task contains `operator/trajectory-auditor/SKILL.md`,
its collector and referenced final integrity policy, without depending on the
authoring checkout or adding them to Work. Review the policy's contrasting cases
against the task's rules; use representative synthetic trajectories when testing
an actual audit model within the authorized validation budget. Scripted model
responses test plumbing, not semantic recognition of cheating. Record what was
reviewed versus actually exercised in the existing validation report.

Check `references/scientific-reverification.md` in the selected backend's runner;
the other runner is not required. The task README must identify the objective
type and retention procedure for the selected candidate and its evidence. During
the existing baseline/short validation, confirm that a submitted candidate can
still be recovered with the same contents and submission/version identity after
Work changes and temporary Judge snapshot cleanup. Use saved/versioned task
outputs within the agreed storage allowance, not an archive of every workspace.
If retention is unavailable, record scientific re-verification as deferred rather
than treating a score/log as reproducible evidence. Keep reviewer materials outside
Work. This is handoff readiness, not scientific re-verification or a new baseline
score; it does not authorize extra computation.

## Judge-shaped container

Exercise the Judge procedure in the built task image the way the Harness runs
it: root, `--read-only`, a 256 MiB `noexec` tmpfs `/tmp`
(`--tmpfs /tmp:rw,noexec,nosuid,nodev,size=256m,mode=1777`; Docker sets no
size unless you pass one), a read-only snapshot of the whole `WORKDIR`
(which holds the candidate at `<WORKDIR>/candidate`), as the Harness gives
each Judge, `tests/` staged in root-owned `/tests` tmpfs with the final Harness ownership, a writable
`/logs/verifier`, a synthetic `/logs/agent` with a valid `manifest.json`, and
the container network present. Set the environment the Harness gives the
test command: the task's `[environment.env]` with `[verifier.env]` merged on
top, plus `RSI_AGENT_NAME` (and `RSI_AGENT_MODEL` and
`RSI_AGENT_REASONING_EFFORT` when the run sets them), `RSI_JUDGE_MODEL` and
`RSI_JUDGE_MODEL_EFFORT` (library version 5) and
`RSI_JUDGE_ISOLATION_FALLBACK=none`, which an RSI-Harness that supports
Judges that are not root sets in every Judge (always `none` on local Docker).
Add one variable that stands in for a `[verifier.env]` secret. Install a
stub `rsi-agent` read-only at `/usr/local/bin/rsi-agent`.

**Stub `rsi-agent`.** It accepts `exec --prompt-file F --output F [--schema F]
[--timeout S] [--workdir D] [--log F]`, and `llm` with the same options without
`--workdir`, as the Harness documents them; for
`rsi-agent isolation` (Judge library version 4 and later ask it) it prints a report in
the real command's form, `{"mode", "landlock_abi", "fallback"}`, with `mode`
`"stub"` so the records show the stub, for example
`{"mode": "stub", "landlock_abi": 0, "fallback": "none"}`, and exits 0
(scriptable to exit 3, as the real command does when it cannot isolate the
Agent); and:

- records its argv and environment;
- tells the audit from a rubric job by the directory that holds
  `--prompt-file` (`audit`, or `rubric-<index>-<id>` with the id sanitized
  and cut to 40 characters), or by the schema: the audit schema requires
  `trajectory_digest`, and a rubric schema names its rubric id in
  `results.items.properties.id.enum`;
- returns schema-conforming verdicts with the digests copied from the task's
  Judge model prompts (inspect the actual `<key>: <hex>` lines in the
  generated prompt files), and can be scripted to return `violation`, `unresolved`, an answer
  that fails its schema, or wrong digests;
- can be scripted to exit 1, 3, 124, 125 or 143, honours `--timeout` with
  exit 124, and exits 143 on `SIGTERM`;
- exits 2 (a usage error, as `rsi-agent` does) for a prompt above 4 MiB or an
  `--output` or `--log` inside `--workdir`;
- as root, checks as uid 61000 that every evidence file the prompt lists is
  readable and not writable.

The stub stands in only for the Harness program; it is never shipped in the
task.

**Non-root Judge.** With Judge library version 4 or later, run the clear
round once more in the same container started as an unprivileged user
(`--user 1000:1000`) with `--read-only` and
`--security-opt no-new-privileges`, on a kernel with Landlock. Every place
the Judge writes must be writable by that user: keep the same `/tmp` flags
(`mode=1777` makes it writable) and give it a writable `/logs/verifier`, for
example `--tmpfs /logs/verifier:rw,nosuid,nodev,mode=1777` or a mount owned
by uid 1000. Every input the Judge reads must be readable by that user too:
`/tests`, the `WORKDIR` snapshot and `/logs/agent`. A host bind mount owned by
another uid needs world-read permission (directories also world-execute), or
an owner matching the chosen uid. The round writes the literal pass count, and `bundle.json`
records `execution_isolation.mode` `landlock` with its Landlock ABI and
`operator_fallback` `false`. This is the mode a Judge that is not root (every
cluster Judge, for example) uses. Where the host kernel has no Landlock, a
task on library 9.4 or later takes `userns` where unprivileged user
namespaces work (Docker's default seccomp profile refuses them); otherwise
record that this run was not possible, and that the round instead fails as
`infrastructure` before any route runs, as `RSI_JUDGE_ISOLATION_FALLBACK=none`
requires; only the operator's `same-user` fallback would let it run.
A task on library version 3 cannot run in a Judge that is not root; record
that it is limited to root Judges.

## Required assertions

Record each with its command and output:

1. each route runs as its own uid (root Judge) or confined by Landlock or
   user namespaces (the non-root run), on its own copy, with a minimal environment, and gets each
   `thread_env` variable (`1` when it is unset); with library version 4 or
   later `bundle.json` and `review.json` record `judge_library` with the
   version and sha256 of `tests/science_judge.py`;
2. a route that opens an `AF_INET` or `AF_INET6` socket fails, with the
   container network present, and so do `io_uring_setup` and an x32-ABI
   syscall from a route, and (non-root run) `ptrace` or `process_vm_readv`
   of the Judge from a route fails with EPERM; the `bundle.json`
   `execution_isolation.self_test` record is evidence alongside these direct
   probes;
3. no route or `rsi-agent` call receives the stand-in secret; the stub sees
   only `PATH` and `LANG`; the evidence the prompt lists is readable but not
   writable by uid 61000, and `/logs/verifier/model` is not readable by it.
   For v9.3 or later root/uid runs retain both UID reports for each writable device and readonly-mount records for inputs; exercise
   an intentionally exposed synthetic directory and confirm that validation
   fails before checker/model execution with no reward;
4. a route that overruns CPU or time is killed and its leftover processes are
   reaped;
5. a candidate changed after freezing is refused, and so is changed staged
   evidence;
6. symlinks and candidates beyond the file or byte bound are rejected;
7. a `violation` or `unresolved` audit writes no reward and exits 2;
8. an invalid, incomplete or digest-unbound verdict writes no reward;
9. a stale `reward.json` from an earlier round is removed first;
10. the shared review deadline holds, and the first error cancels every other
    job;
11. a clear round writes the literal pass count, and its feedback cites
    evidence relative to the evidence directory, never a `/tmp` staging
    path;
12. each model job is one `rsi-agent` call (`exec` for the audit; `llm` for
    each review from version 5) with its `--timeout` before the phase
    deadline; exit statuses 1, 2, 3, 124, 125 and 143 map as the Judge
    requirements define; cancellation sends `SIGTERM` to `rsi-agent`; missing
    model access, a missing `RSI_JUDGE_MODEL` (version 5), or (version 4 and
    later) `rsi-agent isolation` exiting 3, fails in stage `validate` before any
    recompute; (version 5) each review prompt carries the evidence content,
    and a `review_evidence_chars` below the evidence size marks truncated
    files in the prompt and in `review.json` `review_evidence`;
13. for Scientific Discovery, the `--recompute` preview works in Work and writes nothing
    under `/logs/verifier`; for Benchmark, Work has no private preview or `/tests`,
    and recomputation is exercised in the Judge-shaped validation container;
14. data files are verified against their manifest hashes;
15. every route uid can read the data it needs;
16. a whole round, with the largest allowed candidate, fits the writable
    locations of the Judge ABI (`/logs/verifier`, `/tmp`) without writing
    anywhere else;
17. a missing `<WORKDIR>/candidate` writes no reward and reports
    `candidate_missing`.
18. exercise checker failure, timeout, signal termination, truncated and malformed
    output; verify the actual diagnostics reach the model. With controlled model
    pass/fail/unresolved answers and valid citations, verify those scientific
    verdicts are retained. A missing checker script remains infrastructure/no
    reward; a command-start failure must be visible as an execution error. Independently test rejection of a nonexistent evidence citation.
    These synthetic tests establish transport and verdict handling, not scientific
    accuracy. Calibrate the real review model against known invalid and valid
    evidence under the task's rubric, recording misjudgments and untested cases;

19. audit provenance across submissions: a known forbidden-origin candidate,
    the same bytes with no new actions, and a documented repair. The unchanged
    candidate must not become clear merely because its creation lies before
    `previous_size`. Include missing-history cases both with and without necessary
    provenance evidence omitted. The audit must explain their effect under the
    task rules and return unresolved when necessary evidence is missing; bounded
    log snapshots alone do not impose an additional acceptance condition.
    Calibrate the real audit model on these cases; a stub validates verdict
    handling and prompt delivery, not provenance judgment or model reliability.

## End to end

### Select a supported validation Agent

In the pinned Harness, `--agent oracle` has no one-shot model backend; Science's integrity audit calls
`rsi-agent exec`, which uses the Work Agent's backend. Therefore oracle cannot
validate the current Science Judge end to end, even with `--judge-llm-auth`:
that flag supplies `rsi-agent llm`, not the missing audit backend. Do not disable
model_access, remove the audit or swap in a stub to claim acceptance.

For current Science tasks, use a supported model Agent for a bounded fixed-submit
validation. This runs the actual Judge without an autonomous research campaign. Reuse the accepted Agent model/effort
and Judge model/effort. Obtain only missing model-cost authorization; never request
secret values. If access is unavailable, retain the unit-test evidence and report
end-to-end acceptance pending.

### Local or remote Linux Docker: fixed-submit acceptance

1. Create a disposable copy of the final task outside the task repository.
   Record a file/hash manifest of the original and copy. Change only the copy's
   `instruction.md`, preserving the original in evidence. Keep the original task,
   image inputs, tests, scientific rules, model settings and starter unchanged.
2. Replace that instruction with the following fixed validation instruction,
   filling WORKDIR with the actual declared directory:

   > This is execution validation, not research. Do not edit files, install
   > dependencies, optimize the starter, or search for a solution. From WORKDIR,
   > call `rsi-submit` exactly once on the unchanged starter. Read the feedback
   > and exit. Do not retry a rejected submission or claim scientific success.

3. Run the copy through the real Harness with the accepted model Agent. Record
   the exact CLI and use `--primary-reward reward --disable-stop-hook` with the
   `--score-direction maximize` for rubric counts. The stop hook otherwise prevents the requested
   natural exit; disable it only for this fixed-submit validation, not formal
   research. Omit `--max-submissions`: a budget of 1 is one final judge, which
   `model_access` refuses. Set an explicit validation `--timeout` sized for
   startup, submission and one full Judge. It does not replace the approved
   research budget. Use declared CPU/RAM and GPU pools, and `--sandbox-policy`
   only if the task requests managed sandboxes. Do not launch without the
   confirmed validation allowance.
4. Verify the trajectory contains exactly one submission, no starter changes,
   no research actions and a normal Agent exit. Compare candidate digests with
   the seeded starter. Any drift invalidates this fixed-submit check; do not
   quietly accept a better candidate. Record the changed instruction as a
   validation-only difference: this verifies transport/Judge execution, not the
   original research instruction's behavior.
5. Inspect `final_result.json`, `run-plan.json`, `agent_output.txt`,
   `submissions/agent-1/report.json`, `test_output.txt`, and the round's
   `verifier/agent-1/` artifacts. Verify the score against recorded expected
   fixture outcomes and inspect `bundle.json`, `integrity.json`, `review.json`
   or `review-error.json`. Zero passing rubrics is valid for an unsolved starter.
   Process exit 0 or a model verdict alone never proves scientific success.

Keep mock-model and adversarial checker tests above as unit tests. A fixed
negative fixture belongs in a separate scratch copy with its expected rejection
recorded, never in weakened scientific rules. Negative testing does not replace
successful final-version execution. Require `task.verifier.clean_image: true`,
unchanged trusted `tests/` bytes and evidence that changes outside WORKDIR do not
reach Judge. Record isolation, source/image/candidate/rubric digests and measured
checker/audit/review timings; calibrate Judge deadlines within the approved
resources. Retain evidence before authorized exact-run cleanup; no automatic
upload. Do not repeat qualifying byte-identical acceptance unnecessarily.

### Cluster execution

Use `cluster-harbor-task-validator` with this reference. Its bundled planner
compiles the task/profile and reports resources without allocating or building.
Use the selected site's scheduler for compute-node image, isolation and Judge
checks; a login-node or Docker check cannot establish cluster acceptance.
Native `--agent oracle --cluster` supports compatible general baselines on the
Slurm, Kubernetes, PBS and PJM topologies documented by the bundled Harness;
check its version and acceptance limits first. Oracle does not supply the model backend required by
the Science integrity audit.
Retain the model-backed fixed-submit procedure below for full Science acceptance
and do not silently replace the selected backend.

The upstream cluster procedure supplies direct evaluator smoke/full checks.
Adapt these to the Science checker, audit and review with fixed fixtures and
record exact driver/profile/image/allocation evidence. These establish only the
exercised Judge path. For complete production submission-path acceptance, reuse
qualifying evidence for the identical final task and environment, or prepare a
separately authorized bounded validation Agent run following the fixed-submit
procedure above, using the same unchanged starter and validation-only instruction. Use a supported Agent with
the accepted explicit model/effort and separate Judge authentication. Inspect its
trajectory to confirm no research or fixture optimization occurred. Record its
exact command, fixed instruction, submission count and the same artifacts as the
Docker route; account for submission wrappers and allocation shutdown.
If that supported launch, authorization or evidence is unavailable, report
`BLOCKED` with production-path acceptance pending, not `EXECUTION READY`.
Do not launch autonomous research as part of validation.

For either backend, report `EXECUTION READY` only when all required assertions,
final-version acceptance, resource checks and model calibration are satisfied.
Report execution health and scientific completion separately; a valid partial
rubric count does not mean the problem is solved.


## Selected numerical backend readiness

An incomplete starter can return before invoking a required numerical backend.
An import or device listing does not establish that the actual computation works.
Reuse existing dry-run, smoke or calibration evidence if it exercises the path.
Otherwise run a bounded case through the relevant task code in the final image,
with the authorized phase's environment and devices and an expected outcome.
Source generation prepares the case; execution validation runs it. Step 2 remains
free of requested GPU work.

Keep an unexercised required capability pending under existing readiness rules.
Record the backend actually exercised: an allowed CPU fallback remains valid,
but does not establish GPU readiness. Optional optimizations and methods left
open for research add no mandatory probes. There is no case-per-dependency quota.
A small successful case establishes the exercised capability, not full-campaign
cost, acceleration or scientific success.

## Hidden implementation acceptance

For Benchmark, verify the actual built Work image and task boundary: the public
instruction and inputs are readable, but `/tests`, internal rubrics, complete
contract, reviewer/audit prompts and Judge/checker code are absent from Work.
Inspect build inputs and image paths, not just permissions. The instruction must
state the goal, submission interface and integrity obligations. For Benchmark,
verify that public Work can read a permitted source and that model-provider
transport succeeds. Check required starting inputs and permitted paper retrieval.
For an explicitly restricted task, exercise its declared policy instead. Verify
withheld test instances and answers are absent from the image, mounts and feedback. Scientific Discovery verifies readable
trusted `/tests` and the existing preview instead.

Run bounded fixed-submit full-Harness acceptance with declared model access:
an incomplete candidate, a revised candidate and an evaluator error. Generic
Oracle alone does not validate the Science audit/model path. Benchmark feedback
must contain only aggregate results, restricted failure feedback and Harness
status/score; full per-item reviews remain private. Verify that
`tests/feedback-context.md` is a byte-identical copy of public `instruction.md`.
Each formal review must produce a dedicated public feedback field alongside its
private verdict; only unchanged fail/unresolved verdicts may contribute public
feedback. Check that the feedback describes actual review findings, reveals no
private rubrics, thresholds, test cases or answers, and withholds explanations
that cannot be safely shared. Exercise an incomplete candidate, a corrected
candidate, a private canary and candidate prompt injection with the actual Judge
model; scripted responses test plumbing, not semantic disclosure control. No
separate advice model or candidate-prefix cutoff is used. Scientific Discovery retains full
per-item feedback. Check equivalent rubric-count profiles score identical internal verdicts equally. Exercise checker errors, timeouts, malformed model output, and a
candidate asking the reviewer to reveal hidden text. Inspect stdout, stderr and
returned artifacts for leaks. Preserve the internal records and report exercised
capabilities separately from untested deployment paths. Online discoverability
and Discussion publication are outside this check.

Stub model tests establish execution/transport behavior, not live-model acceptance.
Real-model calibration still follows the existing acceptance procedure. Keep
untested backends pending; revalidate the final task version and track before research.

## Validate the result profile

Use the accepted contract's deliverables and verification scope. Test the
implemented evidence path and report what it establishes within the declared
environment; a successful program or model call alone does not validate a
real-world claim. If validation exposes a need for outside experiments or a
change to scientific acceptance or committed resources, return that decision
for contributor confirmation. Keep ordinary in-scope implementation repairs
within the existing authorization and do not repeat settled interview questions.

- Match validation to `target.objective_type`: exercise claim evidence, metric
  recomputation or both. For a metric, compare a known better and worse candidate
  under the same units and conditions; verify the LLM applies the agreed criteria.
  Exercise any agreed scientific fit/refit with the declared data boundary. These
  are checks of the existing Judge, not a new scoring backend.
- Exercise the actual staged asset path with representative inputs. Check pinned
  versions, offline availability or authorized source retrieval, storage and
  setup costs. Exercise the selected local, shared-storage or data-service path
  under the actual network policy. Measure Work and the complete Judge within the
  approved validation budget; distinguish measured checks from estimated full-scale costs.
- Check the assembled inputs against the approved scope and selection principle.
  For Benchmarks, inspect whether answer-conditioned filtering or exposed
  target answers remove the intended reasoning or discovery work.
- For Benchmark literature, exercise permitted public retrieval and any staged
  copies or excerpts under the declared network policy. Check provenance, documented use restrictions and
  that the Work package includes neither account credentials nor private evaluation
  references. Missing essential literature requires a permitted source or a
  contributor-confirmed scientific substitute, not a silent change of input scope.
- For an external-confirmation Scientific Discovery task, use a complete synthetic handoff and an
  incomplete one. Check that only the scoped package can pass all rubrics and
  that even a pass retains external confirmation as pending. Check the handoff
  includes the candidate, supporting evidence, test, controls, observations and
  support/refutation conditions, and can be used by the declared follow-up operator.
  Synthetic cases validate the evaluation path, not the scientific hypothesis;
  do not run the external test
  as part of ordinary validation.

## CPU optimization checks

Follow the shared [compute comparison procedure](compute-validation.md).
Its final acceptance means the full scientific Judge for this route.

## Partial Landlock ABI support (General interface; library v7)

Probe on the allocated compute node, in the task container, before Work starts.
ABI version alone is insufficient: RHEL-125143 kernels may report ABI 6 while
rejecting signal scoping. The default remains fail-closed for this mismatch.
The operator may explicitly choose `[apptainer].judge_allow_missing_landlock_signal = true`
in the bundled General Harness. It supplies `RSI_JUDGE_ALLOW_MISSING_LANDLOCK_SIGNAL=1`
to the Judge; tasks cannot set this policy. Retry is restricted to reported ABI 6
and `EINVAL`, never a newer ABI or another failure. This permits only a successfully
probed ruleset retaining filesystem/network and abstract Unix socket scope;
it never enables `same-user` if Landlock is absent. Library v7 and the Harness
model wrapper must both support this policy. Do not alter a released library
in place; copy the new version and update its provenance when upgrading a task.

Record reported ABI separately from actual scope flags. Under this policy a
partial ABI 6 host records `operator_fallback: true`, `capability_status:
"limited"`, and `signal_scoping: false`; the self-test explicitly records
`signal_scoping_tested: false`. Signal confinement has not passed or been
replaced. Test the remaining file, network, tracing, cancellation and descendant
cleanup guarantees on that host. Report acceptance only against the explicitly
selected policy, never as full isolation. If the task's approved execution
policy requires signal confinement, keep it blocked or use a suitable backend.
Do not change scientific rubrics to accommodate infrastructure limitations.

The old `judge_isolation_fallback = "landlock-no-signal"` setting is not accepted
by General. Existing v6 tasks need an explicit library/provenance upgrade and
revalidation before using this policy; keep their historical evidence unchanged.

## Large raw-evidence transport

When the task uses release-8.2 `read_candidate` / `bulk_evidence_paths`, exercise its
full raw interface at representative maximum size and the actual 256 MiB tmpfs.
Confirm streamed frozen hashing, read-only raw access, bounded staging and
cleanup, full-manifest disclosure, source/frozen mutation detection and required
checker enforcement. Check that necessary code/provenance is available to the
audit, including newly added unlisted files. Deliberately misclassify necessary
code as raw and verify task-specific audit/checks prevent a clear/pass result;
verify missing requested evidence and truncated excerpts remain disclosed.
Omitted material must not silently pass. Measure disk/RAM/I/O consumption
and storage-exhaustion no-reward behavior separately from scientific success.
The library regression fixtures do not establish this task's execution readiness.
