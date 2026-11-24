---
name: rsi-task-runner
description: Execute, monitor, recover, or minimally repair one Harbor task beside its RSI-Harness checkout on Linux Docker or a supported native macOS Docker Desktop backend.
---

# RSI Task Runner

## Science route

Choose only the accepted task's running procedure:
- Metric Benchmark: [Benchmark run](references/benchmark-run.md).
- Discovery or an existing model-access rubric task: [Discovery run](references/discovery-run.md).

Install this runner with harbor-task-validator in the execution bundle.
Both reuse the Harness execution/recovery workflow below. Run only after matching
backend validation and research authorization. Preserve confirmed budgets and
explicit deferrals; keep Harness read-only. Keep task and trajectory artifacts
local unless publication is authorized. Before launch, resolve the
[candidate-retention handoff](references/scientific-reverification.md#before-the-run)
or its explicit deferral. After research and accepted Judge work
finish, invoke `<task>/operator/trajectory-auditor/` (or the sibling skill), reading
its SKILL.md and references/science-final-integrity.md to select the route policy. Missing audit evidence remains
pending, not a clean result. Then initiate
[independent scientific re-verification](references/scientific-reverification.md)
in a fresh reviewer context before the completion report; report any unperformed
checks explicitly. These rules override generic upload instructions.

## Overview

Run one Harbor task through the repository's own RSI-Harness checkout. Keep
RSI-Harness read-only, make only approved task-local repairs, and make the
Agent runtime and unlimited-by-default submission policy explicit before
execution.

Select by execution backend: Linux Docker (including over SSH) and supported
native macOS Docker Desktop use this skill. Mac execution requires the bundled
Harness compatibility guide and matching validation of the task and credentials;
run as the Mac user without sudo. Follow the backend procedure in the reference.
For an LSF, Slurm, Kubernetes, PBS or PJM site profile, use
`cluster-rsi-task-runner`, even for a single-node allocation. For missing baseline
acceptance or a required bundle
refresh, use the selected backend's validator (`harbor-task-validator` for Docker,
`cluster-harbor-task-validator` for a cluster), then carry its accepted
evidence and resolved authorization into the run.

**REQUIRED REFERENCE:** Read
[`references/run-workflow.md`](references/run-workflow.md) completely before
inspecting or running the task.

## Scope

Expect one supplied repository containing one RSI-Harness checkout and one
Harbor task. Discover both by the markers in the required reference, not only
by directory name. Ask for the intended path if either side is absent or
ambiguous. Do not use this skill for Blue Vela, task generation, baseline
validation, or deep trajectory audit.

## Workflow

1. Record both roots and the initial RSI-Harness Git state.
2. Read the task and current Harness CLI help; keep the CLI authoritative and
   apply the Agents section below.
3. Run the bundled runtime-environment preflight, then check Docker, disk,
   Agent authentication, and privilege availability read-only. Check GPUs only
   when Work or Judge requests them. If a required task variable such as an
   evaluation-provider API key is missing, stop before
   mutation and ask the user to configure it in the host environment without
   sharing its value.
4. Present the exact command and required confirmation below before mutation.
   When publication of task repairs is enabled and approved repairs pass validation, commit and
   push them separately before launching the next run; follow the reference.
   Publish authorized standalone validation logs in their own commit, separate
   from task changes and formal run logs.
5. Re-run the environment preflight in the launch environment and, for automatic
   publication, run the reference's read-only publication preflight as the same
   host user as Harness (including root for sudo runs). Then run
   synchronously, report the Run ID early, and monitor the same process. Start
   the reference's host-side publisher only when run-log publication is enabled: upload every 30 minutes,
   without Agent hooks, retaining lossless 80 MiB log splitting.
6. Judge the result from durable status and artifacts, then recheck that
   RSI-Harness is unchanged. Follow the reference for failure and repair.
