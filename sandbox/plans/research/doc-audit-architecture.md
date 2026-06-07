# Doc audit — `sandbox/ARCHITECTURE.md` vs. code

Audited 2026-06-05. Doc path: `/home/paulus/dev/hass/core/sandbox/ARCHITECTURE.md`.
Method: every concrete name / RPC / routing rule / table row / core touch-point
checked against the implementation.

## Verified accurate

Near everything the doc names checks out exactly:

- **Main-side components table (§2):** `SandboxFlowRouter`
  (`router.py:47`), `SandboxManager` (`manager.py:527`), `SandboxBridge`
  (`bridge.py:162`), `classifier.py` (`classify`, `classifier.py:58`),
  `sources.py` (`async_register_sandbox_source_resolver`, `sources.py:68`).
- **Sandbox-side components table (§2):** `SandboxRuntime`
  (`sandbox/__init__.py:57`), `FlowRunner` (`flow_runner.py:87`),
  `EntryRunner` (`entry_runner.py:27`), `EntityBridge` (`entity_bridge.py:38`),
  `ServiceMirror` (`service_mirror.py:38`), `EventMirror` (`event_mirror.py:73`),
  `ApprovedDomains` (`approved_domains.py:35`), `ChannelSandboxBridge`
  (`sandbox_bridge.py:31`, doc calls it the store bridge per §8). `_SandboxFlowManager`
  exists (`flow_runner.py:65`).
- **Routing (§3):** classifier order matches `classifier.py:58-76` exactly
  (`integration_type=="system"`, `ALWAYS_MAIN`, `SANDBOX_INCOMPATIBLE_PLATFORMS`,
  custom→`custom`, else→`built-in`; uses `platforms_exists` + `is_built_in`).
  `SANDBOX_INCOMPATIBLE_PLATFORMS` is exactly the 6 named (`const.py:29-44`).
  `ALWAYS_MAIN` behavioural punts + the 18 lockdown helpers match `const.py:47-108`
  verbatim.
- **Channel/transport (§4):** `ProtobufCodec` (`codec_protobuf.py:25`),
  `JsonCodec` + `Transport`/`StreamTransport` (`channel.py:173/223/243`),
  4-byte big-endian length-prefix, `from_transport` seam, `Ready` frame
  (`sandbox/ready`), `ws://` reserved→`NotImplementedError`
  (`sandbox/__init__.py:242`), inflight semaphore. `.proto` regen via
  `proto/generate.sh` + `check_drift.sh` present.
- **Lifecycle (§5):** restart budget `3` / `60.0s` / backoff / `failed` state
  (`manager.py:47-48`, 288-303). `python -m hass_client.sandbox --name <group> --url stdio://`
  form matches (`--name`, not `--group`).
- **Flow forwarding (§6):** `SandboxFlowProxy(ConfigFlow)` (`proxy_flow.py:48`);
  `create_result["sandbox"] = self._sandbox_group` (`proxy_flow.py:213`) confirms
  "main overwrites the group". `schema_bridge.py` rebuilds real `selector.Selector`
  / `data_entry_flow.section` (`schema_bridge.py:69-92`).
- **Statelessness / source (§7):** `IntegrationSource` proto (`sandbox.proto:99`),
  `kind: builtin|git` with `url/ref/tag/domain/subdir`, resolver hook
  + `is_built_in` short-circuit + raise-on-missing-resolver (`sources.py`).
- **Entity bridge (§8):** "all **32** domains have one under `entity/`" — exactly
  32 proxy files. `EntityDescription`/`EntityInfo`/`InitialState`,
  `register_entity` upsert, `<domain>:<unique_id>` prefix, `vol.Invalid`
  rebuild from `error_data` all present. The "coalescing… is a noted future
  optimisation" wording matches the just-landed batcher removal
  (`bridge.py:231-232`, no batcher in code).
- **Context (§8):** 15-min TTL `_CachedContext` cache, `context_id`-only wire,
  fresh `Context(user_id=None)` on miss — matches `bridge.py:95` and the proto
  (no `parent_id`/`user_id` on the wire).
