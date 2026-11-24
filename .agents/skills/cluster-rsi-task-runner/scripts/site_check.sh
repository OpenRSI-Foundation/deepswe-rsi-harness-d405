#!/usr/bin/env bash
# Read-only RSI-Harness site check for a Slurm, LSF, PBS or PJM compute node.
#
# Run inside an ordinary job on a compute node (no sudo):
#   bash site_check.sh [--apptainer PATH] [--image SIF|URI] [--podman PATH]
#                      [--apptainer-config FILE] [--conmon PATH] [--runtime PATH]
#                      [--podman-base IMAGE] [--workdir DIR] [--keep]
#
# Changes no system or user setting. It writes only below a fresh temporary
# directory (Apptainer/Podman caches included) and, for Podman, a short
# /tmp/rsi-run.* runroot; it deletes both on exit.
# The Apptainer probes need an image with python3 (default pulls
# docker://python:3.12-alpine); the optional Podman build pulls --podman-base.
# Needs bash 4.2+, GNU timeout and host python3 3.6+. Each check prints EXPECT and RESULT
# lines: OK; NEEDS a profile setting; WARN (one route is unavailable; FAIL when
# its alternative is too); FAIL (blocks runs); SKIP; INFO. SUMMARY maps every NEEDS/WARN/FAIL result to its
# profile setting or consequence. Exit 1 when any result is FAIL.

APPTAINER="${APPTAINER:-}"
IMAGE="docker://python:3.12-alpine"
PODMAN="${PODMAN:-}"
PODMAN_BASE="docker.io/library/alpine:3.21"
PARENT="${TMPDIR:-/tmp}"
KEEP=0
APPTAINER_CONFIG=""
CONMON=""
RUNTIME=""
while [ $# -gt 0 ]; do
  case "$1" in
    --apptainer|--apptainer-config|--image|--podman|--conmon|--runtime|--podman-base|--workdir)
      if [ $# -lt 2 ] || [ -z "$2" ] || [[ "$2" == -* ]]; then
        echo "missing value for $1 (see --help)" >&2
        exit 2
      fi ;;
  esac
  case "$1" in
    --apptainer-config) APPTAINER_CONFIG="$2"; shift 2 ;;
    --conmon) CONMON="$2"; shift 2 ;;
    --runtime) RUNTIME="$2"; shift 2 ;;
    --apptainer) APPTAINER="$2"; shift 2 ;;
    --image) IMAGE="$2"; shift 2 ;;
    --podman) PODMAN="$2"; shift 2 ;;
    --podman-base) PODMAN_BASE="$2"; shift 2 ;;
    --workdir) PARENT="$2"; shift 2 ;;
    --keep) KEEP=1; shift ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

# Refuse before creating files or running probes when bounded execution is
# unavailable. Never drop the deadline on sites without GNU coreutils.
if ! command -v timeout >/dev/null 2>&1 || ! timeout --kill-after=5 5 true >/dev/null 2>&1; then
  echo "GNU timeout with --kill-after is required; load coreutils before this check" >&2
  exit 2
fi

WORK="$(mktemp -d "$PARENT/rsi-site-check.XXXXXX")" || { echo "cannot create a work directory in $PARENT" >&2; exit 2; }
RESULTS="$WORK/results.txt"
: > "$RESULTS"
export APPTAINER_CACHEDIR="$WORK/apptainer-cache" APPTAINER_TMPDIR="$WORK/apptainer-tmp"
# SingularityCE reads only its own names.
export SINGULARITY_CACHEDIR="$APPTAINER_CACHEDIR" SINGULARITY_TMPDIR="$APPTAINER_TMPDIR"
mkdir -p "$APPTAINER_CACHEDIR" "$APPTAINER_TMPDIR"
PAUSE_PID_FILE=""
RUNROOT=""

cleanup() {
  if [ -n "$PODMAN" ] && [ -d "$WORK/podman" ]; then
    podman_env 120 "$PODMAN" unshare rm -rf "$WORK/podman/root-vfs" "$WORK/podman/root-overlay" \
      ${RUNROOT:+"$RUNROOT"} >/dev/null 2>&1
  fi
  if [ -n "$PAUSE_PID_FILE" ] && [ -f "$PAUSE_PID_FILE" ]; then
    kill "$(cat "$PAUSE_PID_FILE")" 2>/dev/null
  fi
  if [ "$KEEP" = 1 ]; then
    echo "KEPT $WORK $RUNROOT"
  else
    chmod -R u+rwX "$WORK" $RUNROOT 2>/dev/null
    rm -rf "$WORK" $RUNROOT
  fi
}
trap cleanup EXIT

have() { command -v "$1" >/dev/null 2>&1; }
limit() { timeout --kill-after=5 "$@"; }
section() { printf '\n========== %s ==========\n' "$*"; }
expect() { printf 'EXPECT %s: %s\n' "$1" "$2"; }
result() {
  local name="$1" status="$2"; shift 2
  printf 'RESULT %s %s %s\n' "$name" "$status" "$*" | tee -a "$RESULTS"
}
# Probe output keeps its own RESULT lines; record them for the summary.
collect() { grep -E '^RESULT ' "$1" >> "$RESULTS"; }

