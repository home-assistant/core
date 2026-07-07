# Plan: rename `sandbox_v2` → `sandbox`

> **Execute LAST.** This is a high-churn mechanical rename touching ~112 files
> + 5 directories. Land it after every functional plan in the batch has
> shipped so it doesn't conflict with any in-flight diff.

## Why now

- v1 is gone (`plan-v1-removal.md`, 2026-05-28). The `_v2` suffix exists only
  to disambiguate from v1, which no longer exists in tree.
- Keeping `_v2` becomes load-bearing technical debt — every API string, file
  path, channel message name, user/client_id, integration domain, test path
  carries the suffix forever.
- Running this last avoids merge pain: every other plan in the batch touches
  files under `sandbox_v2/` or `components/sandbox_v2/`. Doing the rename
  before they land would force every PR to rebase against the renamed paths;
  after they land, the rename is a closed mechanical sweep.

## Scope

| Surface | From | To |
|---|---|---|
| HA component dir | `homeassistant/components/sandbox_v2/` | `homeassistant/components/sandbox/` |
| HA tests dir | `tests/components/sandbox_v2/` | `tests/components/sandbox/` |
| Top-level dir | `sandbox_v2/` | `sandbox/` |
| Client subpackage | `sandbox_v2/hass_client/hass_client/sandbox_v2/` | `sandbox_v2/hass_client/hass_client/sandbox/` |
| Tests storage dir | `tests/testing_config/.storage/sandbox_v2/` | `tests/testing_config/.storage/sandbox/` |
| Component domain | `sandbox_v2` | `sandbox` |
| Channel message prefix | `sandbox_v2/call_service`, `sandbox_v2/entry_setup`, … | `sandbox/call_service`, `sandbox/entry_setup`, … |
| Storage key namespace | `<config>/.storage/sandbox_v2/<group>/<key>` | `<config>/.storage/sandbox/<group>/<key>` |
| CLI module | `python -m hass_client.sandbox_v2` | `python -m hass_client.sandbox` |
| Sandbox user name | `"Sandbox v2: built-in"` (etc.) | `"Sandbox: built-in"` |
| Client ID prefix | `sandbox_v2/` | `sandbox/` |
| Logger names | `homeassistant.components.sandbox_v2.*`, `hass_client.*` (most already short-named) | match dir |
| Manifest domain | `manifest.json: "domain": "sandbox_v2"` | `"domain": "sandbox"` |
| Generated index | `homeassistant/generated/config_flows.py` — `"sandbox_v2"` entry | `"sandbox"` |
| Hassfest opt-out | `IGNORE_INTEGRATIONS_WITH_ERRORS = {"sandbox"}` (was for v1) | **delete** — v1 is gone; new `sandbox` (former v2) is hassfest-clean |
| `NO_QUALITY_SCALE` set | `sandbox_v2` entry | `sandbox` |
| Doc paths | All references in CLAUDE.md / OVERVIEW / FOLLOWUPS / STATUS-phase-*.md / architecture.html | match dir |
| Historical STATUS files | `sandbox_v2/STATUS-phase-N.md` | move under new dir; **keep mentions of `sandbox_v2` intact inside** — they're historical records |

## Important: what we DO NOT rename

