# Scratchpad — translation forwarding

Decisions, rejected paths, and things to remember while implementing
`plan-translation-forwarding.md`.

## Decisions (locked)
- **Both seams** — live pull-RPC (B) + catalog provider (A).
- **Pull/RPC**, not push — matches the lazy per-language `_TranslationCache`;
  only fetch what the frontend asks for.
- **Built-in reads local disk** in the live path — files are byte-identical on
  main; RPC reserved for customs. One `is_built_in` branch in the provider.
- **Whole-strings-dict** RPC granularity — main slices via `build_resources`,
  matching how it reads the file today.
- **Separate** `async_register_sandbox_catalog_provider` for the picker — do
  NOT overload the sha-pinned `IntegrationSourceDict` source resolver.

## Rejected / not chosen
- Push-at-setup / hybrid transport — needs a language-set decision + still
  needs pull on language switch. Dropped.
- Pure unified pull (RPC for built-in too) — redundant data + needless sandbox
  spawn for the picker. Replaced by the built-in disk carve-out.
- Spawning every sandbox to render the bulk picker — rejected; picker only
  needs `title`, served statically (disk for built-in, catalog for custom).

## Landmines (from research, file:line)
- `async_get_integrations` returns `IntegrationNotFound` as the dict **value**,
  never raises, never caches the miss (`loader.py:1441-1447`).
- `_async_load` skips Exception-valued domains (`translation.py:221-227`);
  missing domain ⇒ silent `{}`.
- No cache-eviction API — `loaded`/`cache` only grow (`translation.py:168-171`).
  Must add `async_invalidate`.
- `title`→`integration.name` fallback (`translation.py:118-124`) needs an
  `Integration` object — impossible on main for customs ⇒ pre-fill sandbox-side.
- Picker uses `integration/descriptions` (disk scan, `loader.py:325-343,
  416-460`), NOT `async_get_config_flows`. Sandbox-only custom is in none.
- Picker loads only `title` (`dialog-add-integration.ts:606,639-643`);
  `config`/`selector` load per-flow (`show-dialog-config-flow.ts:29-46`).

## Open questions to resolve during work
- Exact RPC batching unit: per group is the intent — confirm the provider
  groups `components` by `ConfigEntry.sandbox` before issuing RPCs.
- Boot-time translation loads before any sandbox is up — verify the provider
  returns `{}` (fall through to disk/empty), never blocks.