# Profile setting or consequence for each NEEDS/WARN/FAIL result.
advice() {
  case "$1" in
    SCHEDULER_JOB) echo "rerun inside an ordinary job on a compute node" ;;
    SLURM_GPU_OPTION) echo '[scheduler] gpu_option = "gpus"' ;;
    SLURM_TMPDISK) echo '[scheduler] request_tmp = false (scratch checks still apply)' ;;
    NS_USER|NS_MNT|NS_PID|NS_IPC|HOST_USERNS)
      echo 'without unprivileged namespaces only a setuid Apptainer or SingularityCE with its own PID/network namespaces and Landlock works; process_namespaces = "harness", network_isolation = "seccomp" and userns Judge isolation are unavailable' ;;
    NS_NET) echo '[apptainer] network_isolation = "seccomp" and [builder] host_namespaces including "network"' ;;
    NS_UTS) echo '[builder] host_namespaces including "uts"' ;;
    LANDLOCK) echo 'no setting: non-root Judge isolation uses userns automatically (Harness rsi-isolate, Science Judge library 9.4+) and needs BOX_* OK; judge_isolation_fallback = "same-user" is only an explicit operator choice' ;;
    HOST_PYTHON) echo "host python3 3.6+ is needed for the host-side probes" ;;
    APPTAINER) echo 'load or install Apptainer or SingularityCE and set [apptainer] binary to its absolute compute-node path; a setuid SingularityCE works with network_isolation = "namespace", while seccomp or a user namespace needs a runtime without setuid' ;;
    APPTAINER_PID_NS|APPTAINER_PID_VIRTUAL)
      echo '[apptainer] process_namespaces = "harness" (single-node only; needs BOX_* OK)' ;;
    APPTAINER_IMAGE) echo "pass --image with a local SIF that contains python3" ;;
    APPTAINER_EXEC) echo "contained Apptainer exec fails: no profile setting; fix the Apptainer installation" ;;
    APPTAINER_SITE_BINDS) echo "a site bind path's files are mounted under --containall: the pre-search isolation check fails; no profile setting: ask the site" ;;
    APPTAINER_NET_NONE) echo '[apptainer] network_isolation = "seccomp" (single-node only; needs NONET_WRAP_* OK)' ;;
    NONET_WRAP_START|NONET_WRAP_SOCKETS)
      echo 'network_isolation = "seccomp" unusable: it needs an Apptainer or SingularityCE without setuid (user namespace mode)' ;;
    BOX_*) echo 'process_namespaces = "harness" and userns Judge isolation unusable here' ;;
    SITE_PROCESS_ISOLATION) echo "no Apptainer PID namespace and no working process box: no profile setting; ask the site" ;;
    SITE_NETWORK_ISOLATION) echo "no network namespace and no working seccomp filter: no-network phases cannot be isolated; ask the site" ;;
    SITE_JUDGE_ISOLATION) echo 'neither Landlock nor a working user-namespace box: Judge confinement fails (exit 123) unless the operator explicitly chooses judge_isolation_fallback = "same-user"' ;;
    PODMAN_INFO) echo '[builder] podman_bundle (Harness installs its own Podman), or conmon (and runtime) = absolute helper paths' ;;
    PODMAN_BUILD_PLAIN) echo 'use [builder] host_namespaces = ["network", "uts"] only if PODMAN_BUILD_HOSTNS is OK' ;;
    PODMAN_BUILD_HOSTNS) echo "both tested VFS builds failed; inspect logs or build elsewhere and import a validated SIF" ;;
    PODMAN_PULL_*) echo "base-image pull failed; build capability remains unverified" ;;
    PODMAN_BUILD_OVERLAY) echo 'use [builder] storage_driver = "vfs" only if a VFS build is OK' ;;
    *) echo "inspect the RESULT detail" ;;
  esac
}

# ---------------------------------------------------------------- probes
cat > "$WORK/host_probe.py" <<'PY'
# Host-side probes (Python 3.6+): landlock | userns | nonet-wrap CMD...
import ctypes, os, platform, sys

libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long
L = ctypes.c_long
UL = ctypes.c_ulong


def out(*words):
    print(" ".join(str(w) for w in words), flush=True)


def landlock():
    abi = libc.syscall(L(444), None, ctypes.c_size_t(0), ctypes.c_uint(1))
    if abi < 0:
        out("RESULT LANDLOCK WARN unavailable:", os.strerror(ctypes.get_errno()))
        return
    attr = ctypes.c_uint64(1)  # handled_access_fs = EXECUTE
    fd = libc.syscall(L(444), ctypes.byref(attr), ctypes.c_size_t(8), ctypes.c_uint(0))
    if fd < 0:
        out("RESULT LANDLOCK WARN abi=%d ruleset creation failed:" % abi, os.strerror(ctypes.get_errno()))
        return
    pid = os.fork()
    if pid == 0:
        ok = libc.prctl(UL(38), UL(1), UL(0), UL(0), UL(0)) == 0 and libc.syscall(L(446), L(fd), L(0)) == 0
        os._exit(0 if ok else 1)
    status = os.waitpid(pid, 0)[1]
    os.close(fd)
    out("RESULT LANDLOCK", "OK" if status == 0 else "WARN", "abi=%d enforce=%s" % (abi, "ok" if status == 0 else "failed"))


def userns():
    uid, gid = os.getuid(), os.getgid()
    pid = os.fork()
    if pid == 0:
        if libc.unshare(ctypes.c_int(0x10000000)) != 0:
            out("RESULT HOST_USERNS WARN unshare(CLONE_NEWUSER):", os.strerror(ctypes.get_errno()))
            os._exit(1)
        try:
            for path, text in (("/proc/self/setgroups", "deny"),
                               ("/proc/self/uid_map", "%d %d 1" % (uid, uid)),
                               ("/proc/self/gid_map", "%d %d 1" % (gid, gid))):
                with open(path, "w") as stream:
                    stream.write(text)
        except OSError as error:
            out("RESULT HOST_USERNS WARN id map:", error)
            os._exit(1)
        out("RESULT HOST_USERNS OK unshare and id maps")
        os._exit(0)
    os.waitpid(pid, 0)


class F(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte), ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint)]


class P(ctypes.Structure):
    _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(F))]


