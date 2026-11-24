# Stage 8 Generator review and correction record

## Controller correction round 1

This invocation owns the edits for the two MAJOR findings in the supplied initial `CHANGES_REQUIRED` review. It did not repeat Stages 1–7 or start an independent review. The confirmation and complete handoff were read; no eligible contributor feedback changes the contract. The existing destination is `output/deepswe-rsi-harness`; `run/` and supplied evidence remain read-only. Scientific decisions, baseline, roster, reward, failure scalar (none), network/data scope and budgets are preserved.

**Provider failure/completion finding — fixed.** `tests/provider.py` now registers every accepted request before credential/network access, observes non-2xx status, JSON/SSE error/failure/incomplete signals, missing terminal events, truncated delivery, cancellation and transport failure, and retains explicit completion/error accounting. Responses requires a completed response; streamed Messages requires its terminal event. A subsequent completed request with identical normalized service/method/path/query/body/protocol headers links recovery to earlier failed attempts. Unrelated successes and candidate `done` cannot clear failures. No automatic extra attempts or new inference requirement was introduced. HTTP responses remain available to clients; transport failures keep RPC/relay retries available within the original deadline.

`tests/episode.py` observes RPC termination, stops and waits for the native relay, scans its remaining queued requests, settles/cancels pending transfers, and applies the trusted completion gate before patch collection. Credential/service failures and unfinished operations therefore cannot reach pristine grading or aggregate reward, regardless of zero worker exit. `tests/evaluate.py` and `operator/final.py` bind checkpoints to evaluator revision 2 so pre-correction completed records cannot bypass the corrected gate; image preparation and the scientific protocol identity are unchanged. Candidate/no-op evaluations with no inference still reach their ordinary scoring path, and completed incorrect patches remain zero.

**Lost solving diagnostics finding — fixed.** The candidate `exec` RPC supplies an explicit output sink to `PierManagedEnvironment.exec`. Each received stdout/stderr prefix is emitted within the existing 16-MiB per-stream bound before any bound exception. Timeout, OOM, truncation, transport error and cancellation preserve already-received output and emit a termination record with available bytes and failure/cleanup reasons. Cancellation shields the follower, requests command termination and allows a bounded drain. The broker no longer re-emits the full successful buffers, though the RPC still returns them to its caller. Relay shutdown also drains its bounded candidate-owned streams. Pristine grader calls never receive the public sink, so hidden grading output remains protected. No blanket feedback suppression was added.

Static path checks covered these outcomes (inspection only, no execution):

| Path | Required outcome established in the delivered control flow |
| --- | --- |
| HTTP 401/503, SSE error, failed/incomplete response, EOF without terminal event, missing credential | Failed trusted attempt; unresolved final gate raises; no reward |
| Identical completed retry before deadline | Separate attempts/usage/durations plus `retry_of`, `recovered_attempts`, `recovered_by`; recovery allowed |
| Unrelated completed request after a failure | Prior request stays unresolved; no reward |
| Worker sends done with pending relay/RPC work | Join/stop/final scan and completion gate; incomplete work stays unscored |
| No inference / valid completed incorrect patch | Gate vacuously passes / original zero outcome retained |
| Solving timeout/OOM/truncation/cancellation/transport exception | Already-received bounded traces emitted before termination/failure; no reward |
| Successful command / pristine grading | One broker stream of successful output / no public grader sink |

