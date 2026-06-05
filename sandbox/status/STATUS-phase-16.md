Status: DONE

Phase 16 ships the cross-integration compat sweep + categorised backlog
the plan called for. The sweep ran every classifier-routable,
config-entry-based integration (807 in total) through the in-process
compat plugin in **705s wall** at concurrency=6 — well inside the
30-90 min budget the plan called out. **561/807** integrations pass
cleanly; **33 714/34 378** tests pass — a **98.07 %** test-level rate
across the broader set (Phase 15's 37-integration baseline was
99.19 %, so the broader sweep is a little noisier as expected). The
categoriser (`categorize_failures.py`) buckets **98.6 %** of the 664
failures, clearing the plan's ≥95 % gate; `BACKLOG.md` is hand-curated
on top of the auto-draft `generate_backlog.py` produces, with proposed
fixes + rough sizes per bucket. The headline takeaway is the same as
Phase 15's, just at scale: **640 of 664 failures (96.4 %) are the
`__sandbox_group` autotag noise** Phase 15 already flagged; landing the
"move sandbox-group tag off `entry.data`" follow-up clears all of them
and lifts the rate above the 99.5 % v1-removal threshold. The two real
bridge findings are scoped to two integrations: `dependencies-not-shared`
(`azure_event_hub`+1; test mocks installed in main never reach the
sandbox subprocess) and `proxy-missing` (`atag`; climate +
water_heater entities register in the sandbox but main's registry /
state machine never sees them). **No core HA files touched** — Phase
16 is sweep tooling + documentation only.

The runner forks rather than extends `run_compat.py` (per the plan's
"or fork into `run_compat_full.py`" carve-out). Two reasons: the
Phase-15 runner stays the way Phase 15's curated 37-integration report
expects it, and the new runner has a different shape — asyncio +
JUnit XML + outer concurrency vs the Phase-15 sync-subprocess loop +
text-output parsing. The per-integration parallelism the plan
suggested (`pytest-xdist -n auto`) is wired behind `--xdist` but stays
off by default: xdist worker spin-up cost dominates for the typical
sub-30-test integration, and the outer asyncio concurrency is what
actually drops the sweep from ~70 min serial to ~12 min. xdist is
there for individual long integrations (e.g. zwave_js at 608 tests /
65s) when someone wants to iterate on the backlog locally.

