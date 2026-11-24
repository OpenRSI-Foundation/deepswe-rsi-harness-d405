# Known pitfalls

Consult these diagnostic references when symptoms or configuration match the
task. Confirm the suspected cause before a task-local repair; using a named
framework alone does not call for a probe or configuration change.

## Python packaging inside the image

- **Build backend missing under `--no-build-isolation`**: a pinned source
  package that declares `poetry-core`, `hatchling`, `flit-core`, or
  `scikit-build-core` can fail when the backend is absent. Check: compare the
  source's `pyproject.toml` `[build-system]` with the build
  environment. Fix: install the backend for the build step only and remove it
  afterwards, or keep it in the lock.
- **Editable-layout packages**: packages whose `__init__` reads files relative
  to the source tree (`config/extension.toml`, data next to the package) break
  when those files are unavailable in a regular wheel. Check: failing import
  and expected file paths. Fix: `pip install -e` from the immutable checkout,
  then clean the tree so it stays pristine.
- **Incomplete dependency closure with `--no-deps`**: any module imported
  lazily by a dependency (for example `ray` imported by `rl_games.common.vecenv`)
  may be absent when omitted from the lock. Check: failing import against the
  lock and installed distributions. Fix: pin the missing distributions and
  their dependencies, then refresh the lock hash the evaluator checks.
- **RECORD checks and `.pyc` files**: some wheels ship `__pycache__/*.pyc`
  with digests in `RECORD`; installer recompilation can cause byte-check
  mismatches. For recompiled `.pyc` mismatches, skip `.pyc` entries; keep
  verifying sources and binaries.
- **Missing system libraries on slim bases**: CUDA/Omniverse/torch shared
  objects can fail to load without libraries such as `libgomp1`, `libatomic1`,
  `libgl1`, `libegl1`, `libvulkan1`, or `libglib2.0-0`. Check: `ldd` on the
  failing shared object. Fix: add apt packages supplying the missing libraries.

## Subprocess workers

- **Buffered stdout under `python -I`**: isolated mode ignores
  `PYTHONUNBUFFERED`; a worker that dies by a hard exit loses everything still
  buffered, which can look like "exited 0 with no output". Check: worker flags
  and exit path. Fix: run workers with `-u`.
- **`finally` blocks that end the process**: when the cleanup path calls
  something that terminates the interpreter (see Isaac Sim below), an
  exception raised inside the `try` never reaches an outer handler. Fix: write
  results and tracebacks to disk inside the `try`/`except` before cleanup;
  make the parent read a result file, not the exit code alone.
- **`pkill -f` self-kill**: a stop hook or cleanup that matches its own command
  line (for example a prompt passed in argv) kills the Agent. Fix: feed prompts
  on stdin; match on a unique process marker.

## Isaac Sim / Isaac Lab

- **Multi-GPU foundation on IOMMU hosts**: with several GPUs visible, Kit runs
  a CUDA peer-to-peer validation that can abort the process (`Cuda failure ...
  peer access is already enabled`). Fix: one Kit per GPU with
  `AppLauncher(..., device="cuda:N", multi_gpu=False)`, as Isaac Lab's own
  distributed training does; set `torch.cuda.set_device` after launch.
- **`SimulationApp.close()` ends the process**: nothing after it runs, and an
  exception in flight is swallowed. Fix: see "Subprocess workers".
- **`pxr` at build time**: pip Isaac Sim ships USD Python bindings inside the
  `omni.usd.libs` extension. For build-time import failures caused by missing
  extension paths, set `PYTHONPATH=<ext>` and `LD_LIBRARY_PATH=<ext>/bin`,
  not a foreign `usd-core`.
- **Core MDL references**: bare material references such as `OmniPBR.mdl` are
  resolved from Kit's MDL search path, not the layer directory; an asset mirror
  should skip these references instead of downloading them.
- **Observation dicts**: `RlGamesVecEnvWrapper` returns `{"obs", "states"}`
  when the task has critic states. Player-side code expecting an observation
  tensor must unwrap `["obs"]` for this return shape.
- **Inference mode**: stepping the environment under
  `torch.inference_mode()` turns its buffers into inference tensors and breaks
  the next in-place reset. Fix: use `torch.no_grad()`.

## vLLM / Ray

- **vLLM host-address selection failure**: for startup or worker-communication
  failures, check the selected Judge address and available interfaces. If
  address selection is the cause, resolve exactly one non-loopback Judge IPv4
  and export `VLLM_HOST_IP` before framework start; fail clearly if it cannot
  be resolved instead of falling back to `0.0.0.0`.
- **Ray binding in a `no-network` container**: if cluster initialization fails
  in this configuration, check the selected interface with a one-node
  `ray.init`. If interface selection is the cause, bind the container interface
  explicitly.

## Docker and the Harness

- **Docker API read timeout**: the Python SDK default is 60 s; committing a
  Work rootfs that holds tens of GB can take minutes. For `Read timed out`
  during commit, check rootfs size and the bundled Harness timeout.
  OpenRSI-Index PR #83 or later raises it (old `738c0ea`, now `a39ce4e`);
  older copies can time out and leak the committed image. Report a confirmed
  Harness timeout limitation.
- **Large Work rootfs**: caches placed on the container filesystem
  (`HF_HOME`, `/tmp` scratch, checkpoints) can make Judge snapshots slow and
  large. Check cache locations and sizes; move contributing caches to the
  workspace volume or a declared cache path.
- **Judge relies on Agent tooling**: the oracle's Work image, and so its clean
  Judge, has no Agent CLI or node. A `test.sh` that needs them fails only
  here. Fix: bake the tool into the task image.
- **Judge GPU declarations vs use**: an evaluator hard-wired to `cuda:0`
  gains nothing from a larger declaration. For this mismatch, either parallelize
  candidates across the declared devices or declare one.
- **release-all pools**: with a pool equal to the Work GPU count, Work is
  paused during scoring; for this configuration, the task instruction must tell
  the Agent to stop GPU processes before `rsi-submit`.