def nonet_wrap(argv):
    # no_new_privs + filter, then exec argv: socket() only for AF_UNIX and
    # NETLINK_ROUTE, socketpair() only for AF_UNIX; everything else EPERM.
    arch = platform.machine()
    table = {"x86_64": (0xC000003E, 41, 53), "aarch64": (0xC00000B7, 198, 199)}
    if arch not in table:
        out("RESULT NONET_WRAP_START SKIP unsupported architecture", arch)
        sys.exit(125)
    audit, socket_nr, socketpair_nr = table[arch]
    LD, JEQ, JGE, RET = 0x20, 0x15, 0x35, 0x06
    ALLOW, KILL, EPERM = 0x7FFF0000, 0, 0x00050000 | 1
    prog = [F(LD, 0, 0, 4), F(JEQ, 1, 0, audit), F(RET, 0, 0, KILL), F(LD, 0, 0, 0)]
    if arch == "x86_64":  # x32 system calls
        prog += [F(JGE, 0, 1, 0x40000000), F(RET, 0, 0, EPERM)]
    prog += [
        F(JEQ, 2, 0, socket_nr), F(JEQ, 9, 0, socketpair_nr), F(RET, 0, 0, ALLOW),
        F(LD, 0, 0, 16), F(JEQ, 4, 0, 1), F(JEQ, 0, 4, 16),
        F(LD, 0, 0, 32), F(JEQ, 1, 0, 0), F(RET, 0, 0, EPERM),
        F(RET, 0, 0, ALLOW), F(RET, 0, 0, EPERM),
        F(LD, 0, 0, 16), F(JEQ, 0, 1, 1), F(RET, 0, 0, ALLOW), F(RET, 0, 0, EPERM),
    ]
    array = (F * len(prog))(*prog)
    program = P(len(prog), array)
    if libc.prctl(UL(38), UL(1), UL(0), UL(0), UL(0)) != 0 or \
            libc.prctl(UL(22), UL(2), ctypes.byref(program), UL(0), UL(0)) != 0:
        out("RESULT NONET_WRAP_START WARN filter install:", os.strerror(ctypes.get_errno()))
        sys.exit(125)
    sys.stdout.flush()
    os.execvp(argv[0], argv)


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "landlock":
        landlock()
    elif command == "userns":
        userns()
    elif command == "nonet-wrap":
        nonet_wrap(sys.argv[2:])
PY

cat > "$WORK/sock_probe.py" <<'PY'
import socket
def t(name, fn):
    try:
        s = fn(); s.close(); print("SOCK", name, "ALLOWED", flush=True)
    except OSError as e:
        print("SOCK", name, "DENIED", e.errno, flush=True)
t("inet", lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM))
t("inet6", lambda: socket.socket(socket.AF_INET6, socket.SOCK_STREAM))
t("unix", lambda: socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))
t("netlink_route", lambda: socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, 0))
t("netlink_usersock", lambda: socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, 2))
t("packet", lambda: socket.socket(getattr(socket, "AF_PACKET", 17), socket.SOCK_RAW, 0))
t("socketpair_unix", lambda: socket.socketpair(socket.AF_UNIX)[0])
PY

cat > "$WORK/box_probe.py" <<'PY'
# Inside Apptainer: can an unprivileged user build the Harness process box?
import ctypes, functools, os, signal, sys, time
print = functools.partial(print, flush=True)
libc = ctypes.CDLL(None, use_errno=True)
def err():
    return os.strerror(ctypes.get_errno())
NEWNS, NEWUSER, NEWPID, NEWIPC = 0x00020000, 0x10000000, 0x20000000, 0x08000000
MS_RDONLY, MS_NOSUID, MS_NODEV, MS_NOEXEC = 1, 2, 4, 8
MS_REMOUNT, MS_BIND, MS_REC, MS_PRIVATE = 32, 4096, 16384, 1 << 18
def mount(src, tgt, fs, flags, data=None):
    enc = lambda s: None if s is None else s.encode()
    return libc.mount(enc(src), enc(tgt), enc(fs), ctypes.c_ulong(flags), enc(data))
def ok(name, good, detail=""):
    print("RESULT", name, "OK" if good else "WARN", detail)
uid, gid = os.getuid(), os.getgid()
if libc.unshare(NEWUSER | NEWNS | NEWPID | NEWIPC) != 0:
    ok("BOX_UNSHARE", False, err()); sys.exit(1)
ok("BOX_UNSHARE", True, "user|mnt|pid|ipc")
for path, text in (("/proc/self/setgroups", "deny"), ("/proc/self/uid_map", "%d %d 1" % (uid, uid)),
                   ("/proc/self/gid_map", "%d %d 1" % (gid, gid))):
    try:
        with open(path, "w") as f:
            f.write(text)
    except OSError as e:
        print("BOX write %s failed: %s" % (path, e))
if mount(None, "/", None, MS_REC | MS_PRIVATE) != 0:
    print("BOX make-private failed:", err())
