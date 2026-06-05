# Sandbox translation forwarding — discovery & index research

Goal: figure out how the *add-integration picker* can show a `title` (display
name) for a **custom/HACS integration whose code lives only in a sandbox**, and
how the not-yet-running config-flow entry can be rendered — **without spawning a
sandbox**. Two seams:

- **Seam A (cold/picker path):** picker list + `title` strings, no flow running,
  no entry loaded, possibly no code on main's disk.
- **Seam B (live pull path):** a flow *is* running or an entry *is* loaded —
  main already knows the sandbox group for the domain.

All `file:line` references are against repo root `/home/paulus/dev/hass/core`
(backend) and `/home/paulus/dev/hass/frontend` (frontend, read-only).

---

## 1. Where the picker's integration list comes from

**The picker does NOT call `async_get_config_flows`.** That function
(`homeassistant/loader.py:346-367`) is the *flow allow-list* (used by config-flow
init to decide whether a domain may start a flow). The picker UI is fed by a
different function.

### The picker's actual source: `integration/descriptions`

- Frontend: `dialog-add-integration.ts:590-644` `_load()` calls
  `getIntegrationDescriptions(this.hass)`
  (`frontend/src/data/integrations.ts:42-47`), which is the WS command
  `integration/descriptions`.
- Backend handler: `homeassistant/components/websocket_api/commands.py:1303-1309`
  `handle_integration_descriptions` → `async_get_integration_descriptions`.
- Builder: `homeassistant/loader.py:416-460`
  `async_get_integration_descriptions`:
  - **core** half: read verbatim from the generated
    `homeassistant/generated/integrations.json`
    (`loader.py:420-424`). This is a build-time artifact (brands index +
    per-integration metadata + a `translated_name` list). Never includes
    sandbox-only customs.
  - **custom** half: built live from `async_get_custom_components(hass)`
    (`loader.py:425-458`). That function (`loader.py:325-343` →
    `_get_custom_components`) **scans `<config>/custom_components` on main's
    disk**. Each custom integration contributes a metadata dict:
    `config_flow`, `integration_type`, `iot_class`, `name`,
    `single_config_entry`, `overwrites_built_in` (`loader.py:448-458`).

### Consequence for a sandbox-only custom integration

A custom integration whose code lives **only in the sandbox** (fetched on
`entry_setup` per `sandbox/sources.py`; not present under main's
`<config>/custom_components`) is invisible to **both** lists:

- It is **not** in `async_get_config_flows` — the custom branch
  (`loader.py:360-365`) iterates `async_get_custom_components(...).values()`,
  which only sees on-disk customs.
- It is **not** in `async_get_integration_descriptions` `custom.integration` —
  same on-disk scan (`loader.py:425-431`).
- It is **not** in the generated `integrations.json` (that ships only built-ins).

So **with stateless sandboxes the picker simply has no row for the integration**,
and `frontend/get_translations` has nothing to load a title from. This is the
core gap the feature must close.

> Note on the today-state: the stateless-sandbox source model
> (`sandbox/CLAUDE.md` "Stateless sandboxes — integration source") presumes the
> code is fetched at setup time. But the *current* HACS install still drops the
> code under `<config>/custom_components`, so today the picker works by accident
> (the on-disk scan finds it). The research target is the future where the code
> is NOT on main's disk — then the picker breaks unless we feed it from the
> resolver/index.

---

## 2. The `title` strings for the picker

Two-layer title resolution, both rooted on main's disk:

1. **Display name in the list** — `dialog-add-integration.ts:266 / 282 / 299 /
   324` use `integration.name || domainToName(localize, domain)`. `name` is the
   manifest name carried in the descriptions payload (`loader.py:452`,
   `"name": integration.name`). For a sandbox-only custom there is **no manifest
   on disk → no `name`**, and `domainToName` only falls back to a prettified
   domain string. So the row, if it existed at all, would show e.g.
   `My Custom Thing` only if `integration.name` were supplied.