The categoriser's rule set is intentionally regex-on-traceback-excerpt
because the alternative (parsing pytest's tree, importing the test
module, or running a custom collector) buys precision the bucket
labels don't need. Rules are ordered most-specific → most-generic so a
real-bug rule fires before a catch-all picks up. The `mappingproxy(...)`
patterns are the broadest — the autotag is the only thing in HA Core
that turns a regular `entry.data == {…}` assertion into a
`mappingproxy(…) == {…}` failure — but the rule is gated on `'built-in'`
/ `'custom'` (the autotag's only possible group values) so a future
non-autotag mappingproxy mismatch still lands in `unknown`. The
re-purposed `proxy-missing` rule that catches both
`async_is_registered(...) == False` and `hass.states.get(...) is None`
is the one place the rule set is interpretive rather than mechanical —
both shapes point at "entity registered in sandbox but main never
saw it", which is the same fix story even if the proxy class itself
exists.

Files added:
- sandbox_v2/run_compat_full.py — the sweep runner (asyncio + JUnit
  + outer concurrency).
- sandbox_v2/categorize_failures.py — the categoriser (regex rules +
  JSON rollup).
- sandbox_v2/generate_backlog.py — the auto-draft BACKLOG.md skeleton
  generator (the committed BACKLOG.md is hand-curated on top of it).
- sandbox_v2/COMPAT_FULL.md — auto-generated per-integration results
  table (807 rows).
- sandbox_v2/COMPAT_FULL.csv — machine-readable companion to
  COMPAT_FULL.md.
- sandbox_v2/BACKLOG.md — hand-curated categorised remediation plan
  with proposed fixes + rough sizes.
- sandbox_v2/BACKLOG_FAILURES.json — machine-readable rollup
  (`{bucket → {integration → [{node_id, excerpt}]}}`).
- sandbox_v2/STATUS-phase-16.md (this file).

Files changed:
- sandbox_v2/plan.md — Phase 16 marked complete with the per-checkbox
  summary block.

Core HA files modified (review surface):
- None. (Phase 16 is sweep tooling + documentation only.)

Test results:
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` →
  **134 passed** (no regression from the Phase 15 baseline of 134).
- `cd sandbox_v2/hass_client && uv run pytest -q` →
  **51 passed** (no regression from Phase 15's 51).
- `uv run prek run --files <8 changed files>` → all hooks pass
  (ruff-check, codespell, prettier, check-json).
- Full sweep:
  - `cd sandbox_v2 && uv run python run_compat_full.py --concurrency=6 --timeout=180`
    → 807 integrations exercised in 705s wall; 561 pass, 246 with
    failures; 33 714 tests pass / 34 378 collected (98.07 %).
  - `uv run python categorize_failures.py` → 655/664 failures
    bucketed (98.6 %).

Things to flag for the next phase:

- **The "move `__sandbox_group` off `entry.data`" follow-up is now the
  single highest-leverage fix in the entire v2 codebase.** 96.4 % of
  every failure across 807 integrations clears with one ~80–120 LOC
  patch. Phase 15 flagged this; Phase 16 quantifies it. The two viable
  shapes (side-channel mapping vs re-derive-on-lookup) are spelt out
  in `BACKLOG.md::test-only`. Either lands the test-level pass rate
  above the 99.5 % v1-removal threshold the plan asks for.
- **`atag` is a microcosm of every remaining real-bug bucket.** It's
  the only integration in `proxy-missing` (5 failures), one of the two
  in `dependencies-not-shared` (1 failure), and three of the seven in
  `unknown` (3 failures). Fixing atag's specific coordinator-shape
  bug — climate + water_heater registering in the sandbox but main
  never surfacing them — likely closes 9 of the 24 remaining
  bridge-real failures in one go.
- **The compat plugin's mock-propagation gap is the next real
  protocol decision.** `azure_event_hub` (9 failures) and atag (1)
  both fail because `unittest.mock.patch` installed in the main test
  process doesn't reach the sandbox subprocess. The in-process plugin
  could plausibly close this with a fixture re-entry hook (option (b)
  in `BACKLOG.md::dependencies-not-shared`); the subprocess plugin
  needs a sandbox-aware mock channel that v2 won't ship. Worth
  deciding before option (b)'s 40 LOC lands so the subprocess plugin
  isn't left without a story.
- **The `unknown` bucket has 9 environmental rows that won't go away
  without integration-level test fixes** (bluetooth: `habluetooth`
  version skew; chess_com, mastodon: `tzlocal()` vs `tzutc()`
  fragility; html5: freezegun + tz; google: token-refresh; insteon:
  websocket error envelope). Six are not v2 bridge bugs. Worth
  filing upstream as integration-test issues rather than carrying
  them as v2 follow-ups.
- **`run_compat_full.py` shells out to `uv run python -m pytest` per
  integration** — same dependency on the core venv being present that
  `run_compat.py` already has. With concurrency=6 on the test box the
  sweep finished in 12 min; on a smaller box (4 cores) it'll be
  closer to 30 min. The plan's 30-90 min budget covers both.
- **The categoriser's regex rules are easy to extend** — every new
  bucket signature is one `Rule(...)` tuple. Watch for `unknown`
  bucket creep on the next sweep; if it gains rows that aren't
  environmental, add rules and re-run rather than letting the bucket
  drift wide.
- **`generate_backlog.py` produces a draft skeleton that BACKLOG.md
  was written on top of, not the committed artefact directly.** The
  committed `BACKLOG.md` is hand-curated; running `generate_backlog.py
  --out BACKLOG.md` would overwrite the curated content with the
  TODO-marker skeleton. Document the workflow in CLAUDE.md if anyone
  else needs to regenerate.
