# DeepSWE harness research

## Overview

Research a complete coding harness from an empty candidate tree. Work produces the frozen executable artifact; clean-image Judge evaluates its committed patches on 34 fixed tasks. An operator-only final procedure evaluates all 113 tasks and reports the reused 34 and remaining 79 separately.

## Baseline and evidence

The semantic source is [DeepSWE at 0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea](https://github.com/datacurve-ai/deep-swe/tree/0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea). Its complete archive, license and original evaluation assets are under `tests/`. [Pier at b26211ed2bbee6d145f6b8c5b80e39f18b296f08](https://github.com/datacurve-ai/pier/tree/b26211ed2bbee6d145f6b8c5b80e39f18b296f08) supplies the installed-agent behavior; its source and lock are packaged in `environment/pier.tar.gz`. Upstream licenses remain in those archives; DeepSWE's PROVENANCE.md lists the individual permissive upstream licenses.

The primary baseline is [Codex 0.172.0 / rust-v0.172.0](https://github.com/openai/codex/tree/3d86e43b075adeba2193ec5c22ac92f55afd82e6), model `gpt-5.6-sol`, effort `max`. The additional comparator is [Claude Code 2.1.331](https://github.com/anthropics/claude-code/tree/bd07f2a121a9d16f2b00b209bbdf50c1bc46fb91), model `claude-opus-5`, effort `high`. The build installs the exact released npm payloads; `solution/solve.sh` only copies them into the candidate artifact, selects Codex, and supplies `candidate/comparator-claude.json`. To validate Claude separately after baseline materialization, copy that manifest to `/workspace/candidate.json`. Neither Solution trains, evaluates nor submits.

Matched results are **not reported and not reproduced**. Public 73%/74% results use mini-swe-agent rather than these CLIs, with a different Claude effort; they are context, not matched measurements. The 60–75% expectation is unmeasured. Candidate-only submissions never rerun a live baseline.

## Environment and evaluation

The Dockerfile uses official Python 3.12 and Node 22 Bookworm images, Linux x86-64, and root Work. Pier's frozen lock selects Harbor 0.5.0 in `/opt/pier/.venv`; Harbor 0.21.0 is separately installed in `/opt/harbor`. The final WORKDIR closure creates only empty candidate/research directories and the explicit noop manifest. All trusted tooling lives outside `/workspace`. No hidden benchmark bytes enter an image layer.

`tests/launch.py` imports only the trusted injected evaluator directory. `tests/managed.py` implements Pier's environment interface with the Harness-injected standard-library v2 sandbox client. Workers run through `rsi-isolate`, see only their candidate/current task and scoped IPC, and have no network or secrets. Native CLI HTTP/SSE uses `environment/public/relay.js` in the offline child, with bounded copy/exec transport to the credential-owning proxy. Responses streaming and same-service operations follow [official OpenAI streaming documentation](https://developers.openai.com/api/docs/guides/streaming-responses) and the [Responses reference](https://developers.openai.com/api/reference/typescript/resources/responses). Episode web search and provider-hosted retrieval are disabled.

Each episode preserves the original `/app` base, instruction, 10,800-second solving deadline, 300-second committed binary patch collection, and pristine `/bin/bash /tests/test.sh` verification within 1,800 seconds. Task and grader are serial, with eight episodes maximum in parallel. Reward is successes/34, maximized. Completed incorrect patches count zero; all invalidity, crashes, compilation failures, timeout, infrastructure failures, negative upstream sentinels and incomplete membership remain unscored. Only a completely valid evaluation publishes one `reward.json`.

Trusted provider accounting gates patch collection after both RPC and native-relay requests settle. HTTP errors, credential/transport failures, provider error events and missing/incomplete completion remain unscored even if the worker sends `done` and exits zero. Retries remain available within the episode deadline: a later completed request with the same normalized provider/method/path/query/body/protocol headers records explicit recovery links; an unrelated success cannot erase a failure. Requests with no inference remain valid. The gate follows the providers' [Responses completion/error events](https://developers.openai.com/api/reference/resources/responses/streaming-events), [OpenAI service errors](https://developers.openai.com/api/docs/guides/error-codes), [Messages stream endings](https://platform.claude.com/docs/en/build-with-claude/streaming), and [Claude stream/HTTP errors](https://platform.claude.com/docs/en/api/errors).

Development logs expose task IDs, outcomes, bounded error classes, candidate traces and accounting. Protected upstream grader streams are captured in disposable private scratch. All emitted outer stdout/stderr and Harness footer are visible. The public `/usr/local/bin/validate-candidate --json` is read-only and checks structure/declarations only; Judge reruns its own gate. Exact known answer-asset copies are rejected without naming hidden matches.

Candidate solving commands stream captured stdout/stderr (16 MiB per stream) before propagating timeout, OOM, truncation, cancellation or transport failure. Each command ends with a termination record and available byte counts; successful output is not replayed by the broker. Grader executions have no public sink. Final checkpoints use evaluator revision 2 so records predating these corrections cannot bypass the completion gate; the scientific protocol and image identities are unchanged.

| Resource | Bound |
| --- | --- |
| Node | 32 CPUs, 128 GiB, zero GPUs |
| Each outer service | 4 CPUs, 16384 MiB, 262144 MiB planning storage |
| Each child | 2 CPUs, 8192 MiB, 20480 MiB planning storage, network none |
| Live children | Work 2; Judge 8; one service each |
| Reservation | 28 CPUs; 114688 MiB plus 2048 MiB broker headroom and metadata |
| Timeouts | Build 7200 s; Judge 72000 s; Agent 172800 s |
| Storage | Provisionally 2 TiB host disk; outer storage is not a hard quota |

Five waves require 64500 seconds (17.92 hours) before overhead. Two estimated loops of two hours Work plus twenty hours Judge, with four hours margin, fit a provisional 48-hour window. Submissions are uncapped; operational quotas are not a scientific submission cap. Final evaluation needs 53.75 hours before overhead; the operator driver allows 216000 seconds plus materialization margin and checkpoints completed episodes across windows. Default 1-GiB shared memory and all cadence/cost estimates await execution validation. No over-budget marker is justified by incomplete estimates alone.

## Run and validate

Use a supported Linux Docker host and the pinned Harness checkout supplied to generation. Preparation, broker startup, builds and execution below belong to the separate execution-validation stage. Set `TASK` to this absolute directory and `STATE` to a new operator-private directory outside the task and adaptive workspace. Set actual `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` only in the operator environment. Do not pass them as Work's Agent credential.

```bash
mkdir -m 700 "$STATE"
python3 "$TASK/operator/prepare.py" --output "$STATE/images.json"
export DEEPSWE_IMAGE_LOCK="$(cat "$STATE/images.json")"
```

Preparation resolves exactly the 113 approved ECR tags to real digests, pre-pulls them, inspects architecture/volumes, and probes base commit, cleanliness, absence of reachable/unreachable future history and grading files. It fails closed rather than fabricating an identity. Retain `images.json` unchanged for the run and final report. Review the proposed `operator-policy.toml`: local Docker, ECR pull only, no builds, no child egress, finite lifetime/creation/transfer/log/operation bounds. No Docker socket or published child ports reach Work/Judge.

Start the task-owned broker in a separate operator terminal. `BROKER_BIND` is a real host interface address reachable from the Harness Docker bridge (for example the site's Docker bridge gateway); never use container loopback. The broker creates a new private state directory and run-scoped token. Keep the process alive for the Work run.

```bash
python3 "$TASK/operator/broker.py" --bind "$BROKER_BIND" --port 8765 --state "$STATE/broker" --images "$STATE/images.json"
```

Register that actual endpoint with the supported provider route before Work starts. The Harness pins the endpoint and no-network Work can reach only that provider route. The broker performs normalized URL, DNS/address, redirect and known-content checks for explicit fetch/search, records provenance, rejects CONNECT and hosted-retrieval tools, and supplies upstream keys itself. Hostname filtering alone is not the research boundary.

```bash
export RSI_AGENT_API_BASE_URL="http://$BROKER_BIND:8765/v1"
export RSI_AGENT_API_KEY="$(cat "$STATE/broker/token")"
sudo -E rsi-harness run "$TASK" --agent codex --model "$RSI_MODEL" --reasoning-effort "$RSI_REASONING_EFFORT" --primary-reward reward --score-direction maximize --sandbox-policy "$TASK/operator-policy.toml" --verbose
```

The outer Agent model/effort are operator selectors, independent of benchmark model settings. Do not configure an unrestricted HTTP proxy. Work research uses the broker; Judge calls only `api.openai.com` and `api.anthropic.com` using runtime credential templates. Inspect actual route/path enforcement during validation.

After adaptive research ends, export the chosen complete `/workspace` to an operator-owned frozen artifact directory. Never resume research on final feedback. Run:

```bash
sudo -E python3 "$TASK/operator/final.py" --artifact "$FROZEN_ARTIFACT" --state "$FINAL_STATE" --images "$STATE/images.json" --sandbox-policy "$TASK/operator-policy.toml"
```

The final driver creates an operator-private task instance, uses the same evaluator and Harness production local Docker lifecycle (`ProductionRuntimeServices` → `SandboxBroker`/`docker_env_runtime`/`SandboxLifecycle`), and invokes only the non-research oracle to load the frozen artifact. It removes research/proxy routing, binds checkpoints to the complete artifact and protocol, resumes only incomplete episodes, and releases no partial accuracy. Recover interrupted Harness attempts using their `attempt-N/runtime` and `attempt-N/logs` roots before resuming. A recorded unscored episode requires an established infrastructure cause, one `--retry-infrastructure TASK_ID` per affected task, and `--retry-reason TEXT`; these decisions are logged separately. Candidate failures do not authorize retries. Completed episodes are never selected by best score. Any variability-driven repetition policy must be established prospectively before a new final campaign; the delivered driver implements the initial one-run policy.

Generation checks are static/compiler checks only. The combined check is:

```bash
python3 .agents/skills/harbor-task-agent/scripts/validate_task.py output/deepswe-rsi-harness --harness-root public-evidence/RSI-Harness
python3 output/deepswe-rsi-harness/tools/static_check.py
```

See `generation-review.md` for the final Generator review and validation record. Environment build, actual image metadata/probes, isolation, broker enforcement, both reference CLIs, baseline/no-op scores, final resume/cleanup, provider access, runtime/cost, cadence and a real Agent remain pending for `harbor-task-validator`. No execution result is claimed.

Residual limitations: candidate provenance is self-reported; mirror leakage, transformed contamination, model pretraining exposure, provider evolution, and malicious patch/test-framework exploits cannot be exhaustively excluded. The pristine upstream grader and exact-copy gate do not constitute cryptographic attestation. Upstream verifier outputs are trusted under the confirmed benchmark's residual patch-exploit boundary.
