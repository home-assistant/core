# STATUS — plan-rename-sandbox

**Summary:** `sandbox_v2` → `sandbox` renamed across the whole tree (directories,
integration domain, channel wire strings, storage-key namespace, CLI module,
protobuf, client_id / system-user-name prefixes, docs). Both test suites green
at unchanged counts (HA-side 201, client 70); proto drift guard clean; hassfest
clean without the v1 ignore set. This closes the `v2` chapter.

## Commits (oldest → newest, not pushed — parent pushes)

| SHA | Phase | Subject |
|-----|-------|---------|
| `107cb8b38e8` | A | rename directories sandbox_v2 → sandbox (git mv) |
| `cd024666128` | B | sweep identifiers sandbox_v2 → sandbox + regen protobuf |
| `5bab9f867bf` | C | drop hassfest IGNORE_INTEGRATIONS_WITH_ERRORS |
| `9cd52e950e4` | E | docs reconciliation for the rename |

Each commit leaves the tree in a known state. Phase A alone does **not** import
or pass tests (expected — Phase B fixes every identifier). Phase B onward is
green.

## Phase A — the directory renames (git mv)

5 planned; **4 applied as `git mv`, 1 skipped**:

1. ✅ `homeassistant/components/sandbox_v2` → `homeassistant/components/sandbox`
2. ✅ `tests/components/sandbox_v2` → `tests/components/sandbox`
3. ✅ `sandbox_v2` → `sandbox`
4. ✅ `sandbox/hass_client/hass_client/sandbox_v2` → `…/sandbox`
   *(the launcher subpackage — see the collision note below)*
5. ⏭️ `tests/testing_config/.storage/sandbox_v2` — **skipped, not tracked**
   (a runtime test artifact; `git ls-files` returns nothing for it). Left on
   disk; orphaned (the renamed code writes to `.storage/sandbox/`).

Plus a 6th file rename folded into Phase A: `sandbox/proto/sandbox_v2.proto`
→ `sandbox/proto/sandbox.proto` (`git mv`).

`git log --diff-filter=R --name-status 107cb8b38e8` shows **189 `R` rename
entries** — blame preserved. (Empty `__init__.py` files and `strings.json`
show as add+delete pairs rather than `R` because git can't content-match
0-byte / small files across a rename; their `sandbox_v2/…` counterparts are
deleted in the same commit — they are real renames, not new files.)

## Phase B — identifier sweep

- Bare-token `sandbox_v2` → `sandbox` over 103 files (code + current-state
  docs), excluding historical `STATUS-*.md`, `plans/*.md`,
  `docs/auth-scoping-decision.md`, and the generated `_pb2` gencode.
- Prose `Sandbox v2` → `Sandbox` (single pass also fixes `Sandbox v2: ` →
  `Sandbox: ` system-user-name prefix). `auth.py` now:
  `_USER_NAME_PREFIX = "Sandbox: "`, `_CLIENT_ID_PREFIX = "sandbox/"`.
- Non-obvious targets all swept: channel message strings (`sandbox/call_service`,
  `sandbox/entry_setup`, `sandbox/ready`, `sandbox/state_changed`, …) on both
  sides + the proto; storage-key namespace
  (`<config>/.storage/sandbox/<group>/<key>` — `bridge.py`); manifest domain
  (`"sandbox"`); `requirements_all.txt` section comment.

### Full proto rename — DONE (not the fallback)

- Renamed `sandbox_v2.proto` → `sandbox.proto`; internal `package sandbox_v2;`
  → `package sandbox;` + comment paths swept.
- **Regenerated** the gencode via `sandbox/proto/generate.sh` (isolated venv,
  protobuf 6.32.0 + grpcio-tools): module `sandbox_v2_pb2` → `sandbox_pb2` in
  **both** mirrors; old `sandbox_v2_pb2.py(+.pyi)` `git rm`'d. New descriptor:
  `name=sandbox.proto`, `package=sandbox`, 42 messages.
- All import sites updated by the bare sweep (`sandbox_v2_pb2` → `sandbox_pb2`).
- `generate.sh` + `check_drift.sh` + `.pre-commit-config.yaml` paths/filename
  swept.
- **Drift guard passes:** `sandbox proto drift guard: gencode matches
  sandbox.proto.`
- `rg sandbox_v2_pb2` → only 3 historical files (`plans/plan-transport.md`,
  `STATUS-plan-transport.md`, `STATUS-plan-transport-T2.md`), deliberately
  preserved.

### Name-collision fix (forced by the rename — judgment call, documented)

The client had **two** things that both want the name `sandbox` after the
rename:
- `hass_client/sandbox.py` — the impl module (exports `SandboxRuntime`,
  `_open_unix_channel`, `_transport_scheme`).
- `hass_client/sandbox_v2/` — a `-m` launcher subpackage (`__init__.py` +
  `__main__.py`) that does `from hass_client.sandbox import SandboxRuntime`.

Renaming the launcher subpackage to `sandbox` (Phase A mv #4) collides with the
impl module. The plan/brief assumed `python -m hass_client.sandbox` would just
work; it can't while a sibling `sandbox.py` exists. **Resolution: merged them.**
`sandbox.py` is now `hass_client/sandbox/__init__.py`; the launcher's
`__main__.py` stays. So:
- `python -m hass_client.sandbox` runs `sandbox/__main__.py` ✅
- `from hass_client.sandbox import SandboxRuntime` resolves to the package
  `__init__.py` ✅

The merged `__init__.py`'s parent-relative imports (`from ._proto …` → would be
`hass_client.sandbox._proto`) were rewritten to **absolute** `from hass_client.…`
(ruff `TID252` bans parent-relative imports in this repo).

