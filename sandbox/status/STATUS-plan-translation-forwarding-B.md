# STATUS — plan-translation-forwarding (Phase B: live pull-RPC)

**Done.** Phase B (B1→B4) shipped — a sandboxed custom integration's frontend
translation strings (config / entity / state / services / exceptions, plus
`title`) now reach main's translation cache over a live `sandbox/get_translations`
RPC. Built-in sandboxed integrations are carved out (main reads its own
byte-identical disk). All three suites green, proto drift clean, prek clean on
every changed file. **Phase A (catalog provider / picker discoverability) is
untouched, as scoped.** Not pushed (orchestrator pushes); no `--no-verify`;
pre-commit passed on every commit.

## Commits

| SHA | What |
|---|---|
| `af129cb26a9` | B1 — `get_translations` wire protocol (proto + regen both `_pb2` mirrors + `protocol.py`/`messages.py` mirrors) |
| `5ffbe73ae2b` | B2 — sandbox-side runtime handler + `_collect_component_strings` loader (title pre-fill) |
| `8142996b085` | B3 — core translation provider hook + `_async_load` overlay + `async_invalidate` |
| `bb32e859f10` | B4 — main-side `SandboxTranslationProvider` impl + registration + reload invalidation |

Four commits, one per task, each leaving the tree green.

## What each task delivered

### B1 — wire protocol
- `sandbox/proto/sandbox.proto`: added `GetTranslations {language, domains[]}` /
  `GetTranslationsResult {language, strings: Struct}` (`strings` = `{domain: raw
  strings.json dict}`).
- Regenerated the checked-in gencode into **both** no-cross-import mirrors via
  `proto/generate.sh`; verified idempotent and that `proto/check_drift.sh`
  passes on the committed tree.
- Mirrored `MSG_GET_TRANSLATIONS` in both `protocol.py` files and registered the
  message pair in both `messages.py` `REGISTRY` copies.

### B2 — sandbox handler (`hass_client/sandbox/__init__.py`)
- `SandboxRuntime._handle_get_translations` registered on the channel next to
  ping/shutdown.
- Module helper `_collect_component_strings(hass, language, domains)` resolves
  each domain's `Integration` against the sandbox-private `hass` and **reuses
  core's `_async_get_component_strings`** — chosen over reading the file by hand
  for exact shape parity with main's merge target and free `title`→
  `integration.name` pre-fill (which main cannot do for a custom — it holds no
  `Integration`).
- Tests: built-in title pass-through, custom title injection, empty-domains,
  Struct packing via the handler, no-flow-runner guard.

### B3 — core hook (`homeassistant/helpers/translation.py`)
- `async_register_sandbox_translation_provider(hass, provider)` — `HassKey`-backed
  registry + unregister callback, mirroring `sandbox.sources`. Provider type
  `(list[str], set[str]) -> Awaitable[{language: {domain: raw_strings}}]`.
- `_TranslationCache._async_overlay_sandbox_strings` splices the provider result
  onto `translation_by_language_strings` **after** `async_get_integrations` and
  **before** `_build_category_cache`, so sandboxed strings flow through the same
  flatten / English-fallback / `loaded` machinery as disk strings. A custom
  sandboxed domain (`IntegrationNotFound` on main) thus stops resolving to `{}`.
- `_TranslationCache.async_invalidate(components)` + module wrapper
  `async_invalidate_translations` — the first eviction API (translations were
  otherwise never unloaded): drops the components from every `loaded[lang]` set
  and `del`s them from every `cache[lang][category]`.
- Core never wraps the provider — degrade-to-empty is the **provider's**
  contract (matches the `sources.py` resolver convention; keeps core minimal).
- Tests: overlay, degrade-to-empty (domain still marked loaded, never raises),
  non-sandboxed integration unaffected, invalidate-drops-stale across a
  simulated ref change.

### B4 — provider impl + registration (`homeassistant/components/sandbox/`)
- New module `translation.py` (see deviation note) — `SandboxTranslationProvider`:
  - **Group resolution** matches the flow router: a loaded entry's
    `entry.sandbox` wins; else the live `SandboxFlowProxy` of a brand-new
    custom's in-progress flow (new public `sandbox_group` property on the
    proxy).
  - **Built-in carve-out**: `Integration.is_built_in` ⇒ return nothing; main
    reads its bundled disk copy. `IntegrationNotFound` ⇒ a no-code custom that
    genuinely needs the RPC.
  - **Per-group batching**: one `get_translations` RPC per `(group, language)`
    with all of that group's owned domains.
  - **Degrade to empty**: no live channel, or a closed/errored/timed-out
    (`_RPC_TIMEOUT = 5.0s`) call ⇒ no strings for those domains. The overlay
    runs under the cache lock; this is what keeps a dead/slow sandbox from
    wedging the frontend translation endpoint.
