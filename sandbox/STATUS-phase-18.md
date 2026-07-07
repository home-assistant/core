Status: DONE

Phase 18 reconciles three stale docs with the post-Phase-17 reality and
adds a single canonical "why we did each follow-up phase" history doc
at `sandbox_v2/docs/FOLLOWUPS.md`. OVERVIEW.md, the directory-local
CLAUDE.md, and README.md all carried Phase-5b / Phase-10b /
`data_schema`-stripping / `unique_id`-non-propagation /
concurrent-dispatcher-deadlock callouts that have since been closed by
Phases 12–17. After the sweep, the genuinely-still-open list is:
`share_states=True` subscription consumer (Phase 7's lone surviving
deferral), v1 removal (numerically satisfied — release-process gate
remains), diagnostic snapshot drift / clock pinning (test-side
residuals — fix lives in integrations' trees or as optional Phase 17b),
`calendar` / `todo` / `weather` query-shaped RPCs (no compat-sweep
demand surfaced yet), and non-idempotent service handlers (v3 spec).
BACKLOG.md needed no edit — Phase 17 already rewrote it as the
post-`ConfigEntry.sandbox` categorised backlog with every named
bridge bucket at zero.

**No Python code changes, no test changes, no core HA surface
touched.** In-tree test counts unchanged from Phase 17 (134 HA-core
sandbox_v2 + 51 hass_client).

Files added:
- sandbox_v2/docs/FOLLOWUPS.md
- sandbox_v2/STATUS-phase-18.md (this file)

Files changed:
- sandbox_v2/OVERVIEW.md — top status block rewritten to reflect
  Phase 17; routing-rules section now references `entry.sandbox`
  instead of `__sandbox_group`; config-flow forwarding section
  documents the 3rd router call site (`async_unload_entry`) +
  `ConfigFlowResult["sandbox"]` write path; "What's deferred"
  subsection removed (both items closed by Phase 14) and replaced
  with a positive description of how marshalling works today;
  "Domains shipped" updated (all 32 now ship, Phase 14 perf
  benchmark callout); "Service & event mirroring" updated (schema
  bridge in the wire payload); "Test infrastructure" updated
  (baseline numbers + `run_compat_full.py` / `BACKLOG.md` lineage);
  "Where the design is still open" pruned to the genuinely-open
  items only, with a FOLLOWUPS.md pointer.
- sandbox_v2/CLAUDE.md — "Read these first" updated to reflect
  Phases 0–17 and link FOLLOWUPS.md; "Core HA files modified"
  section folds in Phase 14's `async_unload_entry` hook and Phase
  17's `ConfigEntry.sandbox` field; "Open follow-ups (not yet
  shipped)" pruned to surviving items with FOLLOWUPS.md pointer.
- sandbox_v2/README.md — "Status" block enumerates Phases 0–17
  (was Phase 0–11) and adds the FOLLOWUPS.md pointer. The plan only
  named OVERVIEW.md and CLAUDE.md explicitly but the README's
  status block had drifted identically and would have pointed new
  readers at "Phase 5b deferred" / "Phase 10b deferred" for items
  that have since landed. Scope extension is small and stays
  squarely inside the spirit of Phase 18 (docs reconciliation only).
- sandbox_v2/plan.md — Phase 18 marked complete with the per-checkbox
  summary block.

Core HA files modified (review surface):
None.

Test results:
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` →
  **134 passed** (no change from Phase 17's 134 — docs-only phase).
- `uv run pytest /home/paulus/dev/hass/core/sandbox_v2/hass_client/ -q`
  → **51 passed** (no change from Phase 17's 51).
- `prek run --files sandbox_v2/OVERVIEW.md sandbox_v2/CLAUDE.md sandbox_v2/README.md sandbox_v2/docs/FOLLOWUPS.md`
  → codespell + prettier passed; all Python-specific hooks correctly
  skipped (no Python files in the change set).
- `grep -rn '__sandbox_group\|SANDBOX_GROUP_KEY' sandbox_v2/ homeassistant/components/sandbox_v2/ tests/components/sandbox_v2/`
  → no code-path matches. All matches are in STATUS / BACKLOG /
  plan.md / COMPAT.md / FOLLOWUPS.md / `generate_backlog.py`'s
  historical-shape string literal — all narrative or auto-draft text,
  not live code.

Things to flag for the next phase:

- **The "v2 has shipped at least one stable release" gate is now the
  only thing standing between today's tree and v1 removal.** That's
  not a code change — it's a release-process step. The numeric gate
  (Phase 11 attached it to "match v1's compat numbers") cleared on
  Phase 17 (99.67 % full sweep, 99.97 % v1 baseline; thresholds were
  99.5 %). When v2 ships in a stable release, the next-cycle PR can
  delete `sandbox/` and `homeassistant/components/sandbox/` along
  with the v1-only references in CLAUDE.md, the v1-vs-v2 comparison
  table in OVERVIEW.md, and the dual-tracker behaviour noted in
  CLAUDE.md's preamble.
- **FOLLOWUPS.md's "Still open" list and CLAUDE.md's "Open follow-
  ups" section say the same thing in the same order.** Intentional —
  they're the same source of truth, surfaced in two places (Claude
  loads CLAUDE.md, humans read FOLLOWUPS.md). If a new item closes
  or a new deferral opens, update both. A future docs-tightening pass
  could swap one for an inclusion of the other, but for now mirrored
  text is clearer than a `>>> include` directive that an editor might
  miss.
- **README.md was updated despite not being in the plan's explicit
  checklist.** Called out in the plan changes (and in this STATUS) so
  a reviewer expecting "OVERVIEW.md + CLAUDE.md + FOLLOWUPS.md only"
  sees the README diff and the reason. The plan said "If any other
  section references closed items, update it" for OVERVIEW.md; the
  README's "Status" block was the same shape, so it falls under the
  same rule even though the plan said "OVERVIEW.md" specifically.
- **BACKLOG.md needed no edit.** Phase 17 already rewrote it with the
  Phase-17 categorised numbers, the "test-only / __sandbox_group on
  entry.data" bucket replaced by the residual sub-shapes
  (`+ 'sandbox': 'built-in'` diagnostic snapshots + `'created_at'`
  drift), and every named bridge bucket at zero. The plan's
  "verify Phase 17 closed it" step confirmed the STATUS-phase-17
  claim is accurate.
- **No new historical-narrative `__sandbox_group` matches were
  introduced.** FOLLOWUPS.md mentions the string in three places (all
  in the Phase 15 / 16 / 17 narrative sections describing what the
  autotag *did*), all in markdown prose with backticks — narrative
  references, not code references. The grep verification passes.
