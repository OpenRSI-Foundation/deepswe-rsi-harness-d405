# Candidate interface version 1

`/workspace/candidate.json` has `version: 1`, `mode: "noop"` or `"custom"`, an `entrypoint` argument vector, `dependencies`, `providers`, and `provenance`. Noop has an empty entrypoint. Custom entrypoint[0] is an executable beneath `/workspace/candidate/`; a shebang may select a baked system interpreter, including `/opt/pier/.venv/bin/python`. Every additional dependency must be in the candidate tree. `dependencies` lists every immediate child of that tree. Contained symlinks are supported; escaping links and special files are rejected. The manifest is at most 1 MiB and the workspace at most 100000 entries.

Each provider declaration is `{"provider":"openai","model":"gpt-5.6-sol","settings":{"reasoning_effort":"max"}}` or an analogous declared Anthropic model/settings object. Arbitrary available approved-provider models/settings may be declared. Every source declaration has nonempty `source` and `use` strings, including generated data. Declarations are self-reported provenance, not attestation.

The worker receives a disposable candidate copy through `CANDIDATE_ROOT`, current task JSON through `DEEPSWE_TASK_JSON`, private `HOME`/`TMPDIR`, and a connected Unix socket descriptor through `DEEPSWE_RPC_FD`. Entrypoint arguments containing `/workspace/candidate/` are remapped to the disposable copy. Use the supplied paths; do not hard-code a scratch directory. The worker runs with `rsi-isolate --no-network` and no provider or sandbox credentials. Exit zero after sending `done`; any crash, timeout or absent completion is unscored.

RPC is a four-byte unsigned network-order length followed by UTF-8 JSON, with the same framing for responses. Maximum frame is 24 MiB. Serialize requests on a connection. Response is `{"result":...}` or `{"error":"actionable detail"}`. Unknown operations and invalid frames invalidate the episode. Operations:

| Request | Result |
| --- | --- |
| `{"operation":"exec","command":"git status","cwd":"/app","env":{},"timeout_sec":60}` | `stdout`, `stderr`, integer `return_code`; runs only in this task's offline child. Nonzero tool commands may be handled by your harness. |
| `{"operation":"write","path":"/app/file","data":"BASE64"}` | Writes at most 16 MiB into this task's child. |
| `{"operation":"read","path":"/app/file"}` | `data`, base64-encoded bounded child file. |
| `{"operation":"inference","path":"/v1/responses","body":{"model":"DECLARED MODEL","input":"..."}}` | HTTP `status`, safe `headers`, base64 `body`, and trusted `inference` completion/error/retry metadata. Supports approved Messages/Responses operations, buffered for this RPC. Every request/retry is accounted. |
| `{"operation":"provision_reference"}` | Copies the candidate's `payload/` and `relay.js` into the child, starts its loopback HTTP relay, and sets PATH. The provided reference uses this for native CLI SSE streaming. |
| `{"operation":"done"}` | Completes this worker's solving phase. Commit `/app` changes first. |

The broker owns handles, selects the task, enforces the shared deadline and collects the patch. It destroys the solving child before creating a pristine grading child. It never exposes grading files through this protocol. You may implement your own IPC client in any language; `/opt/deepswe/reference.py` contains a small Python example and the exact pinned reference behavior. No candidate self-reported outcome or trace is scoring authority.

HTTP errors, provider error events, missing terminal events, incomplete responses, credential/transport errors and canceled requests remain unscored unless a subsequent identical normalized request completes within the shared episode deadline. JSON whitespace/key order and relay transport IDs do not affect retry identity; provider, method, path/query, request body and forwarded protocol headers do. Retry links and recovery are broker-owned; changing the prompt/model or sending `done` cannot clear a failed attempt. Transport failures return an RPC `error` with `inference_failure: true` and leave the channel available for retries. HTTP error responses retain their status/body. Native CLIs retain the same HTTP/SSE interface and may retry through the relay. No inference is required for a no-op candidate.

Solving-command stdout/stderr is streamed to development feedback up to 16 MiB per stream, followed by a command termination record including timeout/OOM/truncation or transport/cancellation diagnostics. Successful command output is still returned through RPC but is not separately replayed into feedback by the broker. Pristine-grader output stays protected.

For public Work diagnostics, `research-fetch --development-images` returns the prepared development image digests. Work's injected `rsi-sandbox` supports offline `pull`, `up`, `exec`, `cp`, and `rm` with at most two live children. Save any resulting candidate artifact inside `/workspace` before submission. Only the fixed Judge returns formal full-roster scores.
