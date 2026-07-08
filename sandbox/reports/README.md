# Compat-lane reports archive

Dated snapshots of compat-lane runs and their analysis, one directory per
day (`YYYY-MM-DD/`). The root-level `sandbox/COMPAT.csv` /
`COMPAT_LATEST.md` are git-ignored per-run scratch output — anything worth
keeping gets copied here and committed, so a re-run can't clobber it.

Typical contents of a dated directory:

- `COMPAT.csv` / `COMPAT_LATEST.md` — the full-tree sweep results
  (`run_compat.py --jobs 8`) at the commit named inside the report.
- `COMPAT-issues-rerun.*` — a follow-up run of just the non-passing
  suites with `--tb=line` + wide columns, whose error dumps carry full
  one-line failure reasons for clustering.
- `clusters/` — failure-clustering output (`clusters.md` human summary,
  `clusters.json` machine dump, representative raw logs).
- `FINDINGS.md` — the diagnosis: what the top clusters are, root causes,
  and the fixes they suggest.

## Regenerating the clustering

`sandbox/cluster_failures.py` reads the per-integration error dumps
(`$SANDBOX_ERRORS_DIR`, default `/tmp/sandbox_errors/`) that
`run_compat.py` writes for every non-passing suite, normalizes each
`--tb=line` failure into a `<ExceptionType> @ <frame>: <message>`
signature, and clusters across integrations:

```bash
python sandbox/cluster_failures.py sandbox/reports/<date>/clusters
```

Run the sweep with `--tb=line` (the default now) so the dumps carry full
one-line reasons; `--tb=no` truncates them and the clustering degrades to
noise.
