# Core seam: redirecting a sandboxed integration's translation load to RPC

All citations are against the working tree at `/home/paulus/dev/hass/core`.
THE file is `homeassistant/helpers/translation.py`.

---

## 1. The redirect seam

### 1a. What `async_get_integrations` returns for an unknown (custom, sandboxed) domain

`_TranslationCache._async_load` (`translation.py:208-253`) calls
`async_get_integrations(self.hass, components)` (`:220`) and then iterates,
**skipping any domain whose value is an `Exception`** (`:221-227`):

```python
ints_or_excs = await async_get_integrations(self.hass, components)
for domain, int_or_exc in ints_or_excs.items():
    if isinstance(int_or_exc, Exception):
        _LOGGER.warning("Failed to load integration for translation: %s", int_or_exc)
        continue
    integrations[domain] = int_or_exc
```

`async_get_integrations` (`loader.py:1375-1449`) does **not** raise for an
unknown domain. It resolves custom components first (`:1413-1417`), then
`_resolve_integrations_from_root` (`:1426-1428`); for anything still
unresolved it returns an `IntegrationNotFound` *as the dict value*
(`loader.py:1441-1447`):

```python
del cache[domain]
exc = IntegrationNotFound(domain)
results[domain] = exc
future.set_result(exc)   # not set_exception — value, not raise
```

So for a custom sandboxed domain with no code on disk, main gets
`{domain: IntegrationNotFound(domain)}`. The cache deliberately does **not**
memoise the miss (`:1434-1441`), so a later disk appearance is re-resolvable.

### 1b. What `_async_get_component_strings` does with a missing Integration

`_async_get_component_strings` (`:86-128`) only ever reads `integrations.get(domain)`
— it never indexes, so a domain absent from the `integrations` dict simply
produces **no file to load** and **no title** (see §3). The two relevant guards:

- File collection (`:100-107`): a domain is only added to `files_to_load` when
  `(integration := integrations.get(domain)) and integration.has_translations`.
  A missing integration ⇒ skipped, no `KeyError`.
- Title injection (`:118-124`): `integration := integrations.get(domain)` is
  falsy ⇒ no `title` is set.

Net effect for a custom sandboxed domain on main today: it falls through
silently to `loaded_translations.setdefault(domain, {})` (`:120`) — an **empty
dict**, no warning beyond the `_async_load` one. That empty dict flows into
`translations_by_language[lang][domain] = {}`, `_build_category_cache` finds no
categories for it, and the domain is marked loaded with zero strings. **The
integration's frontend strings are simply missing** — this is the gap to fill.

### 1c. Recommended seam — split sandboxed domains out *before* `_async_load`

**Thesis:** redirect inside `_async_load`, by partitioning `components` into
`local` vs `remote` and merging an RPC result into
`translation_by_language_strings` *before* `_build_category_cache` runs. This is
the single cleanest seam because:

- `_async_load` already owns the `language → languages` fallback expansion
  (`:217`), the per-language cache build (`:234-251`), and the `loaded` set
  bookkeeping (`:244-253`). A sandboxed domain must go through the *same*
  `_build_category_cache` / `loaded` machinery so `get_cached`, the
  English-fallback overlay, and `async_is_loaded` keep working uniformly.
- `_async_get_component_strings` is the right *shape* producer to mirror (its
  output is the merge target), but it is `Integration`-driven and disk-path
  only. Putting the branch there would force passing the sandbox lookup down
  one more layer for no benefit. Keep that function untouched (disk-only).

Concretely, the branch sits right after `async_get_integrations` returns, in
`_async_load` (`:219-231`):

```python
integrations: dict[str, Integration] = {}
ints_or_excs = await async_get_integrations(self.hass, components)
for domain, int_or_exc in ints_or_excs.items():
    if isinstance(int_or_exc, Exception):
        _LOGGER.warning("Failed to load integration for translation: %s", int_or_exc)
        continue
    integrations[domain] = int_or_exc

translation_by_language_strings = await _async_get_component_strings(
    self.hass, languages, components, integrations
)
# NEW: overlay remote (sandboxed) component strings fetched over RPC.
# For each sandboxed domain in `components`, replace its (empty) entry in
# translation_by_language_strings[lang][domain] with the RPC payload.
```