2. **`title` translation category** — loaded lazily via
   `dialog-add-integration.ts:639-643`
   `loadBackendTranslation("title", descriptions.core.translated_name, true)`
   (and `:606` for in-progress discovered handlers). Backend:
   `frontend/get_translations` (`frontend/__init__.py:987-1009`) →
   `async_get_translations` → `_async_get_component_strings`
   (`translation.py:86-127`). Title strings come from:
   - the integration's on-disk `translations/<lang>.json`
     (`translation.py:100-106`, `integration.file_path / "translations" /
     <lang>.json`), **OR**
   - fallback to `integration.name` (manifest name) when the `title` key is
     missing (`translation.py:118-124`):
     ```python
     if "title" not in component_translations and (
         integration := integrations.get(domain)
     ):
         component_translations["title"] = integration.name
     ```
     But `integrations.get(domain)` is the loaded `Integration` object — for a
     sandbox-only custom, `async_get_integrations` cannot load it (no code on
     disk), so even the fallback has nothing.

**Confirmed gap:**

| Integration kind | manifest `name` on main | `translations/*.json` on main |
|---|---|---|
| built-in, sandboxed | ✅ bundled | ✅ bundled |
| custom, code on disk (today's HACS) | ✅ | ✅ (HACS ships them) |
| **custom, sandbox-only (target)** | ❌ | ❌ |

**Minimal data the picker actually needs** (the whole reason we don't need a
sandbox): per custom domain, a tiny static descriptor —
- `name` (display name; what feeds both the list label *and* the `title`
  translation fallback),
- the picker metadata it already wants: `config_flow: true`, `integration_type`
  (so it lands in the right bucket — `integration` vs `helper`), `iot_class`
  (cloud badge), optionally `single_config_entry`.

That is exactly the subset `async_get_integration_descriptions` writes today
(`loader.py:448-458`). No `config`/`selector` schema, no description body — just
enough to render a row and a name. (See §5: the picker never loads `config`.)

---

## 3. Extending the resolver / index to carry the picker `title`

### What exists

`async_register_sandbox_source_resolver(hass, resolver)`
(`sandbox/sources.py:67-87`). A resolver is `Callable[[str], IntegrationSourceDict
| None]` (`sources.py:56`) — domain in, git source out. `IntegrationSourceDict`
(`sources.py:38-51`) is purely *code-location* data: `kind, url, ref, tag,
domain, subdir`. There is **no name/title/metadata** anywhere in the contract.
Resolvers are consulted **lazily, per-domain, only at `entry_setup`** via
`async_resolve_integration_source` (`sources.py:90-114`) — i.e. only once you
already know the domain you want. That shape is wrong for the picker, which needs
to *enumerate* unknown domains up front.

### The contract decomposition: core EXPOSES, HACS FILLS

Mirror the existing resolver philosophy (core HACS-agnostic; HACS registers).
Two cleanly-separable concerns:

- **Code location** (existing): `domain → {kind:git,url,ref,...}`, lazy,
  per-domain, security-critical (`ref` must be a sha). Keep as-is.
- **Picker metadata** (new): the full *set* of custom domains plus their
  display metadata, eager, enumerable, NOT security-critical (it's just a
  display string). This wants a **listing** hook, not a per-domain resolver.

**Cleanest shape — a parallel "catalog provider" hook**, registered the same way:

```python
class SandboxIntegrationDescriptor(TypedDict, total=False):
    domain: str
    name: str                 # display name → list label + title fallback
    integration_type: str     # "integration" | "helper" | ...
    config_flow: bool
    iot_class: str | None
    single_config_entry: bool
    # title translations are optional; see thesis/antithesis below
    title_translations: dict[str, str] | None   # {lang: title}

SandboxCatalogProvider = Callable[[], list[SandboxIntegrationDescriptor]]

@callback
def async_register_sandbox_catalog_provider(hass, provider) -> Callable[[], None]:
    ...
```

Then `async_get_integration_descriptions` (`loader.py:416-460`) — or a thin
sandbox-aware wrapper — merges these descriptors into the `custom.integration` /
`custom.helper` buckets exactly where the on-disk scan does today
(`loader.py:431-458`), de-duping by domain against on-disk customs. And
`frontend/get_translations` for category `title` gains a sandbox source: when a
domain isn't loadable on disk, pull `name` (and/or `title_translations[lang]`)
from the catalog instead of `integration.name` (the fallback at
`translation.py:118-124`).

Why a **separate** provider and not extending `IntegrationSourceDict`:

- The source resolver is *lazy per-domain* and *security-critical* (sha pinning,
  `sources.py:19-22,130-135`). The catalog is *eager enumerable* and *display-
  only*. Fusing them would force the security-critical path to also be a full
  listing API and would drag display strings through the sha-validation code.
- Keeps the wire/`entry_setup` proto (`pb.IntegrationSource`) untouched — title
  strings never need to cross to the sandbox; they're a main-side display
  concern.

### Thesis — extend the index to carry `title`

HACS already maintains a full catalog of installed (and installable) custom
integrations including their repo, version/sha (it supplies `ref` today), and
the `manifest.json` `name`. Surfacing `name` (+ optionally cached
`translations/en.json` `title`) per domain is nearly free for HACS and is the
single source of truth. Core stays agnostic (just a registry + a merge point);
the picker renders custom rows and a sensible name with zero sandbox spin-up.
Matches the established "core exposes hook, HACS fills" precedent exactly
(`sources.py` module docstring lines 10-14).

### Antithesis — what if HACS doesn't have translations indexed?

- HACS reliably knows the **manifest `name`** (it parses `manifest.json` to
  validate installs) and the sha. It does **not** necessarily have the
  integration's `translations/*.json` indexed — those live inside the repo
  tarball, which under the stateless model is only fetched at `entry_setup`. So
  `title_translations` may be empty for most/all domains.
- Mitigation built into the fallback chain we already rely on: if
  `title_translations[lang]` is absent, the picker degrades to
  `integration.name` (manifest name) — which is exactly the existing
  `translation.py:118-124` behavior and the `integration.name ||
  domainToName(...)` chain in `dialog-add-integration.ts:266`. So
  `title_translations` should be **optional**; the load-bearing field is `name`.
  A localized title is a nice-to-have, not a requirement, for the picker.
- Risk: a custom integration that *only* defines its display name in
  `translations/<lang>.json` `title` (no good manifest `name`) would show a
  prettified domain. Acceptable for v1; HACS could later cache `en.json` title
  at install time if it wants better names.
- Trust boundary: unlike `ref` (sha-pinned, security-critical), a wrong/missing
  `name` is cosmetic — no need for the strict validation the source path has.

**Recommendation:** ship the catalog provider carrying `name` + the small
picker-metadata subset; make `title_translations` optional. This unblocks the
picker with the data HACS definitely has, and the title localization can improve
later without a contract change.

---

## 4. Domain → sandbox-group resolution for the LIVE pull path (seam B)

When a flow IS running or an entry IS loaded, main already maps domain → group;
no catalog needed. The existing lookups:

- **`ConfigEntry.sandbox: str | None`** — the routing tag stored on the entry.
  Declared `config_entries.py:432`; `__init__` kwarg `:448`; written to
  `as_dict` `:1223-1224`; read back from storage `:1813` / `:2356`; plumbed via
  `async_finish_flow`/`async_update_entry` (`:2576`, `:2597`, `:2616`). Its value
  is the **group name** (e.g. `"custom"` / `"built_in"`), not a per-domain id.
- **New-flow assignment** — `router.py:189-201` `_assignment_for_new_flow`:
  first an *existing entry's* `sandbox` wins
  (`async_entries(handler_key)` → `existing.sandbox`, `:196-198`); otherwise
  `classify(integration)` decides (`classifier.py:58-76`: system/ALWAYS_MAIN/
  incompatible-platform → MAIN; `not is_built_in → GROUP_CUSTOM`; else
  `GROUP_BUILT_IN`). The classifier is *also* a domain→group function and works
  off the `Integration` object, **but it needs the integration loadable** — so
  for a sandbox-only custom not on disk, `classify` would fail to load it. For
  seam B that's fine because an existing entry's `sandbox` field already pins the
  group (the entry was created when the code was present / fetched).
- **Group → live bridge / channel** — `SandboxData`
  (`__init__.py:38-45`): `bridges: dict[str, SandboxBridge]` and
  `channels: dict[str, Channel]`, keyed by **group name**. Populated on channel
  ready (`__init__.py:53-57`). The router uses `self._data.bridges.get(group)`
  (`router.py:183-184`) and `self._manager.get(group)` / `ensure_started(group)`
  (`router.py:91`, `:168`). `entry_setup`/`unload` resolve group via
  `entry.sandbox` (`router.py:87`, `:165`).
- **Bridge-level domain tracking** — `bridge.py` keys its owned
  `EntityPlatform`s by `(entry_id, domain)` (`bridge.py:179-183`) and tracks
  mirrored `(domain, service)` pairs (`bridge.py:183`). This is reverse-mapping
  (group→domains it owns), used for entity/service mirroring, not for the
  picker's forward domain→group lookup.

**Net:** seam B's forward lookup already exists end-to-end:
`entry.sandbox` (group) → `SandboxData.bridges[group]` / `manager.get(group)`.
For a *running flow* the group is carried on `SandboxFlowProxy(sandbox_group=...)`
created in `async_create_flow` (`router.py:79-83`). So **a translation pull for a
live/in-progress sandboxed domain can be routed to the right bridge using the
existing group keying** — no new index needed for seam B; the catalog (§3) is
only for the cold picker (seam A).

---

## 5. Does the picker ever load category `config` in bulk?

**No.** The picker loads **only `title`**:

- `dialog-add-integration.ts:606` —
  `loadBackendTranslation("title", discoveredHandlers, true)` (discovered flow
  handlers only).
- `dialog-add-integration.ts:639-643` —
  `loadBackendTranslation("title", descriptions.core.translated_name, true)`.

No `config` / `selector` / fragment load anywhere in `dialog-add-integration.ts`.

`config`/`selector` are loaded **only once a specific flow starts**, in
`show-dialog-config-flow.ts`:

- `:29-33` (initial step):
  `loadFragmentTranslation("config")`, `loadBackendTranslation("config", handler)`,
  `loadBackendTranslation("selector", handler)`, `loadBackendTranslation("title",
  handler)`.
- `:40-46` (subsequent step): same set for `step.handler`.

So the heavy `config`/`selector` payload is per-flow and lazy. **For the picker we
only ever need `title` (which collapses to a display `name`)** — confirming §2's
"minimal data" conclusion: the catalog provider only has to carry a name, not
flow schema.

---

## Summary of the contract to build

- **Seam A (picker / cold):** new `async_register_sandbox_catalog_provider`
  (parallel to the source resolver). HACS fills a list of
  `{domain, name, integration_type, config_flow, iot_class,
  single_config_entry, title_translations?}`. Core merges it into
  `async_get_integration_descriptions` custom buckets (`loader.py:431-458`) and
  into the `title` fallback in `translation.py:118-124`. `name` is the
  load-bearing field; `title_translations` optional.
- **Seam B (live):** nothing new — reuse `entry.sandbox` → `SandboxData.bridges`
  / `manager.get(group)` (`router.py`, `__init__.py:38-45`).
- Keep the security-critical source resolver (`sources.py`) untouched and
  separate from the display-only catalog.
