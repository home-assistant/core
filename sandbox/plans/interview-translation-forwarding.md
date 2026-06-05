# Brainstorm — Sandbox translation forwarding

## Topic

Forward an integration's translations from the sandbox subprocess into the
main HA instance so the frontend renders translated strings for sandboxed
integrations — entity names, entity-state translations, config/options flow,
selectors, services, exceptions, issues, etc.

## Problem / Why

The sandbox runs an integration's code (setup, config flow, entities,
services) in an isolated subprocess while main keeps the unified frontend.
Translations in HA are loaded from each integration's on-disk
`translations/<lang>.json`, **keyed by integration domain**, and served to the
frontend via `frontend/get_translations`. For sandboxed integrations the
strings don't reach the frontend today:

- **Built-in** integrations: the translation files *do* exist on main's disk
  (same bundled `homeassistant` package), but the domain isn't in main's
  `hass.config.components` (it ran in the sandbox), so the entity/state
  category never loads for it. Files are present; loading is the gap.
- **Custom** (HACS) integrations: the code — and its `translations/` dir — is
  fetched into the *sandbox's* `<config>/custom_components/<domain>` per the
  integration-source design. The files **do not exist on main at all**.
  Strings genuinely have to cross the wire. Core's `title`→`integration.name`
  fallback (`translation.py:119-124`) also can't run on main (no `Integration`
  object for the custom domain).

## Grounding (code facts)