7. After the run and any active Judge have stopped, verify the publisher's final
   upload to the confirmed upstream. Report publication failures separately from
   the experiment outcome; preserve local logs for retry. For local-only runs,
   skip publication and report the retained artifact paths.
8. For Science, complete the final trajectory audit and scientific re-verification
   above, then issue the completion report. Keep their reports separate from run logs.

## Required run confirmation

Present this card with resolved values, then wait for explicit confirmation:

```text
Task: <absolute task path>
Harness: <absolute read-only Harness path>
Agent/model/reasoning/auth: <resolved values; credential variable name and present/missing, never its value>
Task runtime variables: <required names and present/missing status; never values>
Sandbox policy: <path, reviewed> | none
Work/Judge GPUs: <declared counts; zero means CPU-only for that phase>
GPU selectors: <not required when both zero; explicit pool for Work=0/Judge>0; otherwise explicit or confirmed auto selection>
Agent time budget: <seconds and human duration> (<CLI override or task.toml source>)
Submission budget: <unlimited, the task's `max_submissions`, or user-requested N>
Score: <primary reward>, <maximize|minimize> (README run command)
Stop behavior: <plain-language explanation>
Science post-run review (omit for General): <reviewer/context and authorized resources, or deferred; separate from Agent time>
Data/log roots: <absolute paths>
Log publication: <local-only (Science default); or authorized host user and remote/branch, run snapshots every 30 minutes plus final upload, lossless 80 MiB parts; specify validation-log scope separately>
Task repair publication: <local-only (Science default); or validated, approved task-local repairs committed/pushed separately to the authorized destination>
Command: <exact command>
```

Explain both budgets every time:

- A user-supplied `--timeout` overrides `[agent].timeout_sec`; otherwise use the
  task value, including the final budget saved by `harbor-task-validator`.
  Show that value and its source in the confirmation card; do not substitute
  a fixed default. If neither exists, ask the user for an Agent time budget and
  never silently accept the 60-second Harness fallback. This Agent-phase wall-clock
  budget includes waiting for Judge; it is not a total end-to-end timeout.
  Image preparation, an accepted Judge
  finishing after Agent exit, recovery, and cleanup may extend total command
  duration.
- The submission budget is `--max-submissions N`, else the task's
  `[metadata.rsi_harness.verifier].max_submissions`, else unlimited. A budget
  N > 1 permits at most N Judge calls; exhausting it rejects later submissions
  and does not by itself terminate the Agent, which may continue until it exits
  or reaches its time budget. A budget of 1 is one final judge: the Agent's one
  `rsi-submit` ends the run, otherwise the Harness judges the WORKDIR when the
  Agent's time ends. The Harness refuses it with managed sandboxes or
  `model_access` (its `docs/harbor-task-authoring/task-toml.md#max_submissions`).
- Omit `--max-submissions` by default. Only when the user explicitly requests a
  finite cap, pass `--max-submissions N`. Do not ask the user to choose a
  submission cap; state the resolved budget (`unlimited` unless the task sets
  one) in the confirmation card and exact command.

Never treat a submission cap as a runtime cap. Never run until the user has
confirmed the resolved card, including the Agent time limit and the displayed
submission budget.

The confirmation also authorizes the displayed publication of validated task
repairs, associated validation logs, and separate periodic/final run-log commits.
Default to automatic publication, except for Science, whose artifacts stay local
unless publication is explicitly authorized; honor an explicit local-only request.
Permission to publish a proposal or task does not cover run logs. Publication
approval does not expand the scope of permitted task repairs. Local-only execution
does not require a remote, Git credentials, or publication helper.

## Agents