pid = os.fork()
if pid == 0:
    m = mount("proc", "/proc", "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC)
    ok("BOX_FRESH_PROC", m == 0, "" if m == 0 else err())
    pids = sorted(int(x) for x in os.listdir("/proc") if x.isdigit())
    ok("BOX_VISIBLE_PIDS", m == 0 and pids[:1] == [1] and len(pids) <= 3, pids)
    h = mount("tmpfs", "/secret", "tmpfs", MS_NOSUID | MS_NODEV, "size=1m,mode=0755")
    ok("BOX_HIDE_DIR", h == 0 and not os.path.exists("/secret/flag.txt"), "" if h == 0 else err())
    b = mount("/work", "/work", None, MS_BIND | MS_REC)
    r = mount(None, "/work", None, MS_BIND | MS_REMOUNT | MS_RDONLY | MS_NOSUID | MS_NODEV) if b == 0 else -1
    detail = "" if r == 0 else err()
    try:
        open("/work/rsi-probe-write", "w").close(); readonly = False
    except OSError as e:
        readonly = True; detail = "errno=%d" % e.errno
    ok("BOX_READONLY", r == 0 and readonly, detail)
    c = os.fork()
    if c == 0:
        if os.fork() == 0:
            os.setsid()
            while True:
                time.sleep(1)
        os._exit(0)
    os.waitpid(c, 0)
    time.sleep(1)
    kids = [int(x) for x in os.listdir("/proc") if x.isdigit() and int(x) != 1]
    os.kill(-1, signal.SIGSTOP)
    time.sleep(0.5)
    states = {}
    for p in kids:
        try:
            states[p] = open("/proc/%d/stat" % p).read().rsplit(")", 1)[1].split()[0]
        except OSError:
            pass
    ok("BOX_PAUSE_SETSID", bool(states) and all(s == "T" for s in states.values()), states)
    os.kill(-1, signal.SIGKILL)
    n = os.fork()
    if n == 0:
        rr = libc.unshare(NEWUSER | NEWNS | NEWPID | NEWIPC)
        ok("BOX_NESTED_UNSHARE", rr == 0, "" if rr == 0 else err())
        os._exit(0)
    os.waitpid(n, 0)
    os._exit(0)
os.waitpid(pid, 0)
PY

echo "WORKDIR=$WORK"
echo "HOST=$(hostname) KERNEL=$(uname -r) ARCH=$(uname -m) USER=$(id -un)"
head -2 /etc/os-release 2>/dev/null

# ---------------------------------------------------------------- scheduler
section "SCHEDULER"
if [ -n "$SLURM_JOB_ID" ]; then
  result SCHEDULER_JOB OK "Slurm job $SLURM_JOB_ID"
  if have scontrol; then
    limit 30 scontrol show job "$SLURM_JOB_ID" 2>/dev/null | grep -E 'Partition=|TimeLimit=|TRES=|Features='
    node="${SLURMD_NODENAME:-$(hostname -s)}"
    tmpdisk="$(limit 30 scontrol show node "$node" -o 2>/dev/null | grep -oE 'TmpDisk=[0-9]+' | cut -d= -f2)"
    expect SLURM_TMPDISK "nonzero TmpDisk, so sbatch --tmp is accepted"
    if [ -z "$tmpdisk" ]; then result SLURM_TMPDISK SKIP "not reported"
    elif [ "$tmpdisk" = 0 ]; then result SLURM_TMPDISK NEEDS "TmpDisk=0"
    else result SLURM_TMPDISK OK "TmpDisk=$tmpdisk"; fi
    maxtime="$(limit 30 scontrol show partition "$SLURM_JOB_PARTITION" -o 2>/dev/null | grep -oE 'MaxTime=[^ ]+' | cut -d= -f2)"
    result SLURM_MAXTIME INFO "partition MaxTime=${maxtime:-unknown}; a longer research run needs [scheduler] run_walltime_limit and explicit resume"
  fi
  if have sbatch; then
    # --test-only validates a request without submitting a job.
    probe=(sbatch --test-only ${SLURM_JOB_PARTITION:+-p "$SLURM_JOB_PARTITION"} ${SLURM_JOB_ACCOUNT:+-A "$SLURM_JOB_ACCOUNT"} ${SLURM_JOB_QOS:+-q "$SLURM_JOB_QOS"} -t 1 -N 1 --wrap true)
    expect SLURM_GPU_OPTION "this partition accepts --gres=gpu:1 (the default GPU request)"
    if limit 60 "${probe[@]}" --gres=gpu:1 > "$WORK/gres.out" 2>&1; then result SLURM_GPU_OPTION OK "--gres accepted"
    elif limit 60 "${probe[@]}" --gpus=1 > "$WORK/gpus.out" 2>&1; then result SLURM_GPU_OPTION NEEDS "--gres rejected, --gpus accepted: $(tail -1 "$WORK/gres.out")"
    else result SLURM_GPU_OPTION SKIP "neither GPU form accepted here (CPU partition?): $(tail -1 "$WORK/gres.out")"; fi
  fi
elif [ -n "$LSB_JOBID" ]; then
  result SCHEDULER_JOB OK "LSF job $LSB_JOBID"
  have bjobs && limit 30 bjobs -l "$LSB_JOBID" 2>/dev/null | head -20
elif [ -n "${PBS_JOBID:-}" ]; then
  result SCHEDULER_JOB OK "PBS job $PBS_JOBID"
  have qstat && limit 30 qstat -f "$PBS_JOBID" 2>/dev/null | grep -E '^ *(queue|Resource_List\.[a-z]+) ='
elif [ -n "${PJM_JOBID:-}" ]; then
  result SCHEDULER_JOB OK "PJM job $PJM_JOBID"
  have pjstat && limit 30 pjstat -v "$PJM_JOBID" 2>/dev/null | head -20
else
  result SCHEDULER_JOB FAIL "no SLURM_JOB_ID, LSB_JOBID, PBS_JOBID or PJM_JOBID"
fi
if [ -z "${CUDA_VISIBLE_DEVICES+set}" ]; then
  result CUDA_DEVICES INFO "CUDA_VISIBLE_DEVICES unset: only the job's device cgroup, if any, limits its GPUs"
elif [ -z "$CUDA_VISIBLE_DEVICES" ]; then
  result CUDA_DEVICES INFO "CUDA_VISIBLE_DEVICES empty: no GPUs"
elif [[ "$CUDA_VISIBLE_DEVICES" =~ ^((GPU|MIG)-[^,]+,?)+$ ]]; then
  result CUDA_DEVICES INFO "CUDA_VISIBLE_DEVICES holds UUIDs ($CUDA_VISIBLE_DEVICES): code that reads it as indices fails"
elif [[ "$CUDA_VISIBLE_DEVICES" =~ ^[0-9]+(,[0-9]+)*$ ]]; then
  result CUDA_DEVICES INFO "CUDA_VISIBLE_DEVICES holds indices ($CUDA_VISIBLE_DEVICES)"
else
  result CUDA_DEVICES INFO "CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES: neither UUIDs nor indices"
fi
df -h "$PARENT" 2>/dev/null | tail -1

# ---------------------------------------------------------------- kernel
section "KERNEL"
expect NS_LIMITS "user/mnt/pid/ipc > 0; net or uts = 0 needs a profile setting"
for ns in user mnt pid ipc net uts; do
  value="$(cat "/proc/sys/user/max_${ns}_namespaces" 2>/dev/null)"
  name="NS_$(echo "$ns" | tr '[:lower:]' '[:upper:]')"
  if [ -z "$value" ]; then result "$name" SKIP "max_${ns}_namespaces unreadable"
  elif [ "$value" = 0 ]; then
    case "$ns" in net|uts) result "$name" NEEDS "max_${ns}_namespaces=0" ;; *) result "$name" WARN "max_${ns}_namespaces=0" ;; esac
  else result "$name" OK "max_${ns}_namespaces=$value"; fi
