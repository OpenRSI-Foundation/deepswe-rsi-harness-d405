# Native macOS Docker Desktop

Follow the exact bundled Harness version's native Mac guide, normally at
`docs/macos-docker-desktop.md`. The file locates instructions; its presence is
not proof of backend support. Use the supported task compilation and environment
planning checks, then require the backend capability checks and real Oracle/Judge
acceptance below. Harness `run --dry-run` is a cluster-only option, not a local
Mac validation command. A reachable Docker daemon or a newer Skill alone is not
support. If the bundle lacks the required capability, use the authorized intake
refresh or an accepted Linux/cluster host; do not bypass a failed capability check.

The initial supported path is CPU-only, non-sandbox, split-WORKDIR tasks on
Docker Desktop. Require the bundled backend's capability check on the selected
daemon; do not substitute another Docker-compatible VM or a remote daemon.
Run the controller and publication helper as the Mac user, **without sudo**;
Linux sudo instructions in the workflow apply only to Linux. The trusted firewall
helper operates in Docker Desktop's Linux daemon; acknowledge its documented
capabilities and image as part of the execution envelope. Work/Judge identities,
isolation and network policies stay fixed.

The default environment planner stays read-only and reports unmeasured disk
capacity as pending. Before approved environment execution, measure both the
Docker VM filesystem and the host filesystem backing its sparse disk image.
Use `--docker-capacity-probe-image <trusted-cached-image>` and
`--acknowledge-authorized`, plus `--docker-backing-path <existing-host-path>`
from the selected Docker Desktop disk-image location. Use the actual configured
path, not a guessed default or the daemon's similarly named host path. The
cached image must provide `/bin/df -Pk` (GNU and BusyBox are supported); the
bounded, networkless probe uses its exact image ID and removes its temporary
container. The accepted headroom is the smaller of VM free space and host free
space. Missing either measurement remains pending and blocks execution, not
planning. Include these options again for approved environment work, since disk
usage can change after the plan.

Use native Oracle for a compatible general baseline and require the normal
full acceptance on the final task. Confirm private Judge volume access denial,
exported evidence/rewards, cleanup and the selected credential route. Generic
Docker/model connectivity is insufficient. Standalone Judge `codex-login`
renewal is unsupported; use an accepted API route or separately validated lent
Work login. Validate local Codex authentication with the declared Work user,
including credential-file ownership; do not change the task user or waive an
ownership failure to get a pass.
A short login smoke does not establish long-duration refresh. Public Science
uses its standalone Discovery validation procedure; Mac Oracle is not a
substitute for integrity/rubric validation.