**Why not split before `_async_load` (in `async_load`, `:160-176`)?** That
would bypass the lock-coalescing (`:166-176`) and the
`components - loaded` diff that `async_load` computes, and would need to
duplicate the English-fallback `languages` expansion. The diff/lock belong to
the *whole* component set; only the *strings source* differs per-domain. So
split inside `_async_load`, not above it.

**Main risk / antithesis:** `_async_load` runs under the cache lock and is
`await`-heavy already; adding a synchronous RPC round-trip per sandboxed domain
serialises translation loads behind the channel. Frontend translation fetches
are frequent and latency-sensitive (`async_get_translations` is called per
category). Mitigations: batch all remote domains of one group into a single RPC
(the channel already multiplexes — `channel.call`, `channel.py:392`), and have
the RPC payload pre-shaped so no extra disk/CPU work happens under the lock. A
channel-down / `IntegrationNotFound`-equivalent must degrade to "empty strings,
domain marked loaded" (today's behavior) rather than raising, so a dead sandbox
never wedges the frontend translation endpoint.

### 1d. Required RPC return shape

The merge target is `translation_by_language_strings`, the return of
`_async_get_component_strings` (`:91-128`). Shape is
**`{language: {domain: <raw strings.json dict>}}`**:

```python
translations_by_language: dict[str, dict[str, Any]] = {
    "en": {
        "light": {                     # == contents of light/translations/en.json
            "title": "...",            # injected from integration.name if absent
            "config": {...},
            "entity": {...},
            "exceptions": {...},
            ...
        },
    },
    "<lang>": { "light": {...} },
}
```

`_build_category_cache` (`:300-330`) then walks each component's top-level keys
as *categories* (`config`, `entity`, `exceptions`, `entity_component`, …),
calls `build_resources` (`:71-83`) per category, and `recursive_flatten`s into
`component.<domain>.<category>.<...>` keys. So the RPC must return the **raw,
un-flattened nested `strings.json` structure** for each requested language —
exactly what a `translations/<lang>.json` file on disk contains, with `title`
already filled in (the sandbox *has* the `Integration` and can inject it; see
§3). The languages requested are `["en"]` or `["en", <lang>]` (`:217`) — the
RPC should accept that language list and return both, because `_async_load`
loads English as the fallback overlay (`:233-251`).

---

## 2. Cache structure & invalidation

### Keying

`_TranslationsCacheData` (`:131-141`) holds two dicts shared across cache
instances:

- `loaded: dict[str, set[str]]` — per **language** → set of component domains
  already loaded. Drives `async_is_loaded` (`:156-158`,
  `components.issubset(...)`) and the `components - loaded` diff (`:167`, `:175`).
- `cache: dict[str, dict[str, dict[str, dict[str, str]]]]` — nested
  **`language → category → component → {flat_key: value}`** (built in
  `_build_category_cache`, `:309-330`; read in `get_cached`, `:196-206`).

Flat keys are `component.<domain>.<category>.<path>` (`:324`, `:327-328`).

### "Never unloaded"

The comment is in `async_load` (`:168-171`):

```python
# Translations are never unloaded so if there are no components to load
# we can skip the lock which reduces contention ...
```

There is **no eviction API anywhere** in `translation.py`. `loaded` only ever
grows (`:166` `setdefault`, `:251`/`:253` `update`); `cache` only ever
`setdefault`/`update` (`:309`, `:318`, `:321`, `:330`). Nothing deletes from
either. (`async_setup`, `:382-412`, only *adds* on language change.)

### What re-fetch-at-new-sha needs

For a custom integration re-fetched at a new commit sha whose `strings.json`
changed, stale entries to drop are, for that one `domain` across **all
languages** and **all categories**:

- every `loaded[lang]` set containing `domain` → `discard(domain)`
- every `cache[lang][category]` dict that has a `domain` key → `del`

There is **no existing API** to do this. Minimal addition: a single callback
method on `_TranslationCache`, e.g.

```python
@callback
def async_invalidate(self, components: set[str]) -> None:
    """Drop cached + loaded state for the given components (all languages)."""
    for loaded in self.cache_data.loaded.values():
        loaded -= components
    for by_category in self.cache_data.cache.values():
        for category_cache in by_category.values():
            for component in components & category_cache.keys():
                del category_cache[component]
```

plus a thin module-level `async_invalidate_translations(hass, components)`
wrapper that goes through `_async_get_translations_cache(hass)` (`:376-379`),
mirroring the existing `async_load_integrations` wrapper (`:415-419`). The
sandbox would call it on each re-fetch / entry reload of a custom domain, and
the next `async_fetch` re-runs `_async_load` (now via the RPC seam from §1).
Note: invalidation must hold or respect `self.lock` (`:153`, `:172`) if it can
race a concurrent `_async_load`; the simplest correct form is to make it
`async` and take the lock, or to document it as caller-serialised against loads.