- Registered in `async_setup`; unregistered in `_on_stop`.
- `router.async_unload_entry` now calls `async_invalidate_translations(hass,
  {entry.domain})` for sandboxed entries, so a reload at a new integration-source
  ref re-pulls fresh strings on the next fetch.
- Tests: custom-entry RPC (all five categories round-trip), built-in carve-out,
  dead-channel degrade, non-sandboxed/unknown skipped, flow-in-progress
  resolution, multi-language batching, unload-invalidates / plain-unload-doesn't.

## Verification (run on the final committed tree)

```
$ uv run pytest tests/helpers/test_translation.py -q
23 passed, 2 warnings in 0.39s

$ uv run pytest tests/components/sandbox/ --no-cov -q
201 passed, 2 warnings in 8.04s

$ uv run pytest sandbox/hass_client/ -q          # (run from sandbox/hass_client)
82 passed, 1 warning in 0.63s

$ bash sandbox/proto/check_drift.sh
sandbox proto drift guard: gencode matches sandbox.proto.

$ .venv/bin/prek run --files <all 18 changed files>
ruff check / ruff format / codespell / prettier / mypy / pylint ......... Passed
```

New tests added (per the plan's Verification section):
- `tests/components/sandbox/test_translation.py` — built-in carve-out + custom
  fixture over RPC (config/entity/state/services/exceptions), dead-channel
  degrade, non-sandboxed unaffected, flow-in-progress, reload invalidation.
- `tests/helpers/test_translation.py` — provider overlay, degrade-to-empty,
  `async_invalidate` drops stale strings, non-sandboxed unaffected.
- `sandbox/hass_client/tests/test_translation_provider.py` — title-prefilled raw
  dict for built-in + custom fixture, Struct packing, guards.

## Deviations / decisions (flagged for review)

1. **Provider lives in its own module** `homeassistant/components/sandbox/
   translation.py`, not inline in `bridge.py`/`__init__.py` (the plan's
   file-column hint). It is a *cross-group* concern (resolves domain→group
   across all bridges), whereas `SandboxBridge` is strictly per-group. A
   dedicated module matches the codebase's one-concern-per-file layout
   (`sources.py`, `classifier.py`, `router.py`) and carries its own test file.
   Registration still happens from `__init__.async_setup` as the plan specifies.
2. **Sandbox-restart invalidation** is covered transitively, not added as a
   separate hook. Strings can only change when the integration-source `ref`
   changes, which always arrives via an **entry reload** (HACS update → reload)
   — and reload's unload leg already invalidates. A bare crash-restart re-fetches
   the *same* `ref`, so its strings are unchanged and need no eviction. Adding a
   second invalidation in `_on_channel_ready` would only cost a redundant
   re-pull, so it was left out.
3. **Reuse of core's private `_async_get_component_strings`** on the sandbox side
   (B2) — explicitly blessed by the plan; chosen for shape parity + free title
   pre-fill over hand-reading the file.
4. **One core-private read**: `hass.config_entries.flow._handler_progress_index`
   in `_group_for_flow_in_progress`, to reach the live `SandboxFlowProxy` for a
   brand-new custom with no entry yet (the public flow API exposes only
   serialized results, which don't carry the group). This is a **read**, not a
   monkey-patch — the Iron Law (no patching of private internals) holds. The
   proxy's own group is exposed cleanly via the new public `sandbox_group`
   property.

## Tooling note

`uv run prek …` fails to spawn in this environment (`prek` not on uv's resolved
PATH); `.venv/bin/prek run --files …` is equivalent and was used for every
commit. The core prek `mypy`/`pylint` hooks skip `sandbox/hass_client/**` (it is
a separate `uv` env) — that side is covered by its own pytest suite, which is
green.

## Not in scope (Phase A — deferred)

Phase A (catalog provider for picker discoverability + `title` for a sandbox-only
custom in the add-integration dialog) is **untouched**. It pairs with the
broader stateless-custom-discovery work and ships independently per the plan's
phasing. Nothing in Phase B blocks it; the live path delivered here is the bulk
of the UX.