### Docker / pyproject

- `docker-entrypoint.sh`, `docker-compose.test.yml`, `docs/docker.md`,
  `Dockerfile` → `python -m hass_client.sandbox` (the bare sweep handled the
  module path; the entrypoint comment "do not rename it here" is now
  consistent).
- Client **distribution** name `hass-client-v2` → `hass-client` in
  `pyproject.toml` (the import package `hass_client` is unchanged; this matches
  the already-installed `hass_client.egg-info` whose `PKG-INFO` Name is
  `hass-client`). Description reworded to drop the dangling "v2".

## Phase C — hassfest

- ✅ `IGNORE_INTEGRATIONS_WITH_ERRORS` set **deleted** from
  `script/hassfest/__main__.py` (plus the two list-comprehension conditionals
  that consulted it). It existed to mask v1's broken state; v1 is gone.
- ✅ Renamed integration passes hassfest **naturally**:
  `python -m script.hassfest --action validate` → **0 invalid integrations**;
  `--action generate` → **0 invalid, no generated-file changes**.
- `homeassistant/generated/config_flows.py`: **no change needed** — `sandbox`
  has no `config_flow` in its manifest, so it was never listed there (it was not
  in the `sandbox_v2` grep set either).
- `NO_QUALITY_SCALE` entry (`script/hassfest/quality_scale.py`): `sandbox_v2` →
  `sandbox`, correctly sorted (renamed by the Phase B sweep).

## Phase D — verification

```
rg sandbox_v2 -g '!sandbox/STATUS-*.md' -g '!sandbox/plans/*.md' \
   -g '!sandbox/docs/auth-scoping-decision.md'        → EMPTY ✓
rg '"Sandbox v2"' -g '!sandbox/STATUS-*.md' -g '!sandbox/plans/*.md'  → EMPTY ✓
rg sandbox_v2_pb2                                     → only 3 historical files ✓
```

Tests (same counts as before the rename):
- HA-side: `pytest tests/components/sandbox/ --no-cov -q` → **201 passed**
- Client: `pytest sandbox/hass_client/ -q` → **70 passed**
- `tests/auth/test_auth_store.py` (swept the `Sandbox v2: built-in` literal) →
  **11 passed**
- Drift guard → clean.

`prek`:
- **`prek run --files <all 196 changed files>` → fully clean** (ruff, ruff
  format, codespell, prettier, mypy, pylint, hassfest, gen_requirements all
  Pass). This covers 100% of the files the rename touched.
- **`prek run --all-files` fails on ONE pre-existing, rename-unrelated mypy
  artifact:** `homeassistant/util/hass_dict.py` + `.pyi` →
  `error: Duplicate module named "homeassistant.util.hass_dict"`. Both files
  existed at the batch base (`4e982e34cad`) and are **unchanged** by the rename;
  this duplicate-module error only surfaces when mypy is fed every `.py`+`.pyi`
  pair at once (i.e. `--all-files` mode), and aborts mypy before the later
  hooks run. Not introduced here. The scoped run above is the authoritative
  clean result.

## Things worth flagging

- **Storage-key orphaning (expected, pre-release).** Old dev instances persist
  data under `<config>/.storage/sandbox_v2/<group>/<key>` and auth users named
  `Sandbox v2: <group>` with client_id `sandbox_v2/<group>`. The renamed code
  reads/writes the `sandbox` namespace; old data orphans harmlessly. No
  migration (per [[plan-ephemeral-sources]] wipe-and-restart preference). Wipe
  `.storage/sandbox_v2/` after upgrading.
- **Untracked `.storage/sandbox_v2/` dir** left on disk (test artifact); the
  matching `git mv` was skipped because it isn't tracked.
- **Env fixups (not committed, local venvs only):** the client venv was
  pre-staged at the rename-target path `sandbox/hass_client/.venv` (editable
  install already pointing at `sandbox/hass_client/hass_client`); I (a) restored
  it into the renamed dir, (b) re-pointed the **main** `.venv`'s `hass_client`
  editable finder from the old `sandbox_v2/…` path to `sandbox/…`, and (c)
  installed the declared `protobuf==6.32.0` into the client venv (it was
  missing). `uv.lock` for the client was untracked and is gone; client tests
  were run via the venv python directly (`.venv/bin/python -m pytest`) rather
  than `uv run` to avoid a network re-sync.
- **`plan.md` (top-level) was swept** to `sandbox`. It is NOT in the protected
  set (only `plans/plan-*.md` are), and the Phase D grep requires it clean.
  Historical `STATUS-*.md`, `plans/*.md` (incl. `interview.md`, the plan files,
  `whats-changed.md`) and `docs/auth-scoping-decision.md` keep their
  `sandbox_v2` mentions intact.
- **`OVERVIEW.md` / `Dockerfile`** references to `hass_client/sandbox.py` were
  updated to `hass_client/sandbox/__init__.py` (the file moved in the
  collision-merge); one ASCII box-diagram line in OVERVIEW.md was re-padded to
  keep its border aligned.