---

## 3. `title` fallback needs an `Integration` — confirmed

`:118-124`:

```python
for domain in components:
    component_translations = loaded_translations.setdefault(domain, {})
    if "title" not in component_translations and (
        integration := integrations.get(domain)
    ):
        component_translations["title"] = integration.name
```

The fallback reads `integration.name`, which requires the `Integration`
object's manifest. For a custom sandboxed domain main has **no `Integration`**
(§1a returns `IntegrationNotFound`), so this branch **cannot run on main** for
such a domain — `integrations.get(domain)` is `None` and `title` stays unset.

**Implication:** title injection must happen **on the sandbox side**, which
*does* hold the loaded `Integration` (it fetched + imported the code). The RPC
payload should therefore return component strings with `title` already filled
(the sandbox runs the equivalent of `_async_get_component_strings`' title
fallback before serialising). If the sandbox omits it, the integration's
display name is blank on main's frontend. Built-in sandboxed domains are a
non-issue — their `Integration` resolves on main from the bundled package, so
they could even stay on the local disk path; only **custom** domains truly need
the remote title.

---

## 4. Existing core hooks to mirror

### `async_register_sandbox_source_resolver` (the convention to copy)

`homeassistant/components/sandbox/sources.py:67-87` — a `@callback` that appends
a resolver to a `HassKey`-stored list and returns an unregister `@callback`:

```python
SandboxSourceResolver = Callable[[str], IntegrationSourceDict | None]   # :56
DATA_SOURCE_RESOLVERS: HassKey[list[SandboxSourceResolver]] = HassKey(
    "sandbox_source_resolvers")                                          # :58-60

@callback
def async_register_sandbox_source_resolver(hass, resolver):              # :67-87
    resolvers = hass.data.setdefault(DATA_SOURCE_RESOLVERS, [])
    resolvers.append(resolver)
    @callback
    def _unregister() -> None:
        resolvers.remove(resolver)
    return _unregister
```

The consumer (`async_resolve_integration_source`, `:90-114`) short-circuits
built-ins via `Integration.is_built_in` and otherwise consults resolvers in
order, **raising** `SandboxSourceError` if none matches. A "remote translation
provider" hook can follow this exact convention: a `HassKey`-stored provider
keyed by group (or a single resolver `domain → group | None`), registered by
the sandbox integration at setup, consulted from the new `translation.py`
branch. Because `translation.py` is in `homeassistant/helpers/` (core), it must
**not** import the `sandbox` component — the hook lives there as a registration
seam exactly like the source resolver, and the sandbox integration registers
into it.

### The `router` attribute on `ConfigEntries`

`config_entries.py:2160-2161` — a single nullable hook attribute:

```python
# Optional hook for diverting flows and entry setup (used by sandbox).
self.router: ConfigEntryRouter | None = None
```

`ConfigEntryRouter` is a `Protocol` (`:2121-2142`) with three `async def`
methods (`async_create_flow`, `async_setup_entry`, `async_unload_entry`), each
returning `None` to fall through. `SandboxFlowRouter` (`router.py:46`)
structurally implements it; it's assigned in `sandbox/__init__.py:96`
(`data.router = router`) and presumably set onto `hass.config_entries.router`
at setup. A translation hook could mirror either style — a list of providers
(source-resolver style) or a single Protocol object (router style). The
**list-of-resolvers** style is the better fit here since translation has no
fall-through chain semantics beyond "which group owns this domain".

### Where the singleton translation cache lives on hass

`translation.py:376-379` — stored via the `singleton` decorator under the key
`TRANSLATION_FLATTEN_CACHE = "translation_flatten_cache"` (`:29`):

```python
@singleton.singleton(TRANSLATION_FLATTEN_CACHE)
def _async_get_translations_cache(hass: HomeAssistant) -> _TranslationCache:
    return _TranslationCache(hass)
```

Every public entry point (`async_get_translations` `:353`,
`async_get_cached_translations` `:371`, `async_load_integrations` `:417`,
`async_translations_loaded` `:425`) goes through `_async_get_translations_cache(hass)`.
A new `async_invalidate_translations(hass, ...)` (§2) and any provider lookup
hang off the same singleton, so there is exactly one cache + one hook registry
per `hass`.