done
grep -E '^(Seccomp|NoNewPrivs):' /proc/self/status
echo "LSM=$(cat /sys/kernel/security/lsm 2>/dev/null || echo unreadable)"
# Entries name the user or the numeric uid.
if grep -qsE "^($(id -un)|$(id -u)):" /etc/subuid; then result SUBUID INFO "subuid entry present"
else result SUBUID INFO "no subuid entry: rootless builds use a single id mapping (fakeroot settings handle chown)"; fi

PY3=""
if have python3 && python3 -c 'import sys; sys.exit(sys.version_info < (3, 6))' 2>/dev/null; then
  PY3="$(command -v python3)"
  result HOST_PYTHON OK "$(python3 -V 2>&1)"
  host_check() {  # host_check RESULT_NAME PROBE
    local name="$1" probe="$2" code
    limit 30 python3 "$WORK/host_probe.py" "$probe" > "$WORK/$probe.out" 2>&1
    code=$?
    if [ "$code" = 0 ] && grep -q "^RESULT $name " "$WORK/$probe.out"; then
      cat "$WORK/$probe.out"; collect "$WORK/$probe.out"
    else
      # A probe that times out after partial output has not established its
      # result. Keep the diagnostic without publishing a stale RESULT OK.
      sed 's/^/PROBE_OUTPUT /' "$WORK/$probe.out"
      result "$name" WARN "probe exit $code or no result"
    fi
  }
  expect HOST_USERNS "an unprivileged process can create a user namespace"
  host_check HOST_USERNS userns
  expect LANDLOCK "Landlock ABI >= 1 and a ruleset can be enforced (else userns isolation is used)"
  host_check LANDLOCK landlock
else
  result HOST_PYTHON FAIL "python3 3.6+ not found"
fi

# ---------------------------------------------------------------- apptainer
section "APPTAINER"
[ -n "$APPTAINER" ] || APPTAINER="$(command -v apptainer 2>/dev/null || command -v singularity 2>/dev/null)"
SIF=""; singularity_ce=0
if [ -z "$APPTAINER" ] || [ ! -x "$APPTAINER" ]; then
  result APPTAINER FAIL "apptainer not found (pass --apptainer PATH)"
