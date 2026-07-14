---
name: 9tc-cost-control
description: Cost-control and estimating workflow for the 9 Turnbull Court residential duplex. Use when work involves BOQ, budget, quote comparison, tender comparison, procurement recommendation, commitment, invoice, variation, forecast final cost, EAC, dashboard totals, GST basis, cost reconciliation, quantity-rate checks, or benchmark anomalies for the Turnbull Court project.
---

# 9TC Cost Control

## Configuration

Load `../../config/project.json` before preparing any cost output. Use the configured project identifiers, reference files, budget controls, reconciliation chain, deliverable sections, and required Checks.

## Workflow

1. Separate confirmed facts, assumptions, conflicts, and RFIs.
2. Preserve the configured budget controls as separate fields until source evidence reconciles them.
3. Reconcile every cost line through BOQ -> budget -> quote -> award -> commitment -> invoice -> variation -> forecast final cost -> EAC.
4. Keep raw imported records separate from normalised control tables.
5. Maintain quantity, unit, rate, amount, source, revision/date, dwelling allocation, allowance type, committed cost, paid cost, forecast final cost, and variance.
6. State every amount in AUD and whether it includes or excludes GST.
7. Never compare rates with incompatible units or materially different scopes.

## Required checks

Flag these issues in a visible Checks section:

- Unreconciled totals between workbook tabs.
- Missing source references or unconfirmed data sources.
- Quantity-rate anomalies, zero quantities, lump-sum rates in quantity fields.
- Duplicate scope, exclusions, arithmetic errors, GST inconsistencies.
- Unapproved changes, stale data, broken links, and provisional assumptions.
- Bid lines more than 10% above or below the valid historical median.
- Fewer than three comparable records as `Insufficient history — benchmark provisional`.

## Output

Use tables for cost comparisons and recommendations. Include Status, Sources reviewed, Key findings, Actions / Owner / Due date, Assumptions and limitations, Next control point, and Checks.
