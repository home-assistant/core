---
name: 9tc-workbook-automation
description: Workbook automation and project data management workflow for the 9 Turnbull Court residential duplex. Use when work involves Google Sheets, Excel, XLSM, Apps Script, VBA macros, Power Query, IMPORTRANGE, QUERY, invoice import, Gmail invoice workflow, data consolidation, control workbook changes, named ranges, formulas, validations, conditional formatting, Checks sheets, dashboard refreshes, or PMO workbook exports for the Turnbull Court project.
---

# 9TC Workbook Automation

## Configuration

Load `../../config/project.json` before changing workbook structures, scripts, formulas, imports, or dashboards. Treat Google Sheets as cloud-primary and local Excel files as backup/offline/historical unless confirmed synchronised.

## Workflow

1. Retain a rollback copy before structural workbook changes.
2. Preserve formulas, data validation, conditional formatting, named ranges, query connections, locale `en_AU`, and timezone `Australia/Sydney`.
3. Keep raw imports separate from normalised control tables.
4. Ensure imported records retain source file, source sheet/page, source date, import date, and confidence/status.
5. Prefer visible, auditable formula logic over black-box automation.
6. Document all VBA macros, Power Query, Apps Script, `IMPORTRANGE`, and `QUERY` logic.
7. Protect formula cells while leaving designated input fields editable.
8. Design for new trades, dwellings, invoices, updated schedules, and future source files without structural rework.

## Required checks

Provide a Checks sheet or visible Checks section covering:

- Broken links and formula errors.
- Duplicate IDs.
- Unreconciled totals.
- Missing mandatory fields.
- Stale refresh dates.
- Source gaps.
- Automation health.
- Missing source file/sheet/page/date metadata.
- Provisional or unverified imported records.

## Output

Include instructions, navigation aids, and version/export notes. Export to Excel locally before issuing to external stakeholders when requested.