- **Identifiers inside historical STATUS-phase-*.md files** stay as
  `sandbox_v2` — those documents describe phase-by-phase work performed
  against the `sandbox_v2` paths at the time. Rewriting them rewrites
  history. The files move to the new dir; the contents only get a one-line
  banner ("Note: paths renamed sandbox_v2 → sandbox on YYYY-MM-DD; original
  paths preserved below for historical accuracy").
- **Git history.** No history rewriting. `git mv` for each directory rename
  so blame survives.
- **The git branch name** (`sandbox`). Already named correctly; nothing to
  do.

## Phases

### Phase A — Directory + Python-module renames (git-mv only)

Five `git mv` operations, one commit each (or one commit covering all five
if reviewers prefer atomic):

1. `git mv homeassistant/components/sandbox_v2 homeassistant/components/sandbox`
2. `git mv tests/components/sandbox_v2 tests/components/sandbox`
3. `git mv sandbox_v2 sandbox`  *(top-level — moves planning docs, hass_client subtree, STATUS files, scripts; biggest churn but mechanical)*
4. `git mv sandbox/hass_client/hass_client/sandbox_v2 sandbox/hass_client/hass_client/sandbox`
5. `git mv tests/testing_config/.storage/sandbox_v2 tests/testing_config/.storage/sandbox`  *(if present and tracked)*

**Status:** after Phase A, the dirs are right but every `from
homeassistant.components.sandbox_v2 import …`, `import hass_client.sandbox_v2`,
every channel message string, every test path import, every domain string, etc.
is broken. Phase B is the sweep.

### Phase B — In-file identifier sweep

A single mechanical pass with three search-replace operations, run with
language-aware tooling to avoid mangling unrelated strings (`sandbox_v2` is
distinctive enough that it should be safe, but verify hits before applying).

Replacements, in order (later ones depend on earlier ones being done):

1. **`sandbox_v2` → `sandbox`** as a bare word everywhere except:
   - Inside `STATUS-phase-*.md` files (historical — see "what we don't
     rename")
   - Inside `plans/interview.md` (also historical — pre-build brainstorm)
   - Inside `docs/auth-scoping-decision.md` (will already be SUPERSEDED'd
     by `plan-strip-auth-scopes.md` — historical record)
   - Inside this plan file (it describes the *transition*)
2. **`Sandbox v2:` → `Sandbox:`** (user/group name prefix).
3. **`Sandbox v2` → `Sandbox`** in user-visible prose (READMEs, OVERVIEW.md
   intro, comment headers). Pure prose — should be ~10 hits.

Implementation: use `rg --files-with-matches sandbox_v2 | xargs sed -i …`
but with an exclude list for the historical files above. Per-file review
diff before committing (rg-then-sed can mangle if there are unexpected
contexts).

### Phase C — Hassfest cleanup

- `script/hassfest/__main__.py` — `IGNORE_INTEGRATIONS_WITH_ERRORS` was added
  in Phase 17 to bypass v1's broken state. v1 is gone; v2 (now renamed to
  `sandbox`) is hassfest-clean. **Delete the entire `IGNORE_INTEGRATIONS_WITH_ERRORS`
  set + the conditional that consults it.** Verify the new `sandbox` passes
  hassfest naturally.
- `script/hassfest/quality_scale.py` — `NO_QUALITY_SCALE` entry: rename
  `sandbox_v2` → `sandbox`.
- `homeassistant/generated/config_flows.py` — regenerate (or hand-edit) so
  the `sandbox` entry replaces `sandbox_v2`.

### Phase D — Verification + docs

- **Greps that must come back empty after the sweep** (run from repo root,
  excluding the historical files listed above):
  ```bash
  rg sandbox_v2 \
    --glob '!sandbox/STATUS-phase-*.md' \
    --glob '!sandbox/plans/interview.md' \
    --glob '!sandbox/docs/auth-scoping-decision.md' \
    --glob '!sandbox/plans/plan-rename-sandbox.md'
  # → empty
  rg '"Sandbox v2"' --glob '!sandbox/STATUS-phase-*.md'
  # → empty
  ```
- Tests:
  ```bash
  uv run pytest tests/components/sandbox/ --no-cov -q
  uv run pytest /home/paulus/dev/hass/core/sandbox/hass_client/ -q
  ```
- `uv run prek run --all-files` clean.
- Compat lane (`cd sandbox && python run_compat.py`) shouldn't regress vs.
  the last known-good run; if it does, the rename touched something
  unexpected.

### Phase E — Doc reconciliation pass

Same shape as the closing phase of every other plan in this batch:
- `CLAUDE.md`, `OVERVIEW.md`, `FOLLOWUPS.md`, `README.md`, `hass_client/README.md`,
  `BACKLOG.md`, `COMPAT.md`, `COMPAT_FULL.md`, `architecture.html` — refresh.
- `sandbox/plans/whats-changed.md` — add a final bullet under "Not in this
  batch" (or "TL;DR") confirming the rename.
- Repo-root `CLAUDE.md` (project-level) — grep for `sandbox_v2`, update any
  hits.

## Touch points

```
homeassistant/components/sandbox_v2/                      → homeassistant/components/sandbox/
tests/components/sandbox_v2/                              → tests/components/sandbox/
sandbox_v2/                                                → sandbox/
sandbox_v2/hass_client/hass_client/sandbox_v2/            → sandbox/hass_client/hass_client/sandbox/
tests/testing_config/.storage/sandbox_v2/                 → tests/testing_config/.storage/sandbox/
script/hassfest/__main__.py                               (delete IGNORE_INTEGRATIONS_WITH_ERRORS)
script/hassfest/quality_scale.py                          (rename in NO_QUALITY_SCALE)
homeassistant/generated/config_flows.py                   (regenerate)
~112 files containing `sandbox_v2` literal                (sed sweep, with exclude list)
```

## Sequencing

- **Executes LAST in the plan batch.** After: contextvar (A1+A2),
  strip-auth-scopes, fidelity-batch (#2/#4/#5/#6/#7), ALWAYS_MAIN lockdown,
  transport, ephemeral-sources, docker.
- **Hard dependency: every other plan must have landed.** Any in-flight
  branch against `sandbox_v2/` will conflict; rebase windows are painful for
  this size of sweep.
- Single big PR is acceptable here because the rename is mechanical and
  reviewers can run the verification greps from Phase D to gain confidence
  in seconds.

## Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | **An unrelated string `sandbox_v2` somewhere we missed gets renamed and breaks.** | Low | Medium | rg the codebase before the sed sweep; review each file's hits. The string is distinctive — unlikely to appear in test data or third-party deps. |
| 2 | **Storage-key migration.** Existing dev HA instances persist data under `<config>/.storage/sandbox_v2/<group>/<key>`. After rename, the manager reads `<config>/.storage/sandbox/<group>/<key>` — old data is orphaned. | Medium (dev instances) | Low (data is sandbox-side, regeneratable) | Document in PR: "wipe `<config>/.storage/sandbox_v2/` after upgrading; no production users yet since v2 isn't released". Optionally, ship a one-shot `sandbox` startup migration that `os.renames` the old dir to the new name on first launch — but the user explicitly preferred wipe-and-restart simplicity ([[plan-ephemeral-sources]]), so a migration is over-engineering. |
| 3 | **Logger names change → existing log filters break.** | Trivial | Trivial | v2 isn't released; no log-filter consumers exist. Note in PR description. |
| 4 | **Pre-existing refresh tokens in dev auth stores have client_id `sandbox_v2/<group>` and user-name `Sandbox v2: <group>`.** New code looks for the renamed prefixes; old tokens orphan. | Medium (dev) | Low (auth helper recreates on miss) | The `_get_or_create_sandbox_*` helpers create-if-missing; orphaned old users/tokens linger harmlessly. Optional: a one-shot cleanup migration that deletes any `Sandbox v2:` system user. Defer unless reviewer asks. |
| 5 | **A PR in-flight against the v2 paths during the rename window.** | Medium | High (merge conflict hell) | Coordination: the rename PR is the LAST in the batch by design. Confirm no in-flight branches against `sandbox_v2/` before opening it. |

## Verification checklist

- [ ] Five `git mv`s applied (Phase A).
- [ ] `rg sandbox_v2 -g '!{<historical files>}'` returns empty.
- [ ] Hassfest passes naturally without `IGNORE_INTEGRATIONS_WITH_ERRORS`
      (the set is gone).
- [ ] `tests/components/sandbox/` test suite green.
- [ ] `sandbox/hass_client/` test suite green.
- [ ] `uv run prek run --all-files` clean.
- [ ] Compat lane parity vs last known-good run.
- [ ] `homeassistant/generated/config_flows.py` lists `sandbox`, not
      `sandbox_v2`.
- [ ] `git log --diff-filter=R --name-status` shows the five rename
      operations (`R100` lines).

## Final phase — docs up to date

Cross-cutting docs phase identical to every other plan in the batch:
refresh current-state docs (CLAUDE.md / OVERVIEW.md / FOLLOWUPS.md /
README.md / architecture.html / repo-root CLAUDE.md); leave the historical
STATUS-phase-*.md files alone except for the one-line banner noting the
rename.

This is the plan that finally closes out the `v2` chapter — the directory,
the integration domain, and every API string match the post-v1 reality.
