Status: DONE

Phase 11 is the documentation + migration-path sweep. `OVERVIEW.md`
goes from a Phase-0 stub to the full architecture document — it now
covers routing, lifecycle, graceful shutdown, config-flow forwarding,
the Option B entity bridge, the service/event mirror, scoped auth,
opt-in data sharing, Store routing, the test infrastructure, and the
explicit list of v2-deferred follow-ups (Phase 5b / 10b /
data_schema serialisation / unique_id propagation / share_states
filtering / concurrent channel dispatcher / non-idempotent service
handlers / v1 removal). The decision log is closed out:
`docs/entity-bridge-decision.md` was already in place from Phase 1,
and `docs/auth-scoping-decision.md` is new — it captures why
`scopes` lives on `RefreshToken` itself (vs a subclass), the
`_scope_allows` grammar (prefix grants for `sandbox_v2/`,
exact matches for `auth/current_user`), the per-group sharing
defaults (`built-in` / `main` all on, `custom` all off), and what
the subscription consumer still needs to do once the sandbox→main
websocket lands. `README.md` matches the shape of `sandbox/README.md`
with a Phase-1-through-10 status block and a clear "v1 still lives
in `sandbox/`" pointer. A directory-local `sandbox_v2/CLAUDE.md`
points future Claude sessions at the right files (mirrors
`sandbox/CLAUDE.md` for v1 — auto-loads when working inside
`sandbox_v2/`); the repo-root `CLAUDE.md` / `AGENTS.md` stay focused
on core-wide guidance, since the directory-local file is the right
discovery hop. The v1 removal item stays deferred per plan —
re-evaluate after Phase 10b's compat sweep lands a real baseline.

Files added:
- `sandbox_v2/CLAUDE.md`
- `sandbox_v2/docs/auth-scoping-decision.md`

Files changed:
- `sandbox_v2/OVERVIEW.md` — replaced the Phase-0 stub with the full
  v2 architecture doc.
- `sandbox_v2/README.md` — refreshed status block (Phases 0-10
  shipped, 5b / 10b deferred) and aligned shape with
  `sandbox/README.md`.
- `sandbox_v2/plan.md` — Phase 11 section marked complete with
  per-checkbox status and an inline note on the deferred v1 removal.

Core HA files modified (review surface):
- None. (Phase 11 is documentation only.)

Test results:
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` →
  **91 passed** (unchanged from Phase 10).
- `uv run pytest /home/paulus/dev/hass/core/sandbox_v2/hass_client/ -q`
  → **43 passed** (unchanged from Phase 10).
- `uv run prek run --files sandbox_v2/OVERVIEW.md sandbox_v2/README.md
  sandbox_v2/CLAUDE.md sandbox_v2/plan.md
  sandbox_v2/docs/auth-scoping-decision.md` → all hooks pass
  (codespell, prettier; ruff / mypy / pylint correctly skip
  Markdown-only changes).

Things to flag for the next phase:

- **There is no Phase 12.** The plan ends here; the remaining work
  is the explicitly-tracked Phase 5b (28 domain proxies) and Phase
  10b (compat baseline), plus the open follow-ups enumerated in
  `OVERVIEW.md`'s "Where the design is still open" section. Each
  follow-up is independent and can land as its own PR.
- **v1 removal is the one item still in this plan.** Stays deferred
  until v2 has matched v1's compat numbers (Phase 10b) and shipped
  at least one stable release. When that day comes, the touch list
  is small: `sandbox/`, `homeassistant/components/sandbox/`, the
  `tests/components/sandbox/` tree, any CODEOWNERS line for v1, and
  the `sandbox/CLAUDE.md` discovery hop. The v1 surface has been
  stable since this work started so the cleanup is straightforward
  whenever the trigger fires.
- **A migration script for v1 → v2 entries is not in scope.** Open
  question 4 from the plan ("What's the migration story for users
  on v1 sandbox today?") still wants an answer eventually:
  v1-tagged entries use `entry.options["sandbox"] = "<id>"`, v2
  uses `entry.data["__sandbox_group"]`. A script that walks the
  config-entry store and flips the tag is the obvious shape; it
  blocks the v1 removal item above but not the rest of v2.
- **The top-level `CLAUDE.md` and `AGENTS.md` were left
  un-modified.** They already point at core-wide concerns
  (PR template, Python 3.14 syntax, test conventions, etc.) and
  aren't the right place to call out v2 specifically — the
  directory-local `sandbox_v2/CLAUDE.md` auto-loads whenever Claude
  reads or edits a file under `sandbox_v2/`, which is the hop a
  future session actually needs. Mentioning v2 at the repo root
  would also need the same line for v1 (it isn't there today). If
  a future maintainer disagrees, the change is a one-line addition
  to both files.
- **Decision docs are now two — they could grow.** The
  per-phase STATUS files capture phase-local rationale, but
  longer-running decisions (like "we ship JSON over stdio rather
  than a websocket between manager and runtime", or the
  "concurrent channel dispatcher" follow-up's eventual shape)
  could plausibly become their own files under `docs/`. No need
  yet; flagging the pattern so the directory doesn't sprawl
  unintentionally.
