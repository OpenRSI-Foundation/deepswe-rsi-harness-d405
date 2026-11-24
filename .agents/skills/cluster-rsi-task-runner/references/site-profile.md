# Repository and cluster profile discovery

The user-facing stages mirror the single-node workflow:

```text
$multi-node-harbor-task-agent <approved proposal>
$cluster-harbor-task-validator ./task using /absolute/site.toml
$cluster-rsi-task-runner
```

Discover a task by `task.toml`, `instruction.md`, `environment/` and `tests/`;
exclude fixtures, evidence and scratch. Discover Harness by `pyproject.toml`
and `src/rsi_harness/cli.py`. Resolve ambiguity rather than selecting the newest
run or first directory. Accept relative task paths and report absolute roots.

Profile precedence: explicit user choice, matching accepted validation profile,
then a single repository-local configured profile. `RSI_CLUSTER_PROFILE` may
supply an explicit path; resolve conflicts with existing accepted evidence.
Missing/ambiguous site configuration is a prerequisite, not a reason to guess.

| Cluster | Profile adapter | Scheduler kind | Commands |
| --- | --- | --- | --- |
| LSF, including BlueVela | `bluevela` | `lsf` | `bsub`, `bjobs`, `bkill`, `blaunch`, `bhist` |
| Slurm | `slurm` | `slurm` | `sbatch`, `squeue`, `sacct`, `scancel`, `scontrol`, `srun` |
| Kubernetes | `kubernetes` | `kubernetes` | `kubectl` (Jobs and Pods in the profile's namespace) |
| PBS Pro | `pbs` | `pbs` | `qsub`, `qstat -x`, `qselect`, `qdel` |
| Fujitsu TCS (PJM) | `pjm` | `pjm` | `pjsub`, `pjstat` (`-H` for ended jobs), `pjdel` |

There is no `--cluster lsf` alias. Select the site's external TOML profile.
The selected Harness owns packaged profile discovery and site-specific setup.
Reuse the operator's configured profile and deployed runtime when available;
complete a copy of a packaged example when needed. A profile's presence alone
does not establish live readiness. Do not force Slurm
imports or command dependencies when using an LSF-only Harness checkout.

Resolve queue/group or partition/account/QoS, GPU density, shared image/run/log
roots, builder/Apptainer and scheduler binaries, container interpreter and
phase-scoped asset binds from the actual site. Never expose hidden Judge assets
to Work. Keep site profiles outside portable task code and canonical profiles
unchanged. LSF's `-x` is exclusivity; Slurm's `-x` excludes nodes. Kubernetes
runs each job as one Pod on one node (multi-node tasks need LSF or Slurm); its
shared volumes mount at the submit host's paths, and the runner image and Pod
security come from the profile. Pods run as the submitting (never root) user;
export the Agent's API key on the submit host (`--agent-auth local` is
refused), and keep secrets out of `scheduler.environment`. PBS and PJM also
run each job on one host and pass it the submit host's environment through a
private file; never use `qsub -V` or `pjsub -X`, which copy credentials into
job records, not even for a controller job. PBS needs the server's job history
(`qstat -x`). Preserve the accepted Work/Judge topology when selecting GPU
density and allocation shape; a profile change can alter their resource plan.

## Complete the selected profile

Use the selected Harness's cluster documentation for site setup. Keep packaged
profiles unchanged and operator-owned copies outside the task directory.
Resolve ordinary task settings directly from the
task and image rather than asking the contributor to invent paths:

- Set `[apptainer].workspace_target` to the image's effective `WORKDIR`,
  including an inherited base-image value. Set `container_python` to an actual
  Python 3.8+ executable inside that image; every cluster run needs it.
  Inspect the built image if the Dockerfile alone does not settle either
  value; `/workspace` and `/usr/bin/python3` in the templates are not universal
  task defaults.
- Match `task.toml` assets and runtime paths to real shared files. Add
  `work_binds` or `judge_binds` only for assets supplied outside the image,
  using their declared container targets and phase access. Assets already in
  the image need no extra bind; hidden Judge data belongs only in Judge.
- Resolve shared storage, scheduler account/project and runtime paths from the
  actual deployment. Reuse a compatible installed Apptainer and image cache;
  site runtime installation or patches belong to the Harness's site guidance.
- If login and compute architectures differ, use a matching Harness and native
  Agent CLIs for the controller, keeping the login environment for offline
  checks. Pass the compute executable in `--controller-executable`; its host
  needs the scheduler commands and Git access for monitoring and publication.
  `resources.node_machine` (the packaged Flow2 profiles: `aarch64`) makes
  Harness refuse a controller on another architecture before it submits; a dry
  run still plans.

Run the compute-node `site_check.sh` with the selected Apptainer and image,
then rerun preflight against the completed profile. Carry its path and
fingerprint into validation and the experiment.

Use Harness's environment for `scripts/preflight_task.py`; it compiles, checks
phase asset coverage, resolves resources and records fingerprints without
building, allocating or running task code. Missing credential names can remain
pending in offline output. Before live work resolve actual asset readiness,
authentication, scheduler access and storage headroom. Offline success is not
`EXECUTION READY`.

Preserve the resolved profile path/digest, task/Harness/image fingerprints,
accepted baseline, saved Agent budget and source/validation publication hashes
in validation evidence. The runner reuses matching evidence, checks live
prerequisites again, and revalidates only affected inputs after changes.

A missing cluster or credentials stops live stages with exact pending facts.
For a build-only/offline request, complete the static package without claiming
baseline acceptance or launching jobs.
