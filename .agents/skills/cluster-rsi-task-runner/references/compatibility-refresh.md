# Existing-task compatibility refresh

This is part of validator intake, not task regeneration or a new workflow.
Use the existing resource/repair/publication authorization; do not ask again
when it already covers the refresh. An inspection-only request permits a plan,
not replacement or execution. No repository-wide or bulk upgrade is implied.

1. Record the task, bundled Harness and installed Skill versions or content
   hashes, repository status and local patches. Identify the actual missing
   capability (for example cluster Oracle), rather than upgrading merely
   because a newer version exists. Preserve task inputs, scientific criteria,
   Judge visibility/network policy, resources and existing run evidence.
2. Resolve an accessible, reviewed source to an immutable commit. Normally use
   the public OpenRSI-Index Harness export and the matched RSI-Skills source;
   verify the required capability is actually present. A pending upstream PR
   does not mean the public export or this private task repo has it. Use a
   different reviewed source only when already authorized; otherwise report
   the missing release/access. Never require private-repo access when an
   approved public export or bundle is available.
3. Make a recoverable copy or snapshot outside the replacement directories,
   including uncommitted patches and needed ignored files. Stage the new bundle
   separately and compare it with the old one. Reconcile local modifications;
   do not delete the current tree or use a hard reset/force push to replace it.
   Finish this comparison before changing the repository's bundled copy. Do not
   upgrade a runtime used by a live job or rewrite frozen control files to make
   an old run resume on new code; retain its original runtime for recovery.
4. Refresh only the approved bundled Harness and the complete validator/runner
   Skill folders needed for the backend, including references and scripts.
   Preserve the local pair and add the cluster pair where needed. Rename legacy
   `multi-node-harbor-task-validator` / `multi-node-rsi-task-runner` installs
   to `cluster-harbor-task-validator` / `cluster-rsi-task-runner`, updating their
   callers and retaining one active copy per role; do not copy
   generator/controller secrets or caches. Keep Science-specific procedures and
   Judge-library versions unless their migration is separately in scope. Record
   old/new sources, hashes and reconciled patches in validation evidence; keep
   original generation provenance as historical evidence, not a new attestation.
5. Inspect the task against the selected runtime: Solution must prepare the
   agreed baseline, Judge must work under the actual execution identity, and
   commands/paths/resource options must match the backend. Repair only confirmed
   incompatibilities, including obsolete root-only isolation under the selected
   backend's accepted isolation contract. Do not add training, change the scientific target, replace
   the baseline or waive isolation to obtain a pass. Public Science retains its
   standalone scientific validation procedure; Oracle support alone does not replace model
   audit/rubric validation or migrate the Science Judge.
6. Install the refreshed Harness dependencies from its lockfile and re-run task
   compilation and backend planning. A refresh of only the bundled Harness and
   Skills keeps prior acceptance, validation evidence and results valid and
   needs no rerun. Run the environment, failure checks and full baseline
   acceptance only on a backend without accepted evidence, and repeat only the
   checks that task, Judge or isolation repairs affect. Rebuild images only
   when inputs/runtime requirements changed. Report site prerequisites
   separately from task defects; pending execution is not `EXECUTION READY`.
7. Update the task README with pinned versions, backend-specific validation/run
   commands and known limits. Publish only the reviewed source/bundle/README
   changes, then validation evidence separately, within the existing publication
   scope; honor local-only requests. On failure preserve both versions and the
   evidence, report the blocker and do not start research. Hand matching final
   fingerprints to the runner; the runner does not perform the upgrade itself.
