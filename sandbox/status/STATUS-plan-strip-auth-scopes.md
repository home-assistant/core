# STATUS — plan-strip-auth-scopes

**Summary:** Reverted Phase 7's `RefreshToken.scopes` + websocket-dispatcher
enforcement from core HA; the sandbox now runs against a plain system-user
token. No on-disk migration — the auth-store load path silently drops a legacy
`scopes` key. All target test suites green; prek clean.

## Commits (branch `sandbox`, not pushed — parent pushes)

- **`5141f96ebe1`** — `sandbox_v2: strip RefreshToken.scopes from core; sandbox token goes plain`
  (Phase A core revert + Phase B sandbox helper + Phase C docs + tests). 14 files.
- **(this commit)** — `sandbox_v2: tick whats-changed for strip-auth-scopes + STATUS marker`
  (ticks the breaking-changes checkbox with the code-commit SHA, adds this file).

## File-by-file (Phase A — core revert)

- `homeassistant/auth/models.py` — deleted the `scopes: frozenset[str] | None`
  field from `RefreshToken`.
- `homeassistant/auth/__init__.py` — deleted the `scopes=` parameter from
  `AuthManager.async_create_refresh_token` and its forwarding to the store.
- `homeassistant/auth/auth_store.py` —
  - deleted `scopes=` from `AuthStore.async_create_refresh_token` (param +
    kwargs dict entry);
  - deleted the load-side `scopes = rt_dict.get("scopes")` read and the
    `scopes=frozenset(...)` kwarg, replacing them with a one-line silent-drop
    shim `rt_dict.pop("scopes", None)` (option A — no migration, no
    storage-version bump);
  - deleted the write-side `"scopes": sorted(...)` serialization.
- `homeassistant/components/websocket_api/connection.py` — deleted the
  module-level `_scope_allows` helper, the `"scopes"` `__slots__` entry, the
  `self.scopes = ...` assignment, and the `async_handle` enforcement branch.
  `async_handle` is back to its pre-Phase-7 shape. (`RefreshToken` import is
  still used by the `__init__` signature — kept.)

## File-by-file (Phase B — sandbox helper)

- `homeassistant/components/sandbox_v2/auth.py` —
  - deleted the `SANDBOX_TOKEN_SCOPES` constant (and its `__all__` entry);
  - `_get_or_create_sandbox_refresh_token` now takes `(hass, user)` and
    identifies the token by the **one-token-per-system-user invariant**
    (locked decision: option 2 — reuse `tokens[0]` if present, else create
    with no `scopes=`/`client_id=`). Token type stays `TOKEN_TYPE_SYSTEM`.
  - rewrote the module + helper docstrings to drop the Phase-7 scoping
    language.
  - `_user_name_for_group` / `_client_id_for_group` kept (the latter is unused
    but harmless, per the plan).

## Tests deleted vs added

- **Deleted:** `tests/components/websocket_api/test_scopes.py` (whole file, 140
  lines).
- **Deleted:** `tests/auth/test_init.py` — `test_refresh_token_scopes_default_to_none`
  and `test_refresh_token_scopes_round_trip_through_store`.
- **Added:** `tests/auth/test_auth_store.py::test_loading_drops_legacy_scopes_key`
  — hand-crafted on-disk auth store with a refresh token carrying
  `scopes: ["sandbox_v2/", "auth/current_user"]`; asserts it loads without
  error and the resulting `RefreshToken` has no `scopes` attribute.
- **Updated:** `tests/components/sandbox_v2/test_auth.py` — removed the
  `SANDBOX_TOKEN_SCOPES` import + `test_sandbox_token_scopes_allowlist`; dropped
  the `refresh.scopes == ...` assertion; added a
  `len(refresh_a.user.refresh_tokens) == 1` assertion documenting the invariant
  the helper now relies on.

## Doc updates (Phase C)

- `sandbox_v2/docs/auth-scoping-decision.md` — prepended the SUPERSEDED banner.
- `sandbox_v2/CLAUDE.md` — deleted the `auth/*` row from "Core HA files
  modified" (intro count "four core HA files" → "three core HA surfaces");
  rewrote the "Read these first" bullet to mark the design doc SUPERSEDED.
- `sandbox_v2/OVERVIEW.md` — rewrote the v1/v2 auth comparison row, the
  "Scoped auth" → "Sandbox auth" section, the `--token` CLI placeholder, and
  the summary-table "Auth scopes" row.
- `sandbox_v2/docs/FOLLOWUPS.md` — added a `plan-strip-auth-scopes` narrative
  section and a "Still open" bullet to re-introduce scope enforcement when the
  WS transport lands.
- `sandbox_v2/architecture.html` — Iron-Law callout, TOC, section-9 heading +
  body (scopes-on-RefreshToken / `_scope_allows` / why-not-a-subclass rewritten
  to "plain token, enforcement deferred"), the auth SVG boxes, the Phase-7
  timeline entry (annotated as reverted), the core-HA-modified list, the
  summary-table row, and the CLI `--token` placeholder. (prettier reflowed the
  file.)
- `sandbox_v2/plans/whats-changed.md` — ticked the `RefreshToken.scopes
  removed` breaking-change checkbox `[ ]` → `[x]` and appended the code-commit
  SHA `5141f96ebe1`.

## Test results

- `uv run pytest tests/auth/ tests/components/websocket_api/ tests/components/sandbox_v2/ --no-cov -q`
  → **467 passed** (2 snapshots), 7 warnings.
- `uv run pytest sandbox_v2/hass_client/ -q` → **50 passed**, 1 warning.
- `uv run prek run --files <14 changed files>` → all hooks Passed (prettier
  auto-formatted `architecture.html` once, then clean).

## Verification grep results (Step 7)

- `grep -rn "RefreshToken\.scopes\|token\.scopes\|self\.scopes\|scopes="
  homeassistant/auth/ .../websocket_api/connection.py .../sandbox_v2/`
  → **empty.**
- `grep -rn "SANDBOX_TOKEN_SCOPES\|_scope_allows" homeassistant/ tests/ sandbox_v2/hass_client/`
  (Python) → **empty.**
- `grep -rln "SANDBOX_TOKEN_SCOPES\|_scope_allows" .` → only markdown/HTML:
  the SUPERSEDED design doc, this batch's plan + FOLLOWUPS (past-tense /
  re-introduction references), historical `STATUS-phase-7/11/20.md`, and the
  forward-looking `design-share-states.md` / `plan-transport.md` (which point at
  the future re-introduction). The live `OVERVIEW.md` / `architecture.html` /
  `FOLLOWUPS.md` matches are all past-tense "was reverted" prose.

## Anything weird

- The first `git commit` only captured the already-staged `test_scopes.py`
  deletion because the `git add` line aborted on that removed pathspec; folded
  the remaining 13 files in via `git commit --amend` (commit not pushed, so the
  amend is safe). Final commit `5141f96ebe1` has all 14 files.
- `design-share-states.md` and `plan-transport.md` still reference
  `SANDBOX_TOKEN_SCOPES` as the place to extend when scoping returns. Left as-is
  — they are forward-looking design/plan docs outside this plan's Phase-C list,
  and FOLLOWUPS now points re-introduction at `auth-scoping-decision.md`.
- `architecture.html`'s "Core HA files modified" list does not include the
  `current_sandbox` contextvar row (pre-existing drift from plan-sandbox-context,
  not introduced here); only the auth row was removed per this plan's scope.