- `homeassistant/helpers/translation.py`
  - `_TranslationCache` is lazy and **per-language**; once a (language, domain)
    is loaded it's cached forever (translations are never unloaded).
  - `_async_load` → `async_get_integrations` (needs the `Integration` object)
    → `_async_get_component_strings` (reads `translations/<lang>.json` from the
    integration's dir). Both steps break for a custom domain absent on main.
  - `async_get_translations(..., category, integrations, config_flow)`:
    with `config_flow=True` and no integration list,
    `components = async_get_config_flows(hass) - hass.config.components`
    → a **bulk** set of every config-flow integration.
  - Categories are **not a fixed enum** — `build_resources` slices whatever
    top-level keys exist in the strings file (`config`, `options`, `selector`,
    `title`, `entity`, `state`, `services`, `exceptions`, `issues`, …).
  - `title` fallback: missing `title` ⇒ `component.<domain>.title =
    integration.name` (line 119-124). Unavailable for custom on main.
- Frontend (`../frontend`):
  - Add-integration **picker**: `dialog-add-integration.ts:606,640`
    → `loadBackendTranslation("title", discoveredHandlers, true)` — loads only
    the **`title`** category, in **bulk**, for all handlers; names also come
    from the static integrations index (`integration.name` /
    `domainToName`). No `config` category at picker time.
  - **Running** flow: `show-dialog-config-flow.ts:29-46`
    → loads `config` + `selector` + `title` for a **single** `handler`. By
    then that integration's sandbox is alive.
- Existing extensibility pattern to mirror: `sources.py`
  `async_register_sandbox_source_resolver` (HACS-agnostic resolver hook that
  maps a custom domain → git source). The `router` attribute on
  `ConfigEntries` and the `current_sandbox` ContextVar are the other
  precedents for a small declared core hook.

## Decisions so far

1. **Scope = both groups, unified path** (user). One conceptual mechanism for
   built-in and custom rather than per-group branching — subject to the picker
   carve-out below.
2. **Transport = pull / RPC on demand** (user). Main intercepts translation
   loading for a sandboxed *running* domain and issues a
   `sandbox/get_translations(domain, language)` RPC; the sandbox reads its
   local `translations/<lang>.json` and returns it. Matches the lazy
   per-language cache; only fetches what the frontend asks for; couples
   availability to the sandbox being alive (it is, when entities/flows are
   active).
3. **Picker is a separate, static seam** (user insight). The add-integration
   dialog only needs the **`title`** category and must work when no sandbox is
   running. So:
   - built-in → main reads `title` from its own disk (unchanged);
   - custom → the **source resolver / index** supplies the picker `title`
     (and any minimal picker strings), exactly like it already supplies the
     git install source. No sandbox spawn to render the picker.
   - Once the user *starts* a flow, the sandbox spawns and the full `config` /
     `selector` / `title` strings come over the live pull-RPC.

## Resulting shape (two seams)

- **Seam A — static picker strings (no live sandbox):** extend the
  integration-source resolver/index so a custom integration contributes its
  `title` (picker name + minimal strings) to main. Built-in stays disk-served.
- **Seam B — live pull-RPC (sandbox running):** a declared core hook in the
  translation loader routes a sandboxed domain's (language) strings request to
  the bridge → `sandbox/get_translations` → sandbox reads local file → returns
  the whole strings dict; main caches it in the existing `_TranslationCache`
  and `build_resources` slices by category as usual.

## Open questions / edges

- **RPC granularity:** return the *whole* strings dict for (domain, language)
  in one shot (simplest; main slices) vs per-category. Whole-dict matches how
  main reads the file today.
- **Domain → sandbox-group resolution on main** for a running domain: derive
  from `ConfigEntry.sandbox` / the bridge's registered-entity map. Pre-entry
  (flow in progress) the router already knows the group.
- **Cache invalidation on custom-integration update** (new sha → changed
  strings): core never invalidates translation cache; a sandbox restart with a
  new ref may need an explicit drop of cached (domain, *) strings.
- **Sandbox liveness for non-flow loads:** entity/state/exceptions strings for
  a loaded sandboxed entry — sandbox is running, fine. Guard the core hook to
  only redirect domains that are actually sandboxed-and-owned, so a
  not-running / main domain still reads disk.
- **`title` fallback** (`integration.name`) for custom on main — must come
  from Seam A, since main has no `Integration` object.
- **Custom-integration discovery on main** (whether a custom domain even
  appears in `async_get_config_flows` when its code lives only in the sandbox)
  is an adjacent unknown that Seam A's index likely also has to feed.

## Research findings (2 agents)

Full notes: `research/translation-forwarding-core-seam.md`,
`research/translation-forwarding-discovery-and-index.md`.

### Seam B — live pull-RPC (sandbox running) — well-supported

- **Silent-vanish today:** `async_get_integrations` returns `IntegrationNotFound`
  *as the dict value* (not raised, not cached — `loader.py:1441-1447`);
  `_async_load` skips Exception-valued domains (`translation.py:221-227`);
  `_async_get_component_strings` does `integrations.get(domain)` → a custom
  sandboxed domain silently yields `{}` and its frontend strings just disappear.
- **Recommended seam:** branch **inside `_async_load`**
  (`translation.py:208-253`) right after `async_get_integrations`, overlaying the
  RPC result onto `translation_by_language_strings` *before*
  `_build_category_cache` (which owns EN-fallback expansion + cache bookkeeping
  the sandboxed domain must share).
  - *Antithesis:* runs under the cache lock → a per-domain RPC serialises
    latency-sensitive frontend loads. Mitigate: **batch per group**, and
    **degrade to empty on a dead channel** (never block the picker/frontend).
- **RPC shape:** `{language: {domain: raw strings.json dict}}`, un-flattened,
  with `title` pre-filled **sandbox-side** (main can't run the
  `integration.name` fallback at `translation.py:118-124` for a custom domain).
- **Domain→group is already wired:** `ConfigEntry.sandbox`
  (`config_entries.py:432`) → `SandboxData.bridges[group]`
  (`sandbox/__init__.py:38-45`); pre-entry (flow in progress) the group comes
  from the active `SandboxFlowProxy` / `_assignment_for_new_flow`
  (`router.py:189-201`). No new index needed for the live path.
- **Cache invalidation:** there is **no eviction API** — `loaded`/`cache` only
  grow (`translation.py:168-171`). A custom integration re-fetched at a new
  commit sha (changed strings) needs a new `async_invalidate(components)` to
  drop stale `(domain, *)` entries. Minimal addition.

### Seam A — picker — bigger than translations

- **Reframe:** the picker does **not** use `async_get_config_flows`. It calls
  WS `integration/descriptions` → `async_get_integration_descriptions`
  (`loader.py:416-460`), built from the generated `integrations.json` (core) +
  `async_get_custom_components` — a **disk scan of `<config>/custom_components`**
  (`loader.py:325-343`). A custom integration whose code lives **only in the
  sandbox appears in none of these** (descriptions, config-flows, or index).
  *"Today the picker works by accident because HACS still drops code on disk;
  the stateless-sandbox future breaks it."* So the picker gap is
  **discoverability**, not just translation — the `title` strings are a subset
  of the catalog metadata main is missing.
- **Recommended shape:** a **separate** `async_register_sandbox_catalog_provider`
  hook (eager, enumerable, display-only) rather than overloading the
  security-critical, sha-pinned `IntegrationSourceDict` source resolver. Core
  merges the catalog into `async_get_integration_descriptions` + the `title`
  fallback; HACS fills it.
  - *Antithesis:* HACS reliably has the manifest `name` but may **not** have
    `translations/*.json` indexed (they live inside the un-fetched tarball) — so
    `title_translations` must be **optional**, degrading to `name` via the
    existing fallback. A wrong/missing name is cosmetic (unlike `ref`), so no
    strict validation needed.

## Converged approaches

**Approach 1 — Seam B first (live pull-RPC only).** Self-contained,
shippable. Covers entity names/state, running config/options flow, selectors,
services, exceptions, issues for any sandboxed integration whose sandbox is
alive. Built-in flows work (they run in the sandbox). Custom integrations work
*once their flow is running / entry is loaded*. Does **not** fix the
not-running picker for sandbox-only customs — but that's already broken for
*discoverability* independent of translations, so this doesn't regress
anything. Smallest core surface: one `_async_load` branch + a provider hook +
`async_invalidate`.

**Approach 2 — Both seams (B + catalog provider A).** Adds
`async_register_sandbox_catalog_provider` so stateless custom integrations are
discoverable *and* titled in the picker without a sandbox. Larger surface;
overlaps the broader "how do sandbox-only custom integrations appear on main"
question, which is arguably its own feature beyond translations.

**Open sub-decisions (either approach):**
- Built-in in Seam B: read main's local disk (skip the redundant RPC, one
  `is_built_in` branch) vs uniform pull. Research leans local-disk for built-in
  — main has byte-identical files.
- Cache invalidation now (`async_invalidate` on sha change) vs defer.
- RPC granularity: whole strings dict per (domain, language) — confirmed
  simplest, matches how main reads the file.

## Coverage

What 2/2 · Why 2/2 · Scope 2/2 · Where 2/2 · How 2/2 · Edge 2/2 (12/12)