| `--agent` | Credential | Also required |
| --- | --- | --- |
| `codex` | `RSI_AGENT_API_KEY` or `--agent-auth local` | none |
| `claude-code` | `CLAUDE_CODE_OAUTH_TOKEN` (below) or `RSI_AGENT_API_KEY` | none |
| `qwen-code`, `kimi-code`, `opencode`, `zcode`, `pi` | `RSI_AGENT_API_KEY` | `RSI_AGENT_API_BASE_URL`, `RSI_AGENT_CONTEXT_WINDOW`, `RSI_AGENT_MAX_OUTPUT_TOKENS`, and a model (`--model` or `RSI_AGENT_MODEL`) |
| `antigravity` | `RSI_AGENT_API_KEY` or `--agent-auth local` (a personal Google login) | a model id listed by `agy models` (on a login, one the login lists), such as `gemini-4-hydrogen-high` (`--model` or `RSI_AGENT_MODEL`); `--reasoning-effort` (`low`, `medium`, `high`, `xhigh`) is set as the id's suffix; optional `RSI_AGENT_API_BASE_URL`, which must serve the Gemini v1beta API |

`oracle` runs the task's `solution/solve.sh` for `harbor-task-validator`; it
is not an experiment. For the Agents in the last two rows, ask for the model;
for the five endpoint Agents, also ask for the served model's real limits.

If the user has not chosen an Agent, ask. For Codex or Claude Code without an
explicit model override, use the exact current fragment and do not ask for the
model or effort:

- Codex: `--agent codex --model gpt-6-astra --reasoning-effort max`
- Claude Code: `--agent claude-code --model claude-opus-5-5 --reasoning-effort max`

Do not encode either Agent's effort into its model name. The current Harness
maps the generic option to each Agent's native control (Claude Code's native
`--effort max`). Show any user-requested model or effort override explicitly in
the confirmation card.

The Harness copies the credential into Work once and never refreshes it, so it
must stay valid for the whole Agent time budget. For Claude Code, the user runs
`claude setup-token` once and exports the long-lived `CLAUDE_CODE_OAUTH_TOKEN`
in the launch shell (`sudo -E` preserves it); the run passes
`RSI_AGENT_EXTRA_ENV=CLAUDE_CODE_OAUTH_TOKEN=$CLAUDE_CODE_OAUTH_TOKEN` without
`--agent-auth local`. Report only each credential's variable name and whether
it is present.

## Safety rules

- Treat every file under RSI-Harness as read-only.
- On Linux, never request or capture a sudo password. If `sudo -n` is unavailable
  and the bundled Harness cannot run without root, show one copyable command for
  the user to run interactively and continue from its observed output.
- Never run destructive cleanup automatically. Preserve final state and logs
  unless the user explicitly asks otherwise.
- Never guess GPU selectors, credentials, an unlisted Agent model, or semantic
  task changes. Use the listed Codex and Claude Code defaults when applicable.
- Never launch while a required task runtime variable is missing. Missing host
  credentials are an operator prerequisite, not a reason to rewrite the task or
  switch its fixed provider.

- Keep credentials and secret values out of commands, commentary, patches, and
  artifacts.

## Completion report

Report final status, Run ID, effective budgets, submissions, best score,
artifacts, task-local changes, and any recovery need. Include the task-repair
commit when applicable, the separate validation-log and run-log commits, and
the last verified upload and whether it is final, with their remote destination,
or the specific reason publication is blocked or local-only.
Local files or a local commit alone do not mean changes or logs are uploaded.

For Science, briefly explain the concrete result, agreed scope and remaining
uncertainties, linking the reported candidate/artifacts to existing Judge/checker
evidence. Distinguish candidate claims, model-reviewed conclusions and independent
checks. If no candidate has a completed evaluation, state why and label its status
accurately rather than selecting an unverified best result.
Apply the selected route’s outcome procedure for rubric verdicts or metric
measurements and any external-confirmation handoff. Link the independent scientific
re-verification report and state its coverage or why it remains pending; its
findings do not overwrite the score or trajectory integrity decision.

For a task reference, cite its recorded source/date and report better, equivalent,
worse or not comparable as the evidence supports under matched conditions; do not
infer a world record. Without a reference, describe the result directly. Reuse
existing report fields; no additional experiments, literature search, scoring or
acceptance requirements are introduced by this summary.