else
  if ! limit 30 "$APPTAINER" --version > "$WORK/apptainer-version.txt" 2> "$WORK/apptainer-version.err"; then
    result APPTAINER FAIL "--version failed: $(cat "$WORK/apptainer-version.txt" "$WORK/apptainer-version.err" | tail -1)"
  elif [[ "$(awk 'NF { print tolower($1); exit }' "$WORK/apptainer-version.txt")" == singularity* ]]; then
    singularity_ce=1
    result APPTAINER OK "$APPTAINER $(cat "$WORK/apptainer-version.txt") is SingularityCE (container variables are SINGULARITYENV_*)"
  else
    result APPTAINER OK "$APPTAINER $(cat "$WORK/apptainer-version.txt")"
  fi
  suid=""; conf="$APPTAINER_CONFIG"
  if limit 30 "$APPTAINER" buildcfg > "$WORK/buildcfg.txt" 2> "$WORK/buildcfg.err"; then
    # SingularityCE names its keys SINGULARITY_*.
    suid="$(sed -nE 's/^(APPTAINER|SINGULARITY)_SUID_INSTALL=//p' "$WORK/buildcfg.txt" | head -1)"
    # The running binary reports its configured path; do not search nearby
    # installs or the user's home and accidentally inspect a different one.
    [ -n "$conf" ] || conf="$(sed -nE 's/^(APPTAINER|SINGULARITY)_CONF_FILE=//p' "$WORK/buildcfg.txt" | head -1)"
  fi
  setuid_conf=""; pidns=""; binds=""; conf_known=0
  if [ -n "$conf" ] && [ -r "$conf" ]; then
    conf_known=1
    setuid_conf="$(grep -E '^[[:space:]]*allow setuid[[:space:]]*=' "$conf" | tail -1 | cut -d= -f2 | tr -d '[:space:]')"
    pidns="$(grep -E '^[[:space:]]*allow pid ns[[:space:]]*=' "$conf" | tail -1 | cut -d= -f2 | tr -d '[:space:]')"
    binds="$(grep -E '^[[:space:]]*bind path[[:space:]]*=' "$conf" | cut -d= -f2- | tr -d ' ')"
    grep -E '^[[:space:]]*(allow (pid ns|setuid|net users|net networks)|mount (hostfs|home|tmp|proc)|enable (overlay|fusemount)|bind path)' "$conf"
  fi
  setuid_note='network_isolation = "seccomp" needs non-setuid mode'
  # As the Harness decides: a setuid install not configured allow setuid = no.
  if [ "$singularity_ce" = 1 ] && [ "$suid" = 1 ] && [ "${setuid_conf,,}" != no ]; then
    setuid_note='setuid SingularityCE: network_isolation = "namespace" outside a user namespace only; for "seccomp" or inside one, a runtime without setuid'
  fi
  result APPTAINER_SETUID INFO "suid_install=${suid:-unknown} allow_setuid=${setuid_conf:-unknown} conf=${conf:-unknown} ($setuid_note)"
  expect APPTAINER_PID_NS "configured allow pid ns (runtime behavior is checked separately)"
  case "$pidns" in
    no) result APPTAINER_PID_NS NEEDS "allow pid ns = no" ;;
    yes) result APPTAINER_PID_NS OK "allow pid ns = yes" ;;
    *) result APPTAINER_PID_NS SKIP "configuration unknown; pass --apptainer-config FILE if buildcfg does not report a readable APPTAINER_CONF_FILE (SINGULARITY_CONF_FILE)" ;;
  esac

  if [ -f "$IMAGE" ]; then SIF="$IMAGE"
  else
    echo "pulling $IMAGE"
    if limit 600 "$APPTAINER" pull -F "$WORK/probe.sif" "$IMAGE" > "$WORK/pull.log" 2>&1; then SIF="$WORK/probe.sif"
    else tail -5 "$WORK/pull.log"; fi
  fi
  if [ -z "$SIF" ]; then
    result APPTAINER_IMAGE FAIL "cannot obtain $IMAGE"
  else
    result APPTAINER_IMAGE OK "$SIF"
    EXEC=("$APPTAINER" exec --containall --no-mount hostfs --writable-tmpfs)

    expect APPTAINER_EXEC "contained exec (--containall --no-mount hostfs --writable-tmpfs) starts"
    limit 300 "${EXEC[@]}" "$SIF" cat /proc/self/mountinfo > "$WORK/mountinfo" 2> "$WORK/exec.err"
    code=$?; exec_status=$code; cat "$WORK/exec.err"
    if [ "$code" = 0 ]; then result APPTAINER_EXEC OK
    else result APPTAINER_EXEC FAIL "exit $code: $(tail -1 "$WORK/exec.err")"; fi
    expect APPTAINER_PID_VIRTUAL "contained exec runs in a different PID namespace from this host process"
    host_pidns="$(readlink /proc/self/ns/pid 2>/dev/null)"
    if [ "$exec_status" != 0 ] || [ -z "$host_pidns" ]; then
      result APPTAINER_PID_VIRTUAL SKIP "no successful contained exec or host namespace identity"
    elif limit 300 "${EXEC[@]}" "$SIF" python3 -c 'import os; print(os.readlink("/proc/self/ns/pid"))' > "$WORK/pidns.out" 2> "$WORK/pidns.err"; then
      container_pidns="$(cat "$WORK/pidns.out")"
      if [[ "$container_pidns" != pid:\[*\] ]]; then
        result APPTAINER_PID_VIRTUAL WARN "invalid namespace identity"
      elif [ "$container_pidns" = "$host_pidns" ]; then
        result APPTAINER_PID_VIRTUAL NEEDS "contained process shares host PID namespace $host_pidns"
      else
        result APPTAINER_PID_VIRTUAL OK "host=$host_pidns container=$container_pidns"
      fi
    else
      result APPTAINER_PID_VIRTUAL WARN "namespace probe failed: $(tail -1 "$WORK/pidns.err")"
    fi

    expect APPTAINER_SITE_BINDS "no apptainer.conf bind path's files (except /etc/hosts, /etc/localtime) are mounted under --containall"
    mounted=""
    for entry in $binds; do
      src="${entry%%:*}"
      case "$src" in /etc/hosts|/etc/localtime|/) continue ;; /*) ;; *) continue ;; esac
      # As the Harness check: a container mount on the device of the host
      # mount holding src whose root overlaps src's path on that device.
      at="$(awk -v src="$src" '
        function under(p, q) { return p == q || q == "/" || index(p, q "/") == 1 }
        NR == FNR { if (under(src, $5) && length($5) > best) { best = length($5); dev = $3; root = $4; point = $5 } next }
        FNR == 1 {
          rel = point == "/" ? substr(src, 2) : substr(src, length(point) + 2)
          inner = rel == "" ? root : (root == "/" ? "/" rel : root "/" rel)
        }
        $3 == dev && (under($4, inner) || under(inner, $4)) { printf " %s", $5 }
      ' /proc/self/mountinfo "$WORK/mountinfo" 2>/dev/null)"
      [ -n "$at" ] && mounted="$mounted $src at$at;"
    done
    if [ "$exec_status" != 0 ] || [ ! -s "$WORK/mountinfo" ]; then result APPTAINER_SITE_BINDS SKIP "no successful mount-table probe"
    elif [ "$conf_known" != 1 ]; then result APPTAINER_SITE_BINDS SKIP "site bind configuration unknown"
    elif [ -n "$mounted" ]; then result APPTAINER_SITE_BINDS FAIL "mounted:$mounted"
    else result APPTAINER_SITE_BINDS OK "checked: $(echo ${binds:-none})"; fi

    expect APPTAINER_NET_NONE "--net --network none starts (needs network namespaces)"
    if limit 300 "${EXEC[@]}" --net --network none "$SIF" true > "$WORK/net.err" 2>&1; then
      result APPTAINER_NET_NONE OK
    else
      cat "$WORK/net.err"; result APPTAINER_NET_NONE NEEDS "$(tail -1 "$WORK/net.err")"
    fi

    if [ -n "$PY3" ]; then
      expect NONET_WRAP_START "Apptainer starts under a host-side no_new_privs + seccomp filter; Seccomp: 2 inside"
      limit 300 "$PY3" "$WORK/host_probe.py" nonet-wrap "${EXEC[@]}" "$SIF" \
        sh -c 'id -un; grep -E "^(Seccomp|NoNewPrivs):" /proc/self/status' > "$WORK/wrap.out" 2>&1
      code=$?; cat "$WORK/wrap.out"; wrap_ok=0
      if grep -q '^RESULT NONET_WRAP_START' "$WORK/wrap.out"; then collect "$WORK/wrap.out"
      elif [ "$code" = 0 ] && grep -qE '^Seccomp:[[:space:]]*2' "$WORK/wrap.out"; then result NONET_WRAP_START OK; wrap_ok=1
      else result NONET_WRAP_START WARN "exit $code: $(tail -1 "$WORK/wrap.out")"; fi
    fi
    if [ -n "$PY3" ] && [ "$wrap_ok" = 1 ]; then
      expect NONET_WRAP_SOCKETS "inet, inet6, packet, netlink_usersock DENIED; unix, netlink_route, socketpair_unix ALLOWED"
      limit 300 "$PY3" "$WORK/host_probe.py" nonet-wrap "${EXEC[@]}" \
        --bind "$WORK/sock_probe.py:/rsi_sock_probe.py:ro" "$SIF" python3 /rsi_sock_probe.py > "$WORK/sock.out" 2>&1
      code=$?; cat "$WORK/sock.out"
      bad=""
      [ "$code" = 0 ] || bad=" probe-exit-$code"
      for s in inet inet6 packet netlink_usersock; do grep -q "^SOCK $s DENIED" "$WORK/sock.out" || bad="$bad $s-not-denied"; done
      for s in unix netlink_route socketpair_unix; do grep -q "^SOCK $s ALLOWED" "$WORK/sock.out" || bad="$bad $s-not-allowed"; done
      if [ -z "$bad" ]; then result NONET_WRAP_SOCKETS OK; else result NONET_WRAP_SOCKETS WARN "$bad"; fi
    fi

    expect BOX "BOX_UNSHARE, BOX_FRESH_PROC, BOX_VISIBLE_PIDS [1..], BOX_HIDE_DIR, BOX_READONLY, BOX_PAUSE_SETSID, BOX_NESTED_UNSHARE all OK"
    mkdir -p "$WORK/box-secret" "$WORK/box-work"
    echo hidden > "$WORK/box-secret/flag.txt"
    limit 300 "${EXEC[@]}" --bind "$WORK/box-secret:/secret:ro" --bind "$WORK/box-work:/work" \
      --bind "$WORK/box_probe.py:/rsi_box_probe.py:ro" "$SIF" python3 -u /rsi_box_probe.py > "$WORK/box.out" 2>&1
    code=$?; cat "$WORK/box.out"; collect "$WORK/box.out"
    if [ "$code" = 0 ]; then result BOX_RUN OK; else result BOX_RUN WARN "exit $code"; fi
    for step in BOX_UNSHARE BOX_FRESH_PROC BOX_VISIBLE_PIDS BOX_HIDE_DIR BOX_READONLY BOX_PAUSE_SETSID BOX_NESTED_UNSHARE; do
      grep -q "^RESULT $step " "$WORK/box.out" || result "$step" WARN "no result (probe stopped earlier)"
    done
  fi
fi

# ---------------------------------------------------------------- podman
section "PODMAN (optional image build)"
podman_env() {  # podman_env SECONDS PODMAN ARGS...: private runtime, data and registry config
  local seconds="$1"; shift
  limit "$seconds" env -u DBUS_SESSION_BUS_ADDRESS XDG_RUNTIME_DIR="$WORK/podman/run" \
    XDG_DATA_HOME="$WORK/podman/data" TMPDIR="$WORK/podman/tmp" \
    CONTAINERS_REGISTRIES_CONF="$WORK/podman/registries.conf" "$@"
}
[ -n "$PODMAN" ] || PODMAN="$(command -v podman 2>/dev/null)"
if [ -z "$PODMAN" ] || [ ! -x "$PODMAN" ]; then
  PODMAN=""
  result PODMAN SKIP "no podman found (pass --podman PATH); [builder] podman_bundle makes Harness install its own, or import a SIF"
else
  mkdir -p "$WORK/podman/run" "$WORK/podman/data" "$WORK/podman/tmp" "$WORK/podman/context"
  # Podman 4.x to 5.0 refuse a runroot longer than 50 characters.
  RUNROOT="$(mktemp -d /tmp/rsi-run.XXXXXX)"
  chmod 0700 "$WORK/podman/run"
  PAUSE_PID_FILE="$WORK/podman/run/libpod/tmp/pause.pid"
  printf '%s\n' 'unqualified-search-registries = ["docker.io"]' 'short-name-mode = "disabled"' > "$WORK/podman/registries.conf"
  printf 'FROM %s\nRUN printf ok > /probe.txt\n' "$PODMAN_BASE" > "$WORK/podman/context/Dockerfile"
  result PODMAN INFO "$PODMAN $(podman_env 60 "$PODMAN" --version 2>&1)"
  base_opts=(--cgroup-manager=cgroupfs --events-backend=file)
  [ -n "$CONMON" ] && base_opts+=(--conmon "$CONMON")
  [ -n "$RUNTIME" ] && base_opts+=(--runtime "$RUNTIME")

  expect PODMAN_INFO "configured Podman info succeeds and returns a JSON object"
  podman_env 120 "$PODMAN" --root "$WORK/podman/root-vfs" --runroot "$RUNROOT/vfs" \
    --storage-driver=vfs "${base_opts[@]}" info --format json > "$WORK/podman/info.json" 2> "$WORK/podman/info.err"
  code=$?; info_ok=0
  if [ "$code" != 0 ]; then
    result PODMAN_INFO WARN "exit $code: $(tail -1 "$WORK/podman/info.err")"
  elif [ -n "$PY3" ] && "$PY3" -c 'import json, sys; v=json.load(open(sys.argv[1])); sys.exit(not isinstance(v, dict) or not isinstance(v.get("host"), dict))' "$WORK/podman/info.json"; then
    result PODMAN_INFO OK "Podman reported host information; helper overrides only from --conmon/--runtime"
    info_ok=1
  else
    result PODMAN_INFO WARN "invalid or unverifiable JSON info; inspect $WORK/podman/info.json"
  fi

  pull_base() {  # each storage driver has its own image store
    local driver="$1" opt
    if [ "$driver" = vfs ]; then opt=vfs.ignore_chown_errors=true; else opt=ignore_chown_errors=true; fi
    podman_env 600 "$PODMAN" --root "$WORK/podman/root-$driver" --runroot "$RUNROOT/$driver" \
      --storage-driver="$driver" --storage-opt "$opt" "${base_opts[@]}" pull "$PODMAN_BASE" > "$WORK/podman/pull-$driver.log" 2>&1
  }
  build() {  # build NAME DRIVER [build options...]
    local name="$1" driver="$2" opt; shift 2
    if [ "$driver" = vfs ]; then opt=vfs.ignore_chown_errors=true; else opt=ignore_chown_errors=true; fi
    podman_env 900 "$PODMAN" --root "$WORK/podman/root-$driver" --runroot "$RUNROOT/$driver" \
      --storage-driver="$driver" --storage-opt "$opt" "${base_opts[@]}" \
      build --pull=never --isolation rootless --format docker "$@" -t "localhost/rsi-site-check-$name" \
      "$WORK/podman/context" > "$WORK/podman/$name.log" 2>&1
  }
  hostns=(); vfs_ok=0
  if [ "$info_ok" != 1 ]; then
    result PODMAN_BUILD_PLAIN SKIP "Podman info did not pass"
    result PODMAN_BUILD_OVERLAY SKIP "Podman info did not pass"
  else
    expect PODMAN_BUILD_PLAIN "VFS build with RUN succeeds without host namespaces"
    if pull_base vfs; then
      result PODMAN_PULL_VFS OK
      if build plain vfs; then result PODMAN_BUILD_PLAIN OK; vfs_ok=1
      else
        plain_detail="$(tail -1 "$WORK/podman/plain.log")"
        expect PODMAN_BUILD_HOSTNS "VFS build with --network=host --uts=host succeeds"
        if build hostns vfs --network=host --uts=host; then
          result PODMAN_BUILD_PLAIN NEEDS "plain build failed, host-namespace build passed: $plain_detail"
          result PODMAN_BUILD_HOSTNS OK
          hostns=(--network=host --uts=host); vfs_ok=1
        else
          result PODMAN_BUILD_PLAIN WARN "plain build failed: $plain_detail"
          result PODMAN_BUILD_HOSTNS WARN "$(tail -1 "$WORK/podman/hostns.log")"
        fi
      fi
    else
      result PODMAN_PULL_VFS WARN "$(tail -1 "$WORK/podman/pull-vfs.log")"
      result PODMAN_BUILD_PLAIN SKIP "base-image pull did not pass; build not attempted"
    fi
    expect PODMAN_BUILD_OVERLAY "overlay image pull and build succeed with the tested namespace settings"
    if ! pull_base overlay; then
      result PODMAN_PULL_OVERLAY WARN "$(tail -1 "$WORK/podman/pull-overlay.log")"
      result PODMAN_BUILD_OVERLAY SKIP "base-image pull did not pass; build not attempted"
    elif build overlay overlay "${hostns[@]}"; then
      result PODMAN_PULL_OVERLAY OK
      result PODMAN_BUILD_OVERLAY OK
    else
      result PODMAN_PULL_OVERLAY OK
      if [ "$vfs_ok" = 1 ]; then
        result PODMAN_BUILD_OVERLAY NEEDS "overlay build failed while VFS passed: $(tail -1 "$WORK/podman/overlay.log")"
      else
        result PODMAN_BUILD_OVERLAY WARN "overlay build failed; no successful VFS alternative: $(tail -1 "$WORK/podman/overlay.log")"
      fi
    fi
  fi
fi

# ---------------------------------------------------------------- summary
section "SUMMARY"
status_of() { awk -v n="$1" '$2==n {print $3; exit}' "$RESULTS"; }
box_ok=1
for step in BOX_RUN BOX_UNSHARE BOX_FRESH_PROC BOX_VISIBLE_PIDS BOX_HIDE_DIR BOX_READONLY BOX_PAUSE_SETSID; do
  [ "$(status_of "$step")" = OK ] || box_ok=0
done
if [ -n "$SIF" ]; then
  pid_off=0
  [ "$(status_of APPTAINER_PID_VIRTUAL)" = OK ] || pid_off=1
  if [ "$pid_off" = 1 ] && [ "$box_ok" = 0 ]; then
    result SITE_PROCESS_ISOLATION FAIL "Apptainer PID isolation not established and the process box fails"
  fi
  if [ "$(status_of APPTAINER_NET_NONE)" = NEEDS ] && [ "$(status_of NONET_WRAP_SOCKETS)" != OK ]; then
    result SITE_NETWORK_ISOLATION FAIL "--network none fails and the seccomp filter does not work"
  fi
  # Judge userns isolation is the process box, nested when Work's box is needed.
  if [ "$(status_of LANDLOCK)" != OK ] && { [ "$box_ok" = 0 ] || { [ "$pid_off" = 1 ] && [ "$(status_of BOX_NESTED_UNSHARE)" != OK ]; }; }; then
    result SITE_JUDGE_ISOLATION FAIL "no Landlock and no working user-namespace box"
  fi
fi
for s in OK NEEDS WARN FAIL SKIP INFO; do
  printf 'SUMMARY %s=%s\n' "$s" "$(grep -c "^RESULT [^ ]* $s" "$RESULTS")"
done
while read -r _ name status detail; do
  case "$status" in
    NEEDS|WARN|FAIL) printf 'SUMMARY %s %s -> %s\n' "$status" "$name" "$(advice "$name")" ;;
  esac
done < "$RESULTS"
if grep -q '^RESULT [^ ]* FAIL' "$RESULTS"; then
  echo "SUMMARY VERDICT: FAIL lines need the site or another route before a run"
  exit 1
fi
echo "SUMMARY VERDICT: set the NEEDS settings; the site is usable only once a run's pre-search isolation check passes"
exit 0