---

## 5. Liveness guard — knowing a domain is sandboxed and its group, at load time

Two signals already exist; both are reachable from `hass` without importing the
sandbox internals if a small accessor hook is added (per §4).

### Loaded-entry case (authoritative)

`ConfigEntry.sandbox: str | None` (`config_entries.py:432`, declared
`:566-569`) is the group name, set at flow completion (`:1813`,
`async_finish_flow` reads `ConfigFlowResult["sandbox"]`) and read back from
storage (`:2356`). It persists in `as_dict` only when set (`:1221-1224`). So at
translation-load time, the canonical "is `domain` sandboxed and where" is:

```python
for entry in hass.config_entries.async_entries(domain):
    if entry.sandbox is not None:
        group = entry.sandbox   # this domain is sandboxed into `group`
        break
```

This is exactly the pattern the router already uses for new flows —
`SandboxFlowRouter._assignment_for_new_flow` (`router.py:189-200`) loops
`async_entries(handler_key)` and returns `existing.sandbox` if set, else falls
back to `classify(integration)`. Translation loading should reuse that resolve
order (entry-wins, classifier-fallback) so it agrees with where the entry
actually ran.

### Live-channel / bridge case (for issuing the RPC)

Group → live transport lives in `SandboxData` (`sandbox/__init__.py:38-45`),
stored under `DATA_SANDBOX` (`const.py:12`,
`HassKey[SandboxData](DOMAIN)`):

- `data.bridges: dict[str, SandboxBridge]` (`:45`) — the per-group bridge owning
  the channel; populated in `_on_channel_ready` (`:53-57`).
- `data.channels: dict[str, Channel]` (`:44`) — the raw channel.
- `data.manager.get(group)` (`manager.py:582-584`) returns the
  `SandboxProcess` or `None`; `sandbox.channel` may be `None` if down
  (router checks this at `router.py:104-105`, `:169`).

So the RPC issuer resolves `domain → group` (via `entry.sandbox`), then
`group → channel` (via `data.bridges[group].channel` or
`manager.get(group).channel`), then `channel.call(MSG_..., payload)`
(`channel.py:392`). If the group has no running sandbox / no live channel, the
guard degrades to empty strings (the §1c risk note) — never raise into the
frontend translation path.

### Pre-entry (flow-in-progress) case

Before any `ConfigEntry` exists (the add-integration flow is mid-render and
wants config-flow translations — `async_get_translations(..., config_flow=True)`,
`:346-347`), `entry.sandbox` is unavailable. Fall back to
`classify(await async_get_integration(hass, domain))`
(`classifier.py:58-76`) — the same fallback the flow router uses
(`router.py:199-200`). For a **custom** domain, `classify` returns
`Sandbox("custom")` (`classifier.py:73-74`) **without importing** the
integration (it uses manifest + `platforms_exists`). Caveat: at flow-start the
custom integration's code may not yet be on disk on main at all, so even
`async_get_integration` can raise `IntegrationNotFound` — in that pre-entry,
no-code state the loader genuinely has nothing, and the config-flow translation
RPC must target whichever group the flow proxy spun up (the flow already routes
through `SandboxFlowProxy`, `router.py:79-83`, which knows its
`sandbox_group`). That is the trickiest corner: config-flow translations for a
brand-new custom integration need the *flow's* group, not an entry's group.

---

## Summary of the recommended change set

1. **Seam:** branch in `_TranslationCache._async_load` (`translation.py:219-231`),
   after `async_get_integrations`, overlaying remote-fetched
   `{lang: {domain: raw_strings}}` onto `translation_by_language_strings`.
2. **Hook:** a source-resolver-style registry (mirror `sources.py:58-87`) so
   core stays sandbox-agnostic; the sandbox integration registers a
   `domain → group` resolver + an RPC fetcher.
3. **RPC shape:** raw un-flattened `strings.json` nesting per requested
   language, `title` pre-injected sandbox-side (§3).
4. **Invalidation:** new `async_invalidate(components)` on `_TranslationCache`
   (`loaded` discard + `cache[*][*]` del) + module wrapper, called on re-fetch
   at a new sha (§2).
5. **Liveness:** resolve group via `entry.sandbox` (entry-wins) →
   `classify` fallback (pre-entry); resolve channel via
   `DATA_SANDBOX.bridges[group]`; degrade to empty on a down channel.
