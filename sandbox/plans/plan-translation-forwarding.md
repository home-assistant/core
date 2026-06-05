# Plan — Sandbox translation forwarding (both seams)

> Source: `/phx:brainstorm` → `/phx:plan` (adapted to Python / Home Assistant
> core — not Elixir/Phoenix). Brainstorm + research are complete; this plan
> consumes them rather than re-deriving.
>
> Inputs: `interview-translation-forwarding.md`,
> `research/translation-forwarding-core-seam.md`,
> `research/translation-forwarding-discovery-and-index.md`.
> Scratchpad: `scratchpad-translation-forwarding.md`.
>
> **Locked decisions:** both seams in scope · pull/RPC transport · built-in
> reads local disk in the live path (RPC reserved for customs) · separate
> catalog-provider hook for the picker · whole-strings-dict RPC granularity.

## Problem

A sandboxed integration runs in an isolated subprocess; its
`translations/<lang>.json` is keyed by integration domain and served to the
frontend via `frontend/get_translations`. Today those strings don't reach the
frontend:

- **Custom** sandboxed integration → main has no `Integration` object;
  `async_get_integrations` returns `IntegrationNotFound` *as the dict value*
  (`loader.py:1441-1447`), `_async_load` skips Exception-valued domains
  (`translation.py:221-227`), so strings silently vanish (`{}`).
- **Picker** → the add-integration dialog is built from `integration/
  descriptions` (a disk scan of `<config>/custom_components`,
  `loader.py:325-343,416-460`); a sandbox-only custom appears in *none* of
  main's lists — a **discoverability** gap, of which `title` is a subset.

## Goal & success criteria

- [ ] Live: entity names/state, running config/options flow, selectors,
  services, exceptions, issues resolve for built-in *and* custom sandboxed
  integrations whose sandbox is alive.
- [ ] Picker: a sandbox-only custom integration is discoverable + named in the
  add-integration dialog with **no sandbox spawn**.
