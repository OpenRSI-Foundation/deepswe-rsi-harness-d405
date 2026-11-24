#!/usr/bin/env python3
"""Publish immutable run-log snapshots; watch the Harness PID without Agent hooks."""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import errno
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

from split_run_log import MAX_CHUNK, IO_BLOCK, _safe_path, split_log, restore_log


class PublicationError(RuntimeError):
    """Publication failed; source logs and the running experiment are untouched."""


TASK_FILES = (
    "agent_output.txt", "agent_prompt.md", "run_agent.log", "started_at",
    "run-plan.json", "evolve_state.json", "final_result.json", "engine_error.json",
)
ROOT_FILES = ("launch.log", "console.log")
REPACK_TIMEOUT = 120
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
# Publication scans only for the exact values of credential-named host variables (and any
# --secret-env names); Harness redaction markers such as [REDACTED] never trigger it.
SECRET_NAME = re.compile(r"TOKEN|PASSWORD|SECRET|API_?KEY|CREDENTIAL|PRIVATE_KEY", re.I)


def _json_write(path, value):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write((json.dumps(value, indent=2, sort_keys=True) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def _git(cwd, *args, env=None, data=None, check=True, timeout=60, config_values=()):
    environment = {k: v for k, v in os.environ.items() if not k.startswith((
        "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX", "GIT_OBJECT", "GIT_ALTERNATE", "GIT_CONFIG",
    ))}
    environment.update({"GIT_TERMINAL_PROMPT": "0", "GIT_LITERAL_PATHSPECS": "1"})
    environment.update(env or {})
    command = ["git"]
    for key, value in config_values:
        if ("\0" in value or "\n" in value or "\r" in value or
                re.search(r"(?:password|token|secret|api[_-]?key|private[_-]?key)\s*=", value, re.I) or
                re.search(r"://[^/@:]+:[^/@]+@", value)):
            raise PublicationError(
                "credential helper configuration may contain an inline secret; "
                "use a non-secret helper command or host credential store")
        command.extend(("-c", f"{key}={value}"))
    command.extend(args)
    try:
        if args[0] == "repack":
            # Stop pack-objects too before releasing the shared-cache lock.
            with subprocess.Popen(command, cwd=cwd, env=environment,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, start_new_session=True) as process:
                try:
                    stdout, stderr = process.communicate(data, timeout=timeout)
                except BaseException:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.communicate()
                    raise
                result = subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
        else:
            result = subprocess.run(command, cwd=cwd, env=environment, input=data,
                                    capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        if args[0] == "repack":
            raise PublicationError(f"git repack timed out after {timeout}s; cache compaction can be retried") from None
        raise PublicationError(f"git {args[0]} timed out after {timeout}s; check connectivity or increase --transfer-timeout-seconds for large transfers") from None
    except OSError:
        raise PublicationError(f"git {args[0]} unavailable; check Git installation/access") from None
    if check and result.returncode:
        # Git stderr can contain credential-bearing URLs or remote hook output.
        raise PublicationError(f"git {args[0]} failed (exit {result.returncode}); check destination, authentication, permissions and remote updates")
    return result


def _read_prefix(path, target):
    """Read exactly the observed size, then verify that prefix; never chase appends."""
    _safe_path(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise PublicationError("artifact is not a regular file")
        remaining = before.st_size
        digest = hashlib.sha256()
        with target.open("xb") as output:
            while remaining:
                block = source.read(min(IO_BLOCK, remaining))
                if not block:
                    raise PublicationError("artifact shrank during snapshot; retry")
                output.write(block)
                digest.update(block)
                remaining -= len(block)
        source.seek(0)
        verify, remaining = hashlib.sha256(), before.st_size
        while remaining:
            block = source.read(min(IO_BLOCK, remaining))
            if not block:
                raise PublicationError("artifact changed during snapshot; retry")
            verify.update(block)
            remaining -= len(block)
        if verify.digest() != digest.digest():
            raise PublicationError("artifact prefix changed during snapshot; retry")
    return digest.hexdigest()


class Publisher:
    def __init__(self, repo, run_dir, remote, branch, *, state_dir=None,
                 chunk_size=MAX_CHUNK, secret_names=(), transfer_timeout_seconds=900):
        self.repo, self.run_dir = _safe_path(repo), _safe_path(run_dir)
        if not NAME.fullmatch(self.run_dir.name) or not NAME.fullmatch(remote):
            raise PublicationError("run ID and remote must be safe single names")
        if type(chunk_size) is not int or not 1 <= chunk_size <= MAX_CHUNK:
            raise PublicationError("chunk size must be between 1 byte and 80 MiB")
        if not math.isfinite(transfer_timeout_seconds) or transfer_timeout_seconds <= 0:
            raise PublicationError("transfer timeout must be positive and finite")
        self.transfer_timeout = transfer_timeout_seconds
        if _git(self.repo, "check-ref-format", f"refs/heads/{branch}", check=False).returncode:
            raise PublicationError("invalid destination branch")
        self.remote, self.branch, self.chunk_size = remote, branch, chunk_size
        self.path = f"logs/runs/{self.run_dir.name}"
        self.state_dir = _safe_path(state_dir or self.repo / ".rsi-harness/log-publication" / self.run_dir.name)
        if self.state_dir == self.run_dir or self.run_dir in self.state_dir.parents:
            raise PublicationError("publisher state must be outside the source logs")
        urls = _git(self.repo, "remote", "get-url", "--push", "--all", remote).stdout.decode().splitlines()
        if len(urls) != 1:
            raise PublicationError("publication requires exactly one confirmed push URL")
        self.url = urls[0]
        parsed = urlsplit(self.url)
        if parsed.scheme in ("http", "https") and (parsed.username or parsed.password):
            raise PublicationError("use a Git credential helper, not credentials in the remote URL")
        if not parsed.scheme and ":" not in self.url:
            self.url = str((self.repo / self.url).resolve())
        helpers = _git(self.repo, "config", "--local", "--get-all", "credential.helper",
                       check=False).stdout.decode().splitlines()
        self.git_auth_config = tuple(("credential.helper", helper) for helper in helpers)
        common_value = _git(self.repo, "rev-parse", "--git-common-dir").stdout.decode().strip()
        common_path = Path(common_value)
        if not common_path.is_absolute():
            common_path = self.repo / common_path
        common_dir = _safe_path(common_path.resolve())
        cache_key = hashlib.sha256(self.url.encode()).hexdigest()
        self.git_dir = _safe_path(common_dir / "rsi-log-publication" / cache_key / "objects.git")
        if self.run_dir == self.git_dir or self.run_dir in self.git_dir.parents:
            raise PublicationError("publisher cache must be outside the source logs")
        run_key = hashlib.sha256(str(self.state_dir).encode()).hexdigest()
        self.refs = f"refs/rsi-runs/{run_key}"
        self.identity = {}
        for key in ("name", "email"):
            value = _git(self.repo, "config", "--get", f"user.{key}", check=False).stdout.decode().strip()
            if not value:
                raise PublicationError(f"git user.{key} is not configured for this repository; set the confirmed publication identity before starting the publisher")
            self.identity[f"GIT_AUTHOR_{key.upper()}"] = value
            self.identity[f"GIT_COMMITTER_{key.upper()}"] = value
        names = {key for key in os.environ if SECRET_NAME.search(key)} | set(secret_names)
        values = {os.environ[key] for key in names if os.environ.get(key)}
        # RSI_AGENT_EXTRA_ENV may carry a credential not exported separately.
        for item in os.environ.get("RSI_AGENT_EXTRA_ENV", "").split(","):
            key, separator, value = item.partition("=")
            if separator and SECRET_NAME.search(key) and value:
                values.add(value)
        explicit = {os.environ[key] for key in secret_names if os.environ.get(key)}
        self.secrets = tuple(value.encode() for value in values if len(value) >= 8 or value in explicit)
        self.binding = {"repo": str(self.repo), "run_dir": str(self.run_dir),
                        "url": self.url, "branch": branch, "chunk_size": chunk_size}

    def preflight(self):
        result = _git(self.repo, "ls-remote", "--exit-code", "--heads", self.url,
                      f"refs/heads/{self.branch}", check=False, timeout=self.transfer_timeout)
        if result.returncode == 2:
            raise PublicationError(
                f"remote branch '{self.branch}' does not exist on '{self.remote}'; "
                "select an existing branch or explicitly create/push the intended branch, then retry; "
                "the publisher will not create it automatically")
        if result.returncode:
            raise PublicationError(
                f"cannot access remote '{self.remote}' to check branch '{self.branch}' "
                f"(git ls-remote exit {result.returncode}); check the remote URL, host authentication, "
                "repository permissions and network; branch existence could not be determined")
        return {"status": "ready", "remote": self.remote, "branch": self.branch}

    def _artifacts(self):
        if not self.run_dir.is_dir():
            raise PublicationError("run directory is not present yet")
        for name in ROOT_FILES:
            path = self.run_dir / name
            if path.exists() or path.is_symlink():
                yield path
        for task in sorted(self.run_dir.iterdir()):
            if task.name.startswith(".") or task.name.endswith(".parts") or not task.is_dir():
                continue
            if not NAME.fullmatch(task.name):
                raise PublicationError("unsafe task directory name")
            _safe_path(task)
            for name in TASK_FILES:
                path = task / name
                if path.exists() or path.is_symlink():
                    yield path
            feedback = task / "feedback"
            if feedback.exists():
                _safe_path(feedback)
                for path in sorted(feedback.iterdir()):
                    if NAME.fullmatch(path.name) and path.suffix == ".log":
                        yield path
            submissions = task / "submissions"
            if submissions.exists():
                _safe_path(submissions)
                for submission in sorted(submissions.iterdir()):
                    if not NAME.fullmatch(submission.name):
                        continue
                    _safe_path(submission)
                    for name in ("report.json", "test_output.txt"):
                        path = submission / name
                        if path.exists() or path.is_symlink():
                            yield path
            # The Judge's durable reward per submission; verifier scratch stays private.
            verifier = task / "verifier"
            if verifier.exists():
                _safe_path(verifier)
                for round_dir in sorted(verifier.iterdir()):
                    if not NAME.fullmatch(round_dir.name):
                        continue
                    _safe_path(round_dir)
                    path = round_dir / "reward.json"
                    if path.exists() or path.is_symlink():
                        yield path

    def _scan(self, path):
        if not self.secrets:
            return
        overlap = max(len(value) for value in self.secrets)
        tail = b""
        with path.open("rb") as stream:
            while block := stream.read(IO_BLOCK):
                data = tail + block
                if any(value in data for value in self.secrets):
                    raise PublicationError("host credential value found in publication snapshot; review locally before retrying (value withheld)")
                tail = data[-overlap:]

    def _snapshot(self, root, final):
        ignores, count = [], 0
        for source in self._artifacts():
            relative = source.relative_to(self.run_dir)
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = _read_prefix(source, target)
            self._scan(target)
            count += 1
            if target.stat().st_size > self.chunk_size:
                parts = split_log(target, self.chunk_size)
                restored = target.with_name(target.name + ".verified")
                restore_log(parts, restored)
                checksum = hashlib.sha256()
                with restored.open("rb") as stream:
                    while block := stream.read(IO_BLOCK):
                        checksum.update(block)
                if checksum.hexdigest() != digest:
                    raise PublicationError("split snapshot failed byte-for-byte verification")
                restored.unlink()
                target.unlink()  # Only the private snapshot, never the source log.
                ignores.append("/" + relative.as_posix())
        if not count:
            raise PublicationError("no publishable run artifacts yet")
        (root / ".gitattributes").write_text("* -text -filter\n")
        (root / ".gitignore").write_text("".join(name + "\n" for name in sorted(ignores)))
        _json_write(root / "publication.json", {"version": 1, "run_id": self.run_dir.name,
                                               "phase": "final" if final else "running"})

    @contextlib.contextmanager
    def _locked(self, name="lock", directory=None, wait_seconds=0, *, shared=False):
        directory = directory or self.state_dir
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        _safe_path(directory)
        with (directory / name).open("a") as lock:
            deadline = time.monotonic() + wait_seconds
            while True:
                try:
                    fcntl.flock(lock, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise PublicationError("another publisher owns this run/cache lock; retry without starting a duplicate") from None
                    time.sleep(0.05)
            yield

    def _prepare_cache(self):
        # Shared only within this Git repository and push destination; never use
        # the active checkout's index or object database for snapshot commits.
        with self._locked("init.lock", self.git_dir.parent, wait_seconds=30):
            ready = self.git_dir / "rsi-cache-ready"
            if ready.is_file():
                return
            _git(self.git_dir.parent, "init", "--bare", str(self.git_dir))
            _git(self.git_dir, "config", "core.hooksPath", str(self.git_dir.parent / "no-hooks"))
            _git(self.git_dir, "config", "gc.auto", "0")
            _git(self.git_dir, "config", "maintenance.auto", "false")
            ready.touch(mode=0o600)

    def _fetch(self):
        ref = f"{self.refs}/remote"
        result = _git(self.git_dir, "fetch", "--no-tags", "--no-write-fetch-head", "--no-auto-maintenance",
                      self.url, f"+refs/heads/{self.branch}:{ref}", check=False,
                      timeout=self.transfer_timeout, config_values=self.git_auth_config)
        if result.returncode:
            self.preflight()  # Also diagnose a branch removed after startup.
            raise PublicationError(
                f"git fetch failed (exit {result.returncode}) for existing branch '{self.branch}' "
                f"on '{self.remote}'; check local cache permissions/free disk and network, then retry")
        return _git(self.git_dir, "rev-parse", ref).stdout.decode().strip()

    def _pin_state(self, state):
        # Old per-run caches may contain a rejected push referenced only by JSON.
        # Import those objects before retrying; do not delete legacy caches.
        for kind in ("last", "pending"):
            commit = state.get(f"{kind}_commit")
            if not commit:
                continue
            if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
                raise PublicationError("invalid commit in publisher state; review before retrying")
            ref = f"{self.refs}/{kind}"
            if _git(self.git_dir, "cat-file", "-e", f"{commit}^{{commit}}", check=False).returncode:
                legacy = _safe_path(self.state_dir / "objects.git")
                if not legacy.is_dir():
                    raise PublicationError("retry commit missing from shared and legacy caches; restore publisher state/cache before retrying")
                _git(self.git_dir, "fetch", "--no-tags", "--no-write-fetch-head", "--no-auto-maintenance",
                     str(legacy), f"{commit}:{ref}", timeout=self.transfer_timeout)
            _git(self.git_dir, "update-ref", ref, commit)

    def _tree(self, git_dir, revision):
        result = _git(git_dir, "rev-parse", "--verify", f"{revision}:{self.path}", check=False)
        return result.stdout.decode().strip() if result.returncode == 0 else None

    def _compact_cache(self, state_file, state, result):
        if not result["final"] or state.get("compacted_commit") == result["commit"]:
            return
        try:
            # Never wait for another run's upload, and never prune retry objects.
            with self._locked("maintenance.lock", self.git_dir.parent):
                _git(self.git_dir, "repack", "-a", "-d", "--keep-unreachable",
                     "--threads=1", "--window-memory=64m", timeout=REPACK_TIMEOUT)
                state["compacted_commit"] = result["commit"]
                _json_write(state_file, state)
        except (PublicationError, OSError, ValueError):
            result["warning"] = (
                "cache compaction deferred or failed; final upload succeeded. "
                "Check free disk/cache access and retry once --final after other publishers finish")
        try:
            _json_write(self.state_dir / "last-attempt.json", {**result, "at": time.time()})
        except OSError:
            result.setdefault("warning", "final upload succeeded, but cache maintenance status could not be saved; retry once --final")

    def _publication_final(self, state, requested):
        """Resolve finality under the publication lock; cluster runs may resume."""
        return bool(requested or state.get("final") or state.get("pending_final"))

    def _publish(self, final):
        with self._locked(), contextlib.ExitStack() as cache_access:
            state_file = self.state_dir / "state.json"
            state = json.loads(state_file.read_text()) if state_file.exists() else {"binding": self.binding}
            if state.get("binding") != self.binding:
                raise PublicationError("publisher destination changed; use the previously confirmed binding")
            final = self._publication_final(state, final)
            cache_access.enter_context(self._locked("maintenance.lock", self.git_dir.parent,
                                                     wait_seconds=REPACK_TIMEOUT + 5, shared=True))
            self._prepare_cache()
            git_dir = self.git_dir
            base = self._fetch()
            self._pin_state(state)
            remote_tree = self._tree(git_dir, base)
            if remote_tree not in (None, state.get("last_tree"), state.get("pending_tree")):
                raise PublicationError("remote changes conflict with this run's logs; review before resuming")
            if remote_tree is None and state.get("last_tree"):
                raise PublicationError("remote run logs were removed; review before resuming")
            with tempfile.TemporaryDirectory(prefix="snapshot-", dir=self.state_dir) as directory:
                temporary = Path(directory)
                snapshot = temporary / "files"
                snapshot.mkdir()
                self._snapshot(snapshot, final)
                environment = {**self.identity, "GIT_INDEX_FILE": str(temporary / "index")}
                _git(git_dir, "read-tree", base, env=environment)
                previous = _git(git_dir, "ls-tree", "-r", "--name-only", "-z", base, "--", self.path).stdout
                if previous:
                    removals = b"".join(b"0 " + b"0" * 40 + b"\t" + name + b"\0"
                                        for name in previous.split(b"\0") if name)
                    _git(git_dir, "update-index", "-z", "--index-info", data=removals, env=environment)
                for path in sorted(snapshot.rglob("*")):
                    if not path.is_file():
                        continue
                    if path.stat().st_size > MAX_CHUNK:
                        raise PublicationError("snapshot contains an unsplit file larger than 80 MiB")
                    blob = _git(git_dir, "hash-object", "-w", "--no-filters", str(path)).stdout.decode().strip()
                    name = f"{self.path}/{path.relative_to(snapshot).as_posix()}"
                    _git(git_dir, "update-index", "--add", "--cacheinfo", f"100644,{blob},{name}", env=environment)
                tree = _git(git_dir, "write-tree", env=environment).stdout.decode().strip()
                if tree == _git(git_dir, "rev-parse", f"{base}^{{tree}}").stdout.decode().strip():
                    commit = state.get("pending_commit") or state.get("last_commit") or base
                    if _git(git_dir, "merge-base", "--is-ancestor", commit, base, check=False).returncode:
                        commit = base
                    status = "unchanged"
                else:
                    commit = _git(git_dir, "commit-tree", tree, "-p", base, "-m",
                                  f"logs: {'final' if final else 'periodic'} snapshot {self.run_dir.name}",
                                  env=environment).stdout.decode().strip()
                    _git(git_dir, "update-ref", f"{self.refs}/pending", commit)
                    state.update(pending_tree=self._tree(git_dir, commit), pending_commit=commit,
                                 pending_final=bool(final))
                    _json_write(state_file, state)
                    _git(git_dir, "push", self.url, f"{commit}:refs/heads/{self.branch}",
                         timeout=self.transfer_timeout, config_values=self.git_auth_config)
                    verified = self._fetch()
                    _git(git_dir, "merge-base", "--is-ancestor", commit, verified)
                    status = "uploaded"
                _git(git_dir, "update-ref", f"{self.refs}/last", commit)
                state.update(last_tree=self._tree(git_dir, commit), last_commit=commit,
                             last_success_at=time.time(), final=bool(final))
                state.pop("pending_tree", None)
                state.pop("pending_commit", None)
                state.pop("pending_final", None)
                _json_write(state_file, state)
                _git(git_dir, "update-ref", "-d", f"{self.refs}/pending")
                result = {"status": status, "commit": commit, "final": bool(final)}
                _json_write(self.state_dir / "last-attempt.json", {**result, "at": time.time()})
                cache_access.close()  # Release shared access before trying exclusive maintenance.
                self._compact_cache(state_file, state, result)
                return result

    def publish(self, final=False):
        try:
            return self._publish(final)
        except (PublicationError, OSError, ValueError) as error:
            # File contents, filenames, and OS diagnostics may contain secrets.
            if isinstance(error, PermissionError):
                detail = ("publication permissions denied; check log/cache/state access. "
                          "For a root/sudo Harness, run the publisher with matching root privileges "
                          "and confirmed Git identity/authentication; keep the same publication user on retries")
            else:
                detail = (str(error) if isinstance(error, PublicationError) else
                          f"snapshot unavailable ({type(error).__name__}); check log permissions, symlinks and publisher state")
            try:
                _json_write(self.state_dir / "last-attempt.json",
                            {"status": "blocked", "error": detail, "final": bool(final), "at": time.time()})
            except OSError:
                pass  # Report the original failure even when state itself is unwritable.
            raise PublicationError(detail) from None


class _DarwinBsdInfo(ctypes.Structure):
    # Public macOS proc_bsdinfo ABI from <sys/proc_info.h>.
    _fields_ = [
        (name, ctypes.c_uint32) for name in (
            "flags", "status", "xstatus", "pid", "ppid", "uid", "gid",
            "ruid", "rgid", "svuid", "svgid", "reserved",
        )
    ] + [
        ("comm", ctypes.c_char * 16), ("name", ctypes.c_char * 32),
        ("nfiles", ctypes.c_uint32), ("pgid", ctypes.c_uint32),
        ("pjobc", ctypes.c_uint32), ("tdev", ctypes.c_uint32),
        ("tpgid", ctypes.c_uint32), ("nice", ctypes.c_int32),
        ("start_sec", ctypes.c_uint64), ("start_usec", ctypes.c_uint64),
    ]


def _darwin_process_identity(pid):
    """Use kernel start time at microsecond resolution, not PID existence alone."""
    library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    query = library.proc_pidinfo
    query.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                      ctypes.c_void_p, ctypes.c_int]
    query.restype = ctypes.c_int
    info = _DarwinBsdInfo()
    ctypes.set_errno(0)
    size = query(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info))  # PROC_PIDTBSDINFO
    if size == 0 and ctypes.get_errno() == errno.ESRCH:
        return None
    if size != ctypes.sizeof(info) or info.pid != pid:
        raise PublicationError("cannot inspect Harness PID; check process permissions before finalizing")
    if info.status == 5:  # SZOMB: exited, but not yet reaped by its parent.
        return None
    return f"darwin:{pid}:{info.start_sec}:{info.start_usec}"


def _process_identity(pid):
    """Host PID plus start time; exited, zombie or reused PID means stopped."""
    if sys.platform == "darwin":
        return _darwin_process_identity(pid)
    if not sys.platform.startswith("linux"):
        raise PublicationError("PID monitoring requires Linux or macOS")
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return None if fields[0] in ("Z", "X") else fields[19]
    except FileNotFoundError:
        return None


def watch(publisher, pid, interval):
    publisher.preflight()
    with publisher._locked("watch.lock"):
        return _watch(publisher, pid, interval)


def _watch(publisher, pid, interval):
    identity = _process_identity(pid)
    if identity is None:
        raise PublicationError("Harness PID is not running; verify writers stopped, then use once --final")
    # The helper has no authority to signal the Harness or Agent.
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    due = time.monotonic() + interval
    print(json.dumps({"status": "watching", "pid": pid, "interval_seconds": interval}), flush=True)

    def attempt(final):
        try:
            result = publisher.publish(final=final)
        except PublicationError as error:
            result = {"status": "blocked", "error": str(error), "final": final}
        try:
            _json_write(publisher.state_dir / "last-attempt.json", {**result, "at": time.time()})
        except OSError:
            result.setdefault("warning", "publication status could not be saved; check state-directory space/access")
        print(json.dumps(result), flush=True)
        return result["status"] != "blocked"

    publisher.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    while _process_identity(pid) == identity:
        if time.monotonic() >= due:
            attempt(False)
            due += interval
            now = time.monotonic()
            if due < now:
                due += (math.floor((now - due) / interval) + 1) * interval
        time.sleep(min(1, max(0.01, due - time.monotonic())))
    # A dead PID after a crash is not proof of a drained Judge. Publish progress,
    # not a final snapshot; the operator must recover/check writers and finalize.
    leaves = [path.parent for path in publisher.run_dir.glob("*/agent_output.txt")]
    final = bool(leaves) and all((path / "final_result.json").is_file() for path in leaves)
    for attempt_number in range(3):
        if attempt(final):
            if not final:
                print("Harness stopped without final artifacts; recover/check Judge before once --final.", file=sys.stderr)
            return 0 if final else 2
        if attempt_number < 2:
            time.sleep(2)
    return 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "once", "watch"))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True, help="exact logs/runs/<run-id> directory")
    parser.add_argument("--remote", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--secret-env", action="append", default=[], metavar="NAME", help="additional credential environment variable name, never its value")
    parser.add_argument("--final", action="store_true", help="once only: operator verified Harness and Judge writers stopped")
    parser.add_argument("--pid", type=int, help="watch only: actual host Harness CLI PID, not Agent/container/shell PID")
    parser.add_argument("--interval-seconds", type=float, default=1800, help="default 1800 (30 minutes); shorter intervals for tests")
    parser.add_argument("--transfer-timeout-seconds", type=float, default=900, help="per Git fetch/push timeout (default 900); increase for large/slow transfers, independent of Agent timeout")
    args = parser.parse_args(argv)
    if not math.isfinite(args.interval_seconds) or args.interval_seconds <= 0:
        parser.error("interval must be positive and finite")
    if args.mode == "watch" and (args.pid is None or args.pid <= 0 or args.final):
        parser.error("watch requires a positive --pid and does not accept --final")
    try:
        publisher = Publisher(args.repo, args.run_dir, args.remote, args.branch,
                              state_dir=args.state_dir, secret_names=tuple(args.secret_env),
                              transfer_timeout_seconds=args.transfer_timeout_seconds)
        if args.mode == "watch":
            return watch(publisher, args.pid, args.interval_seconds)
        ready = publisher.preflight()
        if args.mode == "preflight":
            print(json.dumps(ready), flush=True)
            return 0
        print(json.dumps(publisher.publish(final=args.final)), flush=True)
        return 0
    except (PublicationError, OSError, ValueError) as error:
        detail = str(error) if isinstance(error, PublicationError) else type(error).__name__
        print(f"Publication blocked: {detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