Official protocol references used for this targeted correction are the [OpenAI streaming events](https://developers.openai.com/api/reference/resources/responses/streaming-events), [OpenAI errors](https://developers.openai.com/api/docs/guides/error-codes), [Claude streaming](https://platform.claude.com/docs/en/build-with-claude/streaming), and [Claude errors](https://platform.claude.com/docs/en/api/errors). The pinned Harness `integrations/sandbox_client.py` establishes `follow_exec` output callbacks and final-state behavior; `runtime/sandbox_exec.py` establishes that `exec_kill` sends a signal without awaiting termination. No provider calls were made.

Read-only preflight checked the target, packaged inputs, shared validator/compiler paths, pinned sandbox interfaces and compiler environment. The first combined static/compiler and task-owned static checks both passed. A subsequent targeted shutdown correction added actual relay termination waiting; the correction record was then updated. After these last edits, the same two commands below are rerun, with only their final invocations reported in the controller result:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 .agents/skills/harbor-task-agent/scripts/validate_task.py output/deepswe-rsi-harness --harness-root public-evidence/RSI-Harness
PYTHONDONTWRITEBYTECODE=1 python3 output/deepswe-rsi-harness/tools/static_check.py
```

All three previously fixed instruction warnings remain resolved; no new warnings occurred in the initial correction checks. Final outcomes are in the controller result. Static checks parse task files as data and use only permitted compiler/syntax tools. Live provider failure/retry scenarios, stream fragmentation/cancellation, command failure-output delivery, final resume, build/import/isolation behavior, reference/no-op scores and runtime/cost/cadence remain execution-validation work for `harbor-task-validator`. The supplied review's self-reported provenance, transformed/mirror contamination, pretraining exposure, provider evolution and malicious-patch/grader limitations remain accepted residual risks. No attestation, exhaustive parser proof or public self-check parity was added. No measured execution or independent re-review success is claimed.

## Original generation record (round 0)

Scope: exactly Stages 7–8. This is the single Generator final review, not an independent review. Correction count for the controller is 0. Stages 1–6 and Stage 9 were not repeated or performed. No environment, task workload, Solution, evaluator, baseline, GPU job or real Agent was run.

The selected destination was absent immediately before creation and remains the same non-symlink task directory, `output/deepswe-rsi-harness`. Every authored file is inside it. Controller inputs and pinned Harness evidence were read-only.

## Contract and terminal-path trace

The official DeepSWE/Pier commits, 113-task corpus, explicit 34-task development roster, primary Codex reference and Claude comparator match the bound confirmation. Archive membership, original verifier/collect deadlines, dependency lock and package sizes are checked as data by `tools/static_check.py`. The complete upstream archive is Judge-only; the build context contains only sanitized development metadata/instructions, public tooling and the filtered Pier source archive. Licensing stays with the packaged sources.

Docker build/install operations precede WORKDIR closure. The resulting three top-level paths satisfy the same public and Judge structural gate: empty candidate/research directories and the explicit noop manifest. Solution only materializes released payloads/configuration in candidate paths. Normal submissions score only the frozen candidate. Work performs all candidate-producing research; Judge performs episode solving and fixed scoring, not research-harness production.

`test.sh` → isolated trusted `launch.py` imports → independent candidate gate → known-contamination gate → isolation preflight → exact roster/image-lock checks → scoped worker and offline solving child → original committed binary patch collection → destruction of solving child → pristine grading child with original assets/entrypoint → binary outcome → complete membership → finite absolute fraction → one exclusive final reward write. No-op follows the same real collection/grading path. Completed incorrect patches contribute zero. Candidate invalidity, compilation/runtime failure, timeout, incomplete grading, upstream sentinels, infrastructure and cleanup failures cannot reach the reward ending.

All candidate diagnostics carry a stable field/path/condition for structural failures. Known-copy diagnostics identify only the candidate-owned path and public rule, never the hidden match. Candidate streams are JSON-encoded and visible during development. Actual hidden grader streams stay inside bounded private buffers/children and are deleted on teardown. Accounting is emitted even on an unscored episode. Final records are emitted only by the trusted evaluator, while candidate traces are suppressed in the operator-only final run.

## Findings closed

- The policy initially requested eight concurrent image jobs; the pinned Harness permits four. Both grants now use four, and the adapter bounds pull jobs independently of eight live episodes. The compiler accepted both phase grants.
- Static instruction warnings about the baseline label, reproduction status and submission-checklist heading were fixed with explicit table rows/headings.
- Pinned sandbox API return shapes are followed: image handles come from `result.image.handle`, environments become `ready`, and complete execs must be `exited`, untruncated and free of OOM records. The adapter implements all pinned Pier abstract environment methods.
- Episode scratch ancestors and public input stages explicitly restore traversal/read modes after restrictive umask creation. Candidate runtime scratch is a narrow per-worker write grant. Concurrent workers require supported filesystem isolation; they never receive provider credentials, full sandbox credentials or grading inputs.
- Provider streaming uses a separate bounded executor so callbacks cannot deadlock waiting for sandbox-transfer threads. Headers, chunks and completion markers become visible atomically. Cancellation and the shared deadline close upstream sockets. Relay task failures are observed and cleanup always attempts environment destruction.
- Native Codex uses its pinned custom-provider configuration to select Responses HTTP streaming with WebSockets disabled; this is a transport adaptation. Pinned Pier command/model/effort behavior remains, including Claude's existing EnterPlanMode exclusion and the confirmed disabled web search. Client-executed tool search is retained; hosted retrieval and remote media are rejected.
- The exact Claude npm release requires its native-binary postinstall step. The Docker build retains that official installation step; no install or postinstall runs during generation or evaluation. Codex's exact optional platform payload is installed alongside its launcher.
- Provider response/item history belongs to one episode; shared conversations and detached background inference are refused. Every observed request/retry records usage, elapsed time and unknown cost explicitly. Source/model declarations remain separate from scoring authority.
- Final artifact identity includes candidate, manifest and research/provenance bytes. The copied artifact is rechecked before execution. The host driver uses the real Harness production Docker/broker/firewall/lease path with a non-research oracle. Trusted completed episodes survive interruption and are never selected by best score. Recorded failures require an operator-established infrastructure diagnosis before explicit logged retry; candidate failures do not authorize repeats. No partial accuracy is published.
- Manifest parsing rejects duplicate/non-finite JSON, escaping executable paths and symlink cycles. Added dependencies remain candidate-contained. Preparation probes propagate failed Git integrity commands rather than interpreting an empty failed command as a clean image.

Changed paths and their direct dependents were inspected together: gate/manifest/starting-state/Solution, adapter/relay/provider/worker/evaluator, preparation/image-lock consumer, final checkpoint writer/reader, and README/instruction/policy. Ray/vLLM and lm-eval conditional rules do not apply.

## Final validation and execution boundary

After all review-driven edits, run the following exact single-line commands; their final outcomes are reported in the controller generation result:

```bash
python3 .agents/skills/harbor-task-agent/scripts/validate_task.py output/deepswe-rsi-harness --harness-root public-evidence/RSI-Harness
python3 output/deepswe-rsi-harness/tools/static_check.py
```

These inspect files, compile the task and proposed sandbox policy, parse Python/JSON/TOML and archives, and check shell/JavaScript syntax without executing task code. Actual import/launcher execution, builds, image/digest/source probes, broker enforcement, credentials, both reference CLIs, baseline/no-op scoring, cancellation/cleanup, final resume, runtime/cost, resource limits and cadence remain for `harbor-task-validator`.

Accepted residual limitations are the confirmation's self-reported provenance, transformed/mirror contamination, pretraining exposure, provider evolution, and malicious-patch/test-framework exploits. No measured baseline, variance, throughput, cost, attestation, or independent-review result is claimed.
