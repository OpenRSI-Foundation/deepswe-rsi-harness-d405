## CPU optimization checks

For CPU optimizations adopted in task implementation or used to justify the
resource estimate, reuse the dry-run/smoke evidence where sufficient; otherwise
run a bounded comparison within the authorized validation budget on the target
execution environment. Contributor suggestions are inputs, not required methods.
Select a small comparison set containing the reference configuration and suitable,
evidence-backed alternatives, using the workload, software evidence and contributor
suggestions. Size the set to fit the authorized validation budget after reserving
required checks and final acceptance. Run every configuration selected for that
comparison before choosing among them; do not select an untested alternative on
expected speed alone. If only the reference is suitable, explain why rather than
inventing alternatives. Within authorized task-local repair scope and
the validation budget, the Agent may modify the task repo and switch to a better
validated configuration or implementation. Reuse the existing validation
authorization; ask only about missing or expanded scope, not for a separate
optimization allowance. Preserve scientific conditions,
accuracy, evidence requirements and isolation. Optimizing the research method
itself remains formal research, not a validation prerequisite. Finish the selected
comparison rather than stopping at the first improvement.
If a configuration is infeasible or the budget is reached, record the missing
comparison and its reason; use a validated configuration provisionally without
claiming it is best among untested alternatives. Do not extend the search or
budget automatically.

Compare with a suitable reference configuration on the same representative
input and comparable allocated resources. Check outputs against the task's
existing correctness/accuracy conditions before interpreting speed. Record the
configurations, CPU/thread allocation, elapsed time and peak memory when material;
distinguish Work costs from complete Judge costs. If timing variation could
change the choice, repeat within budget or mark the gain inconclusive. Explain
whether to retain the optimization, use the validated reference or leave the
choice pending. Retain the reference configuration for comparison or rollback;
if no alternative shows a justified benefit, keep it. After switching, rerun the
affected checks and ensure full Judge acceptance covers the final task version;
pre-change evidence alone cannot certify changed behavior.

In the existing contributor-facing validation handoff, summarize the comparison
set and selection rationale, correctness and performance results, the chosen
configuration and why, and any selected configuration not run or not completed
with its reason. Explain material exclusions without cataloguing every conceivable
optimization. Do not ask the contributor to approve each in-scope trial. Keep
unexplored research methods optional.

Use the measured costs to revise estimates and internal deadlines within confirmed
limits. Report small-case results as small-case evidence, not a promised full-scale
speedup. Missing comparison evidence cannot justify a speedup claim or reduced
budget estimate; if feasibility depends on that claim, keep it unresolved until
validated. Seek confirmation for changes to committed resources or scientific
conditions. These checks add no speedup threshold or scientific scoring item.

