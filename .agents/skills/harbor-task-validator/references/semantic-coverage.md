# Scientific definitions in executable checks

The rubric-specific sections apply to Discovery and existing rubric-runtime tasks.
For metric Benchmark, check evaluator semantics against the agreed metric and
validity constraints; model-evidence transport and per-rubric review do not apply.

Use this reference when a Science task translates a substantive definition into
checker code, particularly when several results consume that definition. It
extends the existing coverage and review, not the Judge ABI or scoring policy.
A model-reviewed proof needs no invented numerical checker or known solution.

## Trace the calculation, not just the evidence mapping

For nontrivial computations where aggregation, shared definitions or evidence
handling can change acceptance, use the existing `tests/coverage.md` to connect:

- the source definition and scope, units, normalization, aggregation order,
  uncertainty convention or information boundary that matters to the result;
- the implementing entry point and relevant consumers, including contrasts,
  resampling or alternative evidence routes if they use the same definition;
- a bounded input that distinguishes the correct interpretation from a
  plausible incorrect one, with its independently derived expected outcome;
- the owning execution-validation check, result artifact and tested/pending
  status. Existing fixtures and reports may supply this evidence.

Scale this work to the implementation risk. Reuse an existing adequate test or
direct derivation; do not demand a new fixture for every rubric or trivial
calculation. These are not new contract fields or a mandatory table layout. Inspect actual
code; an identifier, comment, matching contract hash or successful evidence-delivery test
does not prove numerical semantics. Avoid exhaustive testing demands unrelated
to the confirmed requirements. One discriminating case can be more useful than
many nominal cases where correct and incorrect formulas happen to agree.

Source generation prepares fixtures/procedures; source review reads them under
its existing no-execution rule. Authorized execution validation exercises the
delivered code path, not a reimplementation of it in the fixture. A synthetic
case validates an implementation property, never the research claim itself.

## Bounded review and correction

When a finding corrects a shared definition, identify consumers whose acceptance
calculation depends on that correction and inspect them in targeted re-review.
This can include duplicated formulas that do not call the corrected helper;
state the concrete dependency rather than searching every similarly named
quantity or reopening every rubric. Record which paths were checked and
which execution assertions remain pending. A fixture where both formulas give
the same answer cannot establish that this particular defect is closed.
Unrelated paths remain outside targeted re-review. Report concrete departures
from the confirmed contract under the existing finding rules; do not manufacture
new requirements to make a task easier to review.

Preserve the difference between a source-review PASS, executed validation and a
scientific result. Prepared but unrun fixtures are not passing test evidence.