- [ ] No regression for non-sandboxed integrations (disk path unchanged).
- [ ] **Iron Law:** public declared hooks only — no monkey-patching private
  internals (the sandbox subsystem's standing rule).

---

## Phase B — live pull-RPC (ship first; self-contained)

### B1 · Wire protocol  `[protocol]`
- [ ] Add `sandbox/get_translations` to `proto/sandbox.proto`; regenerate
  `_proto/sandbox_pb2.py(i)` via `proto/generate.sh` (run
  `proto/check_drift.sh`).
- [ ] Mirror the constant in **both** `protocol.py` files
  (`homeassistant/components/sandbox/protocol.py` +
  `sandbox/hass_client/hass_client/protocol.py`).
- [ ] Shapes — request `{ language: str, domains: [str] }` (batched per group);
  response `{ language: str, strings: { domain: <raw strings.json dict> } }`,
  un-flattened, `title` pre-filled.

### B2 · Sandbox handler  `[hass_client]`
- [ ] Register a `sandbox/get_translations` handler in `SandboxRuntime`.
- [ ] For each domain, load raw strings for `language` from the sandbox's own
  filesystem — built-in from the bundled package, custom from the fetched
  `<config>/custom_components/<domain>` — reusing core's
  `_async_get_component_strings` / `component_translation_path` against the
  sandbox's private `hass`, or reading the file directly.
- [ ] **Pre-fill `title`**: if absent, inject `integration.name` (the sandbox
  *has* the `Integration`; `translation.py:118-124` can't run on main for
  customs).

### B3 · Core translation hook  `[core: homeassistant/helpers/translation.py]`
- [ ] Add `async_register_sandbox_translation_provider(hass, provider)`,
  mirroring the `sources.py` resolver convention (HassKey + unregister
  callback). `provider(language, components) -> {language: {domain: raw_strings}}`,
  returning only the domains it owns.
- [ ] In `_TranslationCache._async_load` (`:208-253`), **after**
  `async_get_integrations` and **before** `_build_category_cache`, call the
  provider and overlay its result onto `translation_by_language_strings`.
  Provider-claimed domains bypass the disk/`IntegrationNotFound` path;
  everything else unchanged.
- [ ] **Batch per group** + **degrade to empty on a dead channel** — the
  overlay runs under the cache lock; never block the frontend.
- [ ] Add `_TranslationCache.async_invalidate(components)` (+ module wrapper):
  discard from `loaded[*]` and `del cache[*][*][component]` (no eviction API
  exists today — `:168-171`).

### B4 · Provider impl + registration  `[sandbox: bridge.py / __init__.py]`
- [ ] Implement the provider: domain → group via `ConfigEntry.sandbox`
  (`config_entries.py:432`) for loaded entries, or the active
  `SandboxFlowProxy` / `_assignment_for_new_flow` (`router.py:189-201`) for a
  flow in progress; group → bridge via `SandboxData.bridges[group]`
  (`sandbox/__init__.py:38-45`); issue the batched RPC; `{}` for
  unowned/unreachable domains.
- [ ] **Built-in carve-out:** return nothing for `Integration.is_built_in`
  domains — main reads its byte-identical disk files. One branch.
- [ ] Register the provider in `async_setup`; unregister on unload.
- [ ] Call `async_invalidate({domain})` on entry reload / sandbox restart at a
  new integration-source `ref` (strings may have changed).

---

## Phase A — catalog provider (picker discoverability + title)

> The picker gap is discoverability, not just translation — `title` is a subset
> of the catalog metadata main lacks for a sandbox-only custom.

### A1 · Core hook  `[sandbox: sources.py (or sibling)]`
- [ ] Add a **separate** `async_register_sandbox_catalog_provider(hass,
  provider)` — display-only, enumerable; do **not** overload the sha-pinned,
  security-critical `IntegrationSourceDict` (`sources.py:38-56`). Entry shape:
  `{ domain, name, config_flow, integration_type, iot_class,
  single_config_entry, title_translations?: {lang: str} }`.
  `title_translations` **optional** (HACS may not index the un-fetched
  tarball's `translations/`); absent ⇒ degrade to `name`.

### A2 · Merge into descriptions  `[core: homeassistant/loader.py]`
- [ ] Append catalog entries to the custom half of
  `async_get_integration_descriptions` (`:416-460`) so the picker lists them.
- [ ] Use catalog `name` / `title_translations` in the `title` fallback chain
  when no on-disk `Integration` exists for a custom domain.

### A3 · HACS contract  `[docs]`
- [ ] Core exposes the hook; HACS fills it (HACS-agnostic posture, same as the
  source resolver). Wrong/missing name is cosmetic — no strict validation
  (unlike `ref`). Document in `sandbox/docs/`.

---

## Core surface touched (high review attention)

| File | Change | Phase |
|---|---|---|
| `homeassistant/helpers/translation.py` | provider hook + `_async_load` overlay + `async_invalidate` | B3 |
| `homeassistant/loader.py` | catalog merge into `async_get_integration_descriptions` + title fallback | A2 |
| `homeassistant/components/sandbox/protocol.py` + `sandbox/hass_client/.../protocol.py` + `proto/sandbox.proto` + `_proto/*pb2*` | `get_translations` message | B1 |
| `homeassistant/components/sandbox/{bridge,__init__,sources}.py` | translation + catalog provider impl & registration | B4, A1 |
| `sandbox/hass_client/.../` runtime | `get_translations` handler + title pre-fill | B2 |

## Verification

```bash
# core translation helper
uv run pytest tests/helpers/test_translation.py -q
# sandbox HA-core side
uv run pytest tests/components/sandbox/ --no-cov -q
# client side (separate uv env — no --no-cov)
uv run pytest sandbox/hass_client/ -q
# lint/format on changed files
uv run prek run --files <changed files>
```

- [ ] `tests/components/sandbox/`: assert a sandboxed integration's
  `frontend/get_translations` returns `config`/`entity`/`state`/`services`/
  `exceptions` strings — built-in *and* a fixture custom.
- [ ] `async_invalidate` drops stale strings after a simulated ref change.
- [ ] `hass_client`: `get_translations` returns title-prefilled raw dict for
  built-in + custom fixture.
- [ ] Catalog: a registered provider makes a sandbox-only custom appear in
  `async_get_integration_descriptions` + supplies the picker name.
- [ ] `test_translation.py`: provider overlay + degrade-to-empty on dead
  channel; non-sandboxed integrations unaffected.

## Risks & self-check

- **Cache lock × RPC latency.** The overlay runs under the cache lock;
  per-group batching + degrade-to-empty are load-bearing, not optional.
- **Pre-entry flow translations** for a brand-new custom (no entry, no code on
  main): group must come from the live `SandboxFlowProxy`, not `entry.sandbox`.
- **Invalidation correctness** on sha change — get the `loaded` + nested
  `cache` eviction keys right, or stale strings persist.
- **Scope creep on Phase A** — it bleeds into the broader "sandbox-only custom
  discovery" feature; keep the catalog strictly display metadata.

*Self-check:*
1. *What could make this wrong?* Translation loads that happen before the
   sandbox is up (boot-time) — guard the provider to claim only running/owned
   domains so they fall through to disk/empty, not block.
2. *Simplest thing that works?* Phase B alone is shippable and delivers the
   bulk of the UX; Phase A can land separately.
3. *What did research explicitly warn?* `IntegrationNotFound` is a dict
   *value* not a raise; there is *no* cache-eviction API; HACS may lack
   indexed translations — `title_translations` must be optional.

## Phasing

1. **Phase B** (B1→B4) — live pull-RPC. Self-contained, biggest win.
2. **Phase A** (A1→A3) — catalog provider; pairs with the broader
   stateless-custom-discovery work; can ship independently.

## Status

Not started. Next: `/phx:work sandbox/plans/plan-translation-forwarding.md`
(or implement Phase B directly).
