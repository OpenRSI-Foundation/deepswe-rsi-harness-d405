#!/usr/bin/env python3
"""Use the single-node publisher with LSF/Slurm/Kubernetes/PBS/PJM allocation finalization gates."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

from publish_run_logs import PublicationError, Publisher, watch


ADAPTERS = {"lsf": "bluevela", "slurm": "slurm", "kubernetes": "kubernetes", "pbs": "pbs", "pjm": "pjm"}
# A job run inside the controller's own PBS or PJM job (launch = "allocation").
LOCAL_JOB = re.compile(r"(?P<batch>.+)\.local-(?P<token>[0-9a-f]+)")
JOB_ID = {"lsf": r"[0-9]+", "slurm": r"[0-9]+", "kubernetes": r"[a-z0-9]([a-z0-9-]{0,50}[a-z0-9])?",
          # qsub prints the full ID, "<sequence>.<server>"; a local job's is "<that>.local-<token>".
          "pbs": r"[0-9]+(\.[A-Za-z0-9][A-Za-z0-9_.-]*)?", "pjm": r"[0-9]{1,10}(\.local-[0-9a-f]+)?"}
STATUS_BINARY = {"lsf": "bjobs", "slurm": "squeue", "kubernetes": "kubectl", "pbs": "qstat", "pjm": "pjstat"}
# The ended states (ST) pjstat -H lists. ERR is a held job, still queued until pjdel.
PJM_ENDED = {"EXT", "CCL", "RJT"}
PJM_COLUMNS = ("JOB_ID", "ST", "EC", "PC", "SN")
TERMINAL = {
    "BOOT_FAIL", "CANCELLED", "COMPLETED", "DEADLINE", "FAILED", "NODE_FAIL",
    "OUT_OF_MEMORY", "PREEMPTED", "REVOKED", "SPECIAL_EXIT", "TIMEOUT",
}


def _same_pbs_job(job_id, listed):
    # A full ID matches exactly; a bare sequence number names <number>.<server>.
    return listed == job_id or ("." not in job_id and listed.startswith(f"{job_id}."))


class ClusterPublisher(Publisher):
    def __init__(self, *args, run_info: Path, scheduler: str, status_binary=None,
                 accounting_binary=None, history_binary="bhist", kubectl_args=(), **kwargs):
        if scheduler not in ADAPTERS:
            raise ValueError("scheduler must be lsf, slurm, kubernetes, pbs or pjm")
        super().__init__(*args, **kwargs)
        self.run_info = run_info.resolve()
        self.scheduler = scheduler
        self.status_binary = status_binary or STATUS_BINARY[scheduler]
        # --kubeconfig/--context/--namespace of the profile, for kubectl.
        self.kubectl_args = tuple(kubectl_args)
        self.accounting_binary = accounting_binary or "sacct"
        self.history_binary = history_binary

    def _query(self, argv, *, missing_lsf_job=None, missing_kubernetes_job=False, missing_pbs_job=False):
        try:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False,
                                    env={**os.environ, "LC_ALL": "C"})
        except (OSError, subprocess.TimeoutExpired):
            raise PublicationError("Scheduler status unavailable; final publication deferred") from None
        if result.returncode:
            if missing_lsf_job is not None and re.fullmatch(
                rf"Job <{re.escape(missing_lsf_job)}> is not found\.?",
                result.stderr.strip(),
            ) and not result.stdout.strip():
                return ""
            if missing_kubernetes_job and "(NotFound)" in result.stderr:
                return None
            if missing_pbs_job and "unknown job id" in result.stderr.lower():
                return None
            # Do not expose site diagnostics or environment values in publisher logs.
            raise PublicationError("Scheduler status query failed; final publication deferred")
        return result.stdout

    def _manifest(self, *, allow_missing=False):
        try:
            info = json.loads(self.run_info.read_text())
        except FileNotFoundError:
            if allow_missing:
                return None
            raise PublicationError("exact RUN_INFO.json unavailable; verify cluster writers stopped") from None
        except (OSError, ValueError):
            raise PublicationError("exact RUN_INFO.json unavailable; verify cluster writers stopped") from None
        if not isinstance(info, dict) or info.get("run_id") != self.run_dir.name:
            raise PublicationError("RUN_INFO.json does not match this run ID")
        expected_adapter = ADAPTERS[self.scheduler]
        if "adapter" in info and info["adapter"] != expected_adapter:
            raise PublicationError("RUN_INFO.json does not match the selected scheduler adapter")
        return info

    def require_stopped(self):
        info = self._manifest()
        if info.get("state") not in {"completed", "failed"}:
            raise PublicationError("Harness run manifest is not terminal; recover/check the controller")
        additional = info.get("job_ids", [])
        if not isinstance(additional, list):
            raise PublicationError("invalid job IDs in RUN_INFO.json")
        attempts = info.get("attempt_jobs", {})
        job_pattern = JOB_ID[self.scheduler]
        if not isinstance(attempts, dict) or any(
            not re.fullmatch(r"[1-9][0-9]*", str(attempt))
            or not re.fullmatch(job_pattern, str(job))
            for attempt, job in attempts.items()
        ):
            raise PublicationError("invalid attempt job IDs in RUN_INFO.json")
        job_ids = [info.get("build_job_id"), info.get("run_job_id"),
                   *additional, *attempts.values()]
        job_ids = [item for item in job_ids if item is not None]
        if not job_ids or any(not re.fullmatch(job_pattern, str(item)) for item in job_ids):
            raise PublicationError("RUN_INFO.json lacks exact cluster allocation IDs")
        # Older jobs may be gone after the scheduler's retention (a Kubernetes
        # TTL, PBS or PJM history); the run's latest job must still be found,
        # which also proves the namespace, context or server are the run's.
        for job_id in sorted({str(item) for item in job_ids}):
            older = job_id != str(info.get("run_job_id") or info.get("build_job_id"))
            local = LOCAL_JOB.fullmatch(job_id) if self.scheduler in {"pbs", "pjm"} else None
            if local is not None:
                self._require_local_stopped(job_id, local["batch"], local["token"], allow_removed=older)
            elif self.scheduler == "lsf":
                self._require_lsf_stopped(job_id)
            elif self.scheduler == "kubernetes":
                self._require_kubernetes_stopped(job_id, allow_removed=older)
            elif self.scheduler == "pbs":
                self._require_pbs_stopped(job_id, allow_removed=older)
            elif self.scheduler == "pjm":
                self._require_pjm_stopped(job_id, allow_removed=older)
            else:
                self._require_slurm_stopped(job_id)

    def _require_lsf_stopped(self, job_id):
        output = self._query([
            self.status_binary, "-a", "-noheader", "-o", "jobid stat", job_id,
        ], missing_lsf_job=job_id)
        rows = [line.split() for line in output.splitlines() if line.strip()]
        if not rows:
            self._require_lsf_history_stopped(job_id)
            return
        # Missing/purged, UNKNOWN, UNKWN and ZOMBI jobs do not prove writers stopped.
        # Require the exact allocation, not an array element or another job's row.
        if (len(rows) != 1 or len(rows[0]) != 2 or rows[0][0] != job_id
                or rows[0][1] not in {"DONE", "EXIT"}):
            raise PublicationError(f"LSF allocation {job_id} has no confirmed terminal status")

    def _require_lsf_history_stopped(self, job_id):
        # bjobs retains finished records for CLEAN_PERIOD (normally one hour).
        # Search retained event logs when an old build/allocation was purged.
        history = self._query([self.history_binary, "-a", "-l", "-n", "0", job_id])
        ids = re.findall(r"(?m)^Job <([^>]+)>", history)
        events = re.findall(
            r"(?m)^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
            r"\d{1,2}\s+\d{2}:\d{2}:\d{2}(?:\s+\d{4})?:\s*(.*)",
            history,
        )
        # Last event must confirm termination: an earlier DONE followed by a
        # requeue/start, missing history, or a recycled ID cannot finalize.
        if (ids != [job_id] or not events or not re.match(
            r"(?:Done successfully|Exited with exit code \d+|Exited by signal \d+)(?:[.;\s]|$)",
            events[-1],
        )):
            raise PublicationError(f"LSF allocation {job_id} has no confirmed terminal history")
        # Recheck live state after history lookup to catch requeued jobs.
        current = self._query([
            self.status_binary, "-a", "-noheader", "-o", "jobid stat", job_id,
        ], missing_lsf_job=job_id)
        rows = [line.split() for line in current.splitlines() if line.strip()]
        if rows and (len(rows) != 1 or len(rows[0]) != 2 or rows[0][0] != job_id
                     or rows[0][1] not in {"DONE", "EXIT"}):
            raise PublicationError(f"LSF allocation {job_id} became active during history lookup")

    def _require_slurm_stopped(self, job_id):
        # Query the live queue too: a PREEMPTED accounting row may be requeued.
        active = self._query([
            self.status_binary, "--noheader", f"--jobs={job_id}", "--format=%i|%T",
        ])
        if active.strip():
            raise PublicationError(f"Slurm allocation {job_id} is still visible in squeue")
        accounting = self._query([
            self.accounting_binary, "--noheader", "--parsable2", f"--jobs={job_id}",
            "--format=JobIDRaw,State",
        ])
        states = []
        for line in accounting.splitlines():
            fields = line.strip().split("|")
            if len(fields) >= 2 and fields[0] == job_id:
                state = fields[1].strip().split()
                states.append(state[0].removesuffix("+") if state else "")
        # Only the allocation record establishes termination, never .batch/.extern.
        # Failed runs may still publish final evidence; this is not a success verdict.
        if not states or any(state not in TERMINAL for state in states):
            raise PublicationError(f"Slurm allocation {job_id} has no confirmed terminal accounting")

    def _require_kubernetes_stopped(self, job_id, *, allow_removed=False):
        def pods():
            output = self._query([self.status_binary, *self.kubectl_args, "get", "pods",
                                  f"--selector=job-name={job_id}", "-o", "json"])
            try:
                return json.loads(output)["items"]
            except (ValueError, KeyError, TypeError):
                raise PublicationError(f"Kubernetes Job {job_id} has no readable Pods") from None

        output = self._query([self.status_binary, *self.kubectl_args, "get", "job", job_id, "-o", "json"],
                             missing_kubernetes_job=True)
        if output is None:
            if not allow_removed:
                raise PublicationError(f"Kubernetes Job {job_id} is not found: publish before its TTL "
                                       "and check the namespace and context")
            if pods():
                raise PublicationError(f"Kubernetes Job {job_id} is gone but its Pod is not")
            return
        try:
            job = json.loads(output)
        except ValueError:
            raise PublicationError(f"Kubernetes Job {job_id} has no readable status") from None
        if not isinstance(job, dict) or job.get("metadata", {}).get("name") != job_id:
            raise PublicationError(f"Kubernetes Job {job_id} has no readable status")
        annotations = (job.get("metadata") or {}).get("annotations") or {}
        for condition in (job.get("status") or {}).get("conditions") or ():
            if condition.get("status") != "True":
                continue
            if condition.get("type") in {"Complete", "Failed"}:
                return
            # The Harness cancels by suspending and annotating; it has ended
            # once its Pod is gone. A queue's suspension is not an end.
            if condition.get("type") == "Suspended" and "rsi-harness.io/cancelled" in annotations:
                if pods():
                    break
                return
        raise PublicationError(f"Kubernetes Job {job_id} has no confirmed terminal status")

    def _require_local_stopped(self, job_id, batch, token, *, allow_removed=False):
        # Its runner writes "<exit> <epoch> <done|timeout>" in the job's directory,
        # <run_dir>/{build,run}/<name>-<token>/end, once everything it started has
        # ended; without one, the job ended only if its batch job did.
        for phase in ("build", "run"):
            for end in (self.run_info.parent / phase).glob(f"*-{token}/end"):
                try:
                    exit_code, ended, how = end.read_text().split()
                    int(exit_code), float(ended)
                except (OSError, ValueError):
                    continue
                if how in {"done", "timeout"}:
                    return
        try:
            if self.scheduler == "pbs":
                self._require_pbs_stopped(batch, allow_removed=allow_removed)
            else:
                self._require_pjm_stopped(batch, allow_removed=allow_removed)
        except PublicationError as error:
            raise PublicationError(f"local job {job_id} has no end record; {error}") from None

    def _require_pbs_stopped(self, job_id, *, allow_removed=False):
        # Finished jobs stay in qstat -x for the server's job history.
        output = self._query([self.status_binary, "-x", "-f", "-F", "json", job_id], missing_pbs_job=True)
        if output is None:
            if not allow_removed:
                raise PublicationError(f"PBS job {job_id} is not found: publish within the server's job "
                                       "history and check the server")
            return
        try:
            # Values may hold control characters.
            jobs = json.loads(output, strict=False)["Jobs"]
        except ValueError:
            # Some servers escape unusual values badly in JSON; the plain listing has the state.
            state = self._pbs_text_state(job_id)
        except (KeyError, TypeError):
            raise PublicationError(f"PBS job {job_id} has no readable status") from None
        else:
            found = [value for key, value in jobs.items() if _same_pbs_job(job_id, key)
                     ] if isinstance(jobs, dict) else []
            if len(found) != 1 or not isinstance(found[0], dict):
                raise PublicationError(f"PBS job {job_id} has no readable status")
            state = found[0].get("job_state", "")
        # F: finished; X: a finished subjob. Exit_status is failure evidence only.
        if str(state).strip().upper() not in {"F", "X"}:
            raise PublicationError(f"PBS job {job_id} has no confirmed terminal status")

    def _pbs_text_state(self, job_id):
        lines = (self._query([self.status_binary, "-x", "-f", job_id], missing_pbs_job=True) or "").splitlines()
        header = re.fullmatch(r"Job Id: (\S+)", lines[0].strip()) if lines else None
        states = [line.split(" = ", 1)[1] for line in lines[1:] if line.startswith("    job_state = ")]
        if (header is None or not _same_pbs_job(job_id, header.group(1)) or len(states) != 1
                or any(line.startswith("Job Id:") for line in lines[1:])):
            raise PublicationError(f"PBS job {job_id} has no readable status")
        return states[0]

    def _pjm_rows(self, argv, job_id):
        lines = [line.split() for line in self._query(argv).splitlines() if line.strip()]
        for index, words in enumerate(lines):
            if words and words[0] == PJM_COLUMNS[0] and set(PJM_COLUMNS) <= set(words):
                header = words
                break
        else:
            return []
        rows = [dict(zip(header, words)) for words in lines[index + 1:] if len(words) == len(header)]
        return [row for row in rows if row["JOB_ID"] == job_id]

    def _require_pjm_stopped(self, job_id, *, allow_removed=False):
        choose = ["-v", "--choose", "jid,st,ec,pc,sn", job_id]
        # pjstat lists unfinished jobs, pjstat -H ended ones.
        live = self._pjm_rows([self.status_binary, *choose], job_id)
        states = {row["ST"].upper() for row in live}
        if "ERR" in states:
            raise PublicationError(f"PJM job {job_id} is held (ERR): pjdel the exact owned job")
        if states - PJM_ENDED:
            raise PublicationError(f"PJM job {job_id} is still active")
        ended = self._pjm_rows([self.status_binary, "-H", "day=31", *choose], job_id)
        if not ended and not live:
            if allow_removed:
                return
            raise PublicationError(f"PJM job {job_id} is not found: publish within 31 days of its end "
                                   "and check the cluster")
        if len(ended) != 1 or ended[0]["ST"].upper() not in PJM_ENDED:
            raise PublicationError(f"PJM job {job_id} has no confirmed terminal history")

    def _publication_final(self, state, requested):
        # Called under the publisher lock, including recovery of a lost push.
        info = self._manifest(allow_missing=True)
        if info is None:
            # Progress can be salvaged without a manifest, never finalized.
            if super()._publication_final(state, requested):
                raise PublicationError("exact RUN_INFO.json unavailable; cannot confirm final publication")
            return False
        epoch = [info.get("attempt", 1), info.get("run_job_id")]
        previous = state.get("cluster_attempt")
        if (previous is not None and previous != epoch) or (
            previous is None and info.get("state") not in {"completed", "failed"}
        ):
            # Keep pending commits/trees for idempotent push recovery, but their
            # finality belongs to the old allocation, not this resumed attempt.
            state["final"] = False
            state.pop("pending_final", None)
        state["cluster_attempt"] = epoch
        final = super()._publication_final(state, requested)
        if final:
            self.require_stopped()
        return final


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "once", "watch"))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--run-info", type=Path, required=True)
    parser.add_argument("--remote", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--secret-env", action="append", default=[], metavar="NAME")
    parser.add_argument("--scheduler", choices=tuple(ADAPTERS), required=True)
    parser.add_argument("--status-binary")
    parser.add_argument("--accounting-binary")
    parser.add_argument("--history-binary", default="bhist")
    parser.add_argument("--kubeconfig", help="Kubernetes: the profile's kubeconfig")
    parser.add_argument("--context", help="Kubernetes: the profile's context")
    parser.add_argument("--namespace", help="Kubernetes: the profile's namespace")
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--pid", type=int, help="actual host Harness CLI PID")
    parser.add_argument("--interval-seconds", type=float, default=1800)
    parser.add_argument("--transfer-timeout-seconds", type=float, default=900)
    args = parser.parse_args(argv)
    if not math.isfinite(args.interval_seconds) or args.interval_seconds <= 0:
        parser.error("interval must be positive and finite")
    if args.mode == "watch" and (args.pid is None or args.pid <= 0 or args.final):
        parser.error("watch requires a positive --pid and does not accept --final")
    if args.scheduler == "kubernetes" and not args.namespace:
        parser.error("--scheduler kubernetes requires --namespace")
    if args.final and args.mode != "once":
        parser.error("--final is valid only with once after all writers stopped")
    try:
        publisher = ClusterPublisher(
            args.repo, args.run_dir, args.remote, args.branch,
            state_dir=args.state_dir, secret_names=tuple(args.secret_env),
            transfer_timeout_seconds=args.transfer_timeout_seconds,
            run_info=args.run_info, scheduler=args.scheduler, status_binary=args.status_binary,
            accounting_binary=args.accounting_binary,
            history_binary=args.history_binary,
            kubectl_args=[
                *(("--kubeconfig", args.kubeconfig) if args.kubeconfig else ()),
                *(("--context", args.context) if args.context else ()),
                *(("--namespace", args.namespace) if args.namespace else ()),
            ],
        )
        if args.mode == "watch":
            return watch(publisher, args.pid, args.interval_seconds)
        ready = publisher.preflight()
        if args.mode == "preflight":
            print(json.dumps(ready), flush=True)
        else:
            print(json.dumps(publisher.publish(final=args.final)), flush=True)
        return 0
    except (PublicationError, OSError, ValueError) as error:
        detail = str(error) if isinstance(error, PublicationError) else type(error).__name__
        print(f"Publication blocked: {detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
