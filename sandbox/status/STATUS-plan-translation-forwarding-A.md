# STATUS — plan-translation-forwarding (Phase A: catalog provider)

**Done.** Phase A (A1→A3) shipped — a custom integration whose code lives only
in a sandbox (never on main's `<config>/custom_components` disk) is now
**discoverable + named in the add-integration picker with no sandbox spawn**, via
a new display-only catalog hook that HACS fills. Core exposes the hook; HACS
fills it (same HACS-agnostic posture as the source resolver). The hook is
deliberately **separate** from the sha-pinned, security-critical integration-
source resolver. **Phase B (live pull-RPC) was untouched** — Phase A builds
alongside it. All three suites green, prek clean on every changed file. Not
pushed (orchestrator pushes); no `--no-verify`; pre-commit passed on every
commit.

## Commits

| SHA | What |
|---|---|
| `07dcf64357b` | A1 — catalog-provider hook (`async_register_sandbox_catalog_provider` + `SandboxIntegrationDescriptor` + `async_get_sandbox_catalog`) in core `loader.py`; re-export module in the sandbox component |
| `e95fd93e219` | A2 — merge catalog into `async_get_integration_descriptions` + `title` fallback in `helpers/translation.py` + tests |
| `2085b5348d4` | A3 — `sandbox/docs/catalog-provider-contract.md` (the HACS contract) |

Three commits, one per task, each leaving the tree green.

## What each task delivered

### A1 — catalog-provider hook

The hook is genuinely **core-consumed** (unlike the source resolver, which only
the sandbox router reads). `loader.async_get_integration_descriptions` and
`helpers/translation._async_get_component_strings` both need the catalog, and
neither can import the sandbox component (core → component is a layering
violation). So the **registry lives in core**, exactly mirroring the Phase B
translation-provider precedent (hook + consumer co-located in core
`helpers/translation.py`).

- `homeassistant/loader.py`:
  - `SandboxIntegrationDescriptor(TypedDict, total=False)` — `{domain, name,
    config_flow, integration_type, iot_class, single_config_entry,
    title_translations?}`. `domain`/`name` load-bearing; `title_translations`
    (`{lang: title}`) optional.
  - `SandboxCatalogProvider = Callable[[], list[SandboxIntegrationDescriptor]]`
    — eager, enumerable, sync (HACS holds this in memory; no I/O).
  - `DATA_SANDBOX_CATALOG_PROVIDERS` HassKey + `@callback`
    `async_register_sandbox_catalog_provider(hass, provider) -> unregister`
    (registration order; first to claim a domain wins) +
    `async_get_sandbox_catalog(hass) -> {domain: descriptor}` accessor (returns
    `{}` when no provider registered — the no-sandbox common case, negligible
    cost on the hot translation path).
- `homeassistant/components/sandbox/catalog.py` (NEW) — thin re-export of the
  core hook + types, giving HACS a single sandbox-namespaced registration
  surface parallel to `sandbox/sources.py`, while the registry stays in core.

### A2 — descriptions merge + title fallback

- `loader.async_get_integration_descriptions`: after the on-disk custom scan,
  append `async_get_sandbox_catalog(hass)` descriptors to the custom
  `integration` / `helper` buckets (routed by `integration_type`), defaulting
  the picker-metadata fields. **On-disk customs win a domain collision** (they
  carry richer metadata) — catalog entries are skipped for any domain the disk
  scan already produced.
- `helpers/translation._async_get_component_strings`: the existing `title`
  fallback injects `integration.name` only when an `Integration` is present. A
  sandbox-only custom is `IntegrationNotFound` on main (filtered out of the
  `integrations` dict by `_async_load`, but still present in `components`), so it
  reached the loop with no title. Added an `elif`: take the catalog descriptor's
  `title_translations[language]` if present, else degrade to `name` (else
  `domain`). Catalog is fetched once before the per-language loop.
- Tests:
  - `tests/test_loader.py` —
    `test_get_integration_descriptions_includes_sandbox_catalog` (parametrized:
    full integration descriptor + minimal helper-with-defaults → correct bucket,
    name, metadata) and `test_sandbox_catalog_does_not_override_on_disk_custom`
    (collision: on-disk name wins).
  - `tests/helpers/test_translation.py` —
    `test_get_translations_title_from_sandbox_catalog` (parametrized:
    `title_translations[en]` used when present; degrades to `name` when absent),
    both with the domain `IntegrationNotFound` on main.

### A3 — HACS contract docs

`sandbox/docs/catalog-provider-contract.md`: the discoverability gap, the
`async_register_sandbox_catalog_provider` API + example, and the contract —
separate from the security-critical source resolver, `name` load-bearing,
`title_translations` optional, no validation (a wrong name is cosmetic),
display-only scope (explicitly **not** the broader stateless-custom-discovery
feature), and how it complements the Phase B live RPC for the cold picker case.

## Verification (run on the final committed tree)

```
$ uv run pytest tests/test_loader.py -q
88 passed, 2 warnings in 1.08s

$ uv run pytest tests/helpers/test_translation.py -q
25 passed, 2 warnings in 0.42s

$ uv run pytest tests/components/sandbox/ --no-cov -q
201 passed, 2 warnings in 7.89s

$ .venv/bin/prek run --files <all 6 changed files>
ruff check / ruff format / codespell / prettier / mypy / pylint ......... Passed
```

New tests added (per the plan's Verification section for Phase A):
- a registered catalog provider makes a sandbox-only custom appear in
  `async_get_integration_descriptions` and supplies the picker name ✅
- title fallback uses catalog `name` / `title_translations` when no on-disk
  `Integration` exists ✅
- absent `title_translations` degrades to `name` ✅

## Deviations / decisions (flagged for review)

1. **Hook registry lives in core `loader.py`, not in the sandbox component.**
   The plan's A1 row tagged it `[sandbox: sources.py (or sibling)]`, but core
   (`loader.py` + `helpers/translation.py`) is the **consumer**, and core cannot
   import a component. The only layering-correct home for a core-consumed
   registry is core — and this exactly mirrors the Phase B precedent
   (`async_register_sandbox_translation_provider` lives in core
   `helpers/translation.py`). The sandbox component still owns the **HACS-facing
   API** via the `catalog.py` re-export, satisfying "separate hook in the sandbox
   namespace" without the impossible import.

2. **Catalog provider is sync** (`Callable[[], list[...]]`), matching the
   research's shape and the sync source-resolver convention — HACS holds the
   catalog in memory, so no `await` is needed and `_async_get_component_strings`
   (a hot path) stays cheap.

3. **On-disk wins a domain collision.** Today's HACS still drops code on disk, so
   a domain can be both on-disk and in the catalog; the richer on-disk metadata
   takes precedence. Minimal: catalog entries do **not** touch `core_flows`
   (a sandbox-only custom is, by definition, a domain main doesn't otherwise
   know), keeping the change surgical.

4. **No `__init__.async_setup` registration on the sandbox side.** Unlike the
   Phase B translation provider (which the sandbox component *implements* and
   registers), the catalog is *filled by HACS*, exactly like the source
   resolver — so the sandbox integration only exposes the hook; HACS calls it.
   `homeassistant/components/sandbox/__init__.py` is unchanged.

## HACS contract exposed

`from homeassistant.components.sandbox.catalog import
async_register_sandbox_catalog_provider` — register a
`Callable[[], list[SandboxIntegrationDescriptor]]`; returns an unregister
callback. Descriptor: `{domain, name, config_flow, integration_type, iot_class,
single_config_entry, title_translations?}`. `name` load-bearing,
`title_translations` optional (degrades to `name`), no validation (display-only,
not sha-pinned). See `sandbox/docs/catalog-provider-contract.md`.

## Tooling note

`uv run prek …` fails to spawn in this environment (`prek` not on uv's resolved
PATH); `.venv/bin/prek run --files …` is equivalent and was used for every
commit, as in Phase B.

## Scope held

Phase A is **strictly display metadata** — it was deliberately kept from bleeding
into the broader "sandbox-only custom discovery" feature (config-flow
allow-listing, schema forwarding, etc.), per the plan's called-out scope-creep
risk. Phase B was not touched.
