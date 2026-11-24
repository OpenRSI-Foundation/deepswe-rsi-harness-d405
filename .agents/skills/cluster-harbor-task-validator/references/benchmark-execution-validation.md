# Benchmark execution validation

For `[metadata] science_track = "benchmark"`, follow this complete procedure.
Read [execution setup](science-validation-setup.md) for platform selection,
authorization, environment tools, evidence storage and repair rules. The Science
static validator checks `tests/proposal.md` and compiles the task before this stage.
Use the existing evaluator, scalar reward and feedback interfaces. This route
has no Science rubric library, per-rubric schema or `--recompute` requirement.

## Benchmark validation steps

1. **Intake.** Bind the approved proposal, task files and implementation review.
   Confirm the metric, direction, validity constraints, comparison protocol,
   expected baseline behavior and resource limits. Select the execution platform
   and prepare evidence and scratch locations using the execution setup.
2. **Environment acceptance.** Build or pull the image and inspect its untouched
   starting state, dependencies, data, WORKDIR, mounts, user and resources with
   the selected backend's tools. This inspection runs no research or GPU workload.
3. **Runtime dry-run.** Collect dependency diagnostics and confirm relevant
   findings on the real startup path. Run a bounded framework/GPU probe only
   when needed and authorized. Verify the actual Work and Judge access policies.
4. **Smoke evaluation.** Run the baseline through Harness Oracle on a disposable
   reduced task copy, preserving scientific conditions, isolation and network
   policy. Exercise the metric and failure cases below and measure required
   Work plus complete evaluation costs. Use controlled candidates to check
   repeat-submission feedback, not a research Agent searching for improvements.
5. **Cost and feasibility.** Apply the compute comparison procedure below and
   assess the final configuration within confirmed resources. Report measured
   costs and projected iterations; there is no minimum iteration count or
   bounded-metric headroom requirement. Check evaluator timeout and retain the
   approved research budget. Resolve any resource conflict before claiming readiness.
6. **Full evaluation acceptance.** Run the final version's complete baseline
   through Oracle, reusing qualifying final-version evidence when available.
   Compare the reward and feedback with the approved metric and expected outcome;
   process exit zero alone does not establish acceptance. Use the execution
   transport below and preserve failures as evidence.
7. **Result and handoff.** Report environment, baseline, metric/failure-path
   checks, measured costs, configuration comparisons and remaining blockers.
   Declare `EXECUTION READY` only when required checks and budget feasibility
   are established for the final task/image/Harness/profile. Complete candidate
   retention and the setup's budget/evidence handoff. Stop after validation;
   research and publication require their own existing authorization.

## Baseline execution transport

Use the task repository's bundled Harness and locked environment. For supported
Linux or macOS Docker, run the baseline through:

```bash
<harness>/.venv/bin/rsi-harness run /absolute/task --agent oracle \
  --data-root /absolute/scratch/harness-data \
  --logs-root /absolute/scratch/harness-logs
```

Use the approved Linux privilege mode or native Mac user. Add `--gpus` only for
a declared GPU pool, and `--sandbox-policy` only for a task that requires it.
Size any validation timeout for baseline materialization plus the full evaluator.
Oracle materializes `solution/solve.sh`, removes its private solution mount and
submits through the actual evaluator. Inspect `final_result.json`,
`submissions/agent-1/report.json`, `test_output.txt`, reward output,
`agent_output.txt` and `engine_error.txt` when present. Confirm completed rounds,
Solution exit status, evaluator status, reward and expected evidence; retain
complete outputs, not just a CLI exit code.

For clusters, use the selected cluster validator's
`references/cluster-execution.md` baseline transport commands with the approved
site profile. Check native Oracle support on the exact version and topology;
where unsupported, use only a documented, authorized operator baseline route or
report the limitation. A dry run or local pass does not prove cluster acceptance.
Keep evaluator model configuration/authentication when the task declares it;
Oracle cannot supply a Work-backed `model_access` audit.

## Metric, feedback and scientific checks

Verify a scoreable starter and controlled better/worse candidates against an
independent metric calculation, including fractional rewards and the proposal's
maximize/minimize direction. Exercise candidate-invalid, evaluator-error and
timeout paths: only a declared candidate-failure outcome receives its agreed
scalar; infrastructure and incomplete evaluation stay unscored. Check actual
Work/Judge network policies and repeat submissions with useful feedback that
does not reveal private tests or answers. The evaluator exposes stdout/stderr, so check
child outputs and failure paths as well as successful feedback.

Measure Work and complete evaluation cost and follow the shared
[compute comparison procedure](compute-validation.md) for the final configuration.
Its full Judge acceptance means the complete evaluator for this route. Preserve scientific
requirements when changing execution settings. A successful fixture does not
validate the task's scientific metric, noise or tolerances. Validation does not
authorize research. Science artifacts stay local unless publication is authorized;
final research still requires trajectory-auditor and a scientific outcome report.

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

Benchmark uses contributor-confirmed resource limits. Check complete evaluation
against its timeout and agreed resources. Report measured Work and Judge costs
and projected iterations without using a budget helper's generic pass/repair
verdict as acceptance. Seek approval for changed commitments, without silently
extending budgets or changing scientific criteria.