- **Store routing (§9):** `current_sandbox` ContextVar in
  `helpers/sandbox_context.py`, read by `Store._async_load_data` /
  `_async_write_data` / `async_remove` (`storage.py:361,601,650`).
- **Core touch surface (§11):** `config_entries.py` `ConfigEntryRouter` Protocol
  (`config_entries.py:2121`) + `router` attr (`:2161`) + `ConfigEntry.sandbox`
  field (`:432`); `EntityComponent.async_register_remote_platform`
  (`entity_component.py:207`); `sandbox_context.py` + `storage.py`.

## Drift / inaccuracies

Effectively none in the literal claims that exist — every named symbol, RPC,
constant, and count checked out. The only inaccuracy is one of *completeness*,
which manifests as a now-false framing claim:

- **§11, line 293 — "three surfaces" is now stale.**
  > "The sandbox is deliberately small against core HA — **three surfaces**…"
  Translation forwarding (merged after this doc's last revision) added **two more
  core touch-points** not listed:
  - `homeassistant/helpers/translation.py` —
    `async_register_sandbox_translation_provider` (`:501`),
    `_async_overlay_sandbox_strings` (`:304`), `async_invalidate_translations`
    (`:526`), `SandboxTranslationProvider` callable type (`:43`).
  - `homeassistant/loader.py` — `async_register_sandbox_catalog_provider`
    (`:455`), `async_get_sandbox_catalog` (`:476`), `SandboxIntegrationDescriptor`
    (`:416`), and the catalog merge inside `async_get_integration_descriptions`
    (`:536-539`).
  **Severity: stale/misleading.** The "three surfaces" number is now wrong; the
  doc's own framing ("each a declared public hook") would apply cleanly to these
  two as well, so they belong in the list.

## Omissions

The dominant finding: **the entire translation-forwarding subsystem is absent
from the doc body.** "translations" appears only in the Goal (§1, line 22:
"…events, and translations available on main…") as an aspiration; line 220's
"Exception translation" is unrelated (it is `vol.Invalid` rebuild). Nowhere in
the body, the §2 component tables, the §4 RPC inventory, §11 core touch surface,
or §13 future-work list is the mechanism described. Yet the code is fully
shipped and wired end-to-end:

- **Wire:** `GetTranslations` / `GetTranslationsResult` proto messages
  (`sandbox.proto:162-176`); `sandbox/get_translations` registered in both
  `messages.py` mirrors (`:41`) and both `protocol.py` mirrors
  (`MSG_GET_TRANSLATIONS`).
- **Sandbox side:** handler `_handle_get_translations`
  (`hass_client/sandbox/__init__.py:262`), registered at `:198`.
- **Main side:** `components/sandbox/translation.py` (`SandboxTranslationProvider`,
  resolves group, batches custom domains into one RPC/language, degrades to
  empty under the cache lock); `components/sandbox/catalog.py` (re-exports the
  loader catalog hook for the add-integration picker); registered in
  `components/sandbox/__init__.py:106-107`.
- **Core:** the `translation.py` + `loader.py` hooks above.

**Does it matter for a "current architecture" reference?** Yes. The doc's
masthead (lines 3-7) claims to be the "**final, current architecture**" and a
"state-of-the-system reference." A reader using it to understand how a
sandboxed custom integration's frontend strings (entity names, config-flow
labels, services, exceptions) reach main would find the Goal promises it but no
section explains it — and would be actively misled by the "three surfaces"
count in §11. This is the single material gap.

Minor omissions (lower stakes, arguably fine for an overview-level doc):

- §2 main-side table omits `translation.py` / `catalog.py` (companion to the
  §11 gap).
- Picker/catalog integration (loader merge) for sandbox-only customs is
  undocumented; relevant to anyone wiring HACS into the picker.

## Verdict

ARCHITECTURE.md is **substantially accurate** on everything it describes —
every name, RPC, routing rule, constant, and count verified against code, with
zero literal contradictions found. Its one real defect is an **omission**: the
shipped translation-forwarding feature (proto RPC + main provider + catalog +
two core hooks) is entirely missing from the body, which also falsifies the
§11 "three surfaces" claim. To be the "final, current architecture" it must add
a translation-forwarding section, list `translation.py`/`catalog.py` in §2, and
bump §11 to five surfaces.
