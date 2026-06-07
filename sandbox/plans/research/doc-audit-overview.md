# Doc audit — `sandbox/OVERVIEW.md` vs. implementation

Audited 2026-06-05 against the working tree. Doc path:
`/home/paulus/dev/hass/core/sandbox/OVERVIEW.md`.

## Verified accurate

- **Classifier rule order & structure.** `classify()` matches the doc's
  five-rule order exactly: `integration_type == "system"` → main, `ALWAYS_MAIN`
  → main, `SANDBOX_INCOMPATIBLE_PLATFORMS` intersection → main, custom →
  `Sandbox("custom")`, else `Sandbox("built-in")`
  (`homeassistant/components/sandbox/classifier.py:58-76`). Uses
  `platforms_exists()` (line 67), so no import — as the doc states (line 137).
- **`SANDBOX_INCOMPATIBLE_PLATFORMS` list.** Exactly `stt, tts, conversation,
  assist_satellite, wake_word, camera` (`const.py:29-44`) — matches doc line 118.
- **Three groups (`main`/`built-in`/`custom`).** `classifier.py:31-32`,
  group table at OVERVIEW lines 123-129 is correct.
- **Spawn command.** `manager._default_command` builds `[python, -m,
  hass_client.sandbox, --name <group>, --url <url>]`
  (`manager.py:657-672`); `__main__.py:21-34` defines `--name` (required) and
  `--url` (default `stdio://`). Doc lines 148-152 accurate (doc's `<name>` = the
  group).
- **Transport scheme handling.** `stdio://` default, `unix://<path>` opt-in,
  `ws://`/`wss://` reserved + rejected with `NotImplementedError`
  (`hass_client/sandbox/__init__.py:236-246`, `_transport_scheme` 410-427).
  Matches doc lines 154-166.
- **Ready handshake.** Runtime pushes `MSG_READY` (`sandbox/ready`) as first
  frame (`hass_client/sandbox/__init__.py:193`), manager treats arrival as
  running; no stdout text marker. Matches doc lines 158-161.
- **Crash-recovery budget.** `DEFAULT_RESTART_LIMIT = 3`,
  `DEFAULT_RESTART_WINDOW = 60.0`, `DEFAULT_RESTART_BACKOFF = 1.0`
  (`manager.py:47-49`); `_supervise` sliding-window pop + `state="failed"` on
  budget exhaustion (`manager.py:287-333`). Doc lines 170-175 accurate **except
  the SETUP_RETRY claim — see Drift**.
- **Graceful shutdown sequence.** `_on_stop` runs
  `async_graceful_shutdown_all(timeout=shutdown_grace)` then `async_stop_all()`
  (`__init__.py:111-125`); runtime `_handle_shutdown` snapshots restore-state,
  replies, then `call_soon(self._shutdown.set)`
  (`hass_client/sandbox/__init__.py:248-353`); `_on_shutdown_reply` writes
  `core.restore_state` via the bridge store server (`__init__.py:63-91`).
  Matches doc lines 184-199. Warm-load via `current_sandbox` before handlers
  register (`hass_client/sandbox/__init__.py:177-194`, `_load_restore_state`
  386-407) — matches doc lines 201-209.
- **Config-flow router: three call sites.** `ConfigEntries.router` consulted
  from `async_create_flow`, `async_setup`, `async_unload` (per
  `sandbox/CLAUDE.md` and verified import surface). Proxy issues
  `flow_init`/`flow_step`/`flow_abort`; `_adapt_result` attaches
  `sandbox=<group>` on CREATE_ENTRY (`proxy_flow.py:15-17`), stored on
  `ConfigEntry.sandbox`. `unique_id` propagation present. Doc lines 211-256
  accurate.
- **Integration source.** `sources.py` resolver hook: `is_built_in`
  short-circuits to `{kind: "builtin"}` (line 103-104); no-resolver custom
  **raises** `SandboxSourceError` (line 111); `tag` logs-only. Matches doc lines
  258-283. Sandbox side `hass_client/sources.py` exists.
- **Entity bridge Option B + 32 proxies.** `entity/` holds exactly **32**
  domain files (excluding `__init__.py`), matching the named list (doc lines
  356-364). Device-registry bridging via `dr.async_get(...).async_get_or_create`
  on `device_info` (`bridge.py:366-373`). `register_entity` upsert + namespaced
  `unique_id` (`<domain>:<unique_id>`, `const.py:21`). Doc lines 295-373
  accurate.
- **Store routing.** `Store._async_load_data` / `_async_write_data` /
  `async_remove` all read `current_sandbox` and delegate
  (`helpers/storage.py:361-366, 600-610, 644-652`); branch at
  `_async_write_data` not `async_save` (doc line 466 correct). `current_sandbox`
  ContextVar + `SandboxBridge` Protocol in `helpers/sandbox_context.py`. Key
  validation `_require_key`. Doc lines 462-502 accurate.
- **Auth: no credential.** `auth.py` is gone; no `--token` argv (`__main__.py`
  has only `--name`/`--url`/`--log-level`); no `SANDBOX_TOKEN`. Context
  restoration TTL cache on the bridge. Doc lines 410-450 accurate.
- **`JsonCodec` retained for channel-core tests only.** `channel.py:173-181`
  confirms ("registry-free test/debug wire … stays for the channel-core tests
  only"). Doc lines 163-164 accurate.
- **Protocol mirror parity.** `protocol.py` (main) and
  `hass_client/protocol.py` are verbatim mirrors, both now carrying
  `MSG_GET_TRANSLATIONS = "sandbox/get_translations"`.

## Drift / inaccuracies

### 1. `ALWAYS_MAIN` list is badly out of date — HIGH severity
- **Doc claim (lines 111-113):** "Hand-picked deny-list: `script`,
  `automation`, `scene`, `cloud`, `ai_task`, `image`."
- **Actual (`const.py:47-109`):** the frozenset has **24** entries:
  `script, automation, scene, cloud, ai_task, image` **plus** `template,
  group, homekit, min_max, statistics, trend, threshold, derivative,
  integration, utility_meter, filter, mold_indicator, bayesian,
  generic_thermostat, generic_hygrostat, switch_as_x, history_stats,
  proximity`. These are the "broad readers / source-entity helpers" added for
  built-in lockdown breakage (referenced in
  `plans/research/builtin-lockdown-breakage.md`).
- The doc lists fewer than a third of the real deny-list and gives no hint that
  a whole class of "reads foreign entities/registries" integrations is forced to
  main. This is a routing-rules claim — the most checkable, highest-value part
  of the doc — so the omission is material.

### 2. Failed-sandbox setup surfaces `SETUP_ERROR`, not `SETUP_RETRY` — MEDIUM
- **Doc claim (lines 173-175):** exhausting the restart budget "transitions the
  sandbox to `failed` and `ensure_started` raises `SandboxFailedError` — the
  router surfaces this as `SETUP_RETRY` on the affected entries."
- **Actual (`router.py:91-103`):** `async_setup_entry` catches the
  `ensure_started` exception and sets
  `ConfigEntryState.SETUP_ERROR` ("Sandbox failed to start"), **not**
  `SETUP_RETRY`. (`SETUP_RETRY` is used elsewhere — only for a `ChannelClosedError`
  *during* `entry_setup`, `router.py:133-138`.) The doc conflates the two paths.

### 3. "Periodic 30s ping loop is wired through but currently disabled" — MEDIUM
- **Doc claim (lines 177-180):** "A `sandbox/ping` handler is registered and
  exercised by the subprocess test … the periodic 30s ping loop is wired through
  but currently disabled."
- **Actual:** the `sandbox/ping` *handler* exists on the sandbox side
  (`hass_client/sandbox/__init__.py:195, 458-460`) and the proto pair is in the
  registry (`messages.py:43`). But there is **no ping loop of any kind in
  `manager.py`** — `grep -i ping manager.py` finds nothing. The claim that a 30s
  loop is "wired through" overstates reality: nothing on the manager ever sends a
  ping. Only the on-demand handler + test round-trip exist. ("Disabled" is
  arguably defensible, but "wired through" is not — there is no loop code.)

### 4. Stale "Status" banner & phase framing — LOW (whole-doc)
- **Doc claim (lines 3-23, 532-536, and the "Where the design is still open"
  section):** the doc frames itself as "Complete through Phase 20" and treats
  translation forwarding as nonexistent. The translation-forwarding feature
  (below) has since merged, so the phase narrative no longer captures the
  shipped surface. Not a code-contradiction per se, but the banner now
  under-describes the system.

## Omissions

### A. Translation forwarding is entirely undocumented in the body — HIGH
The recently merged translation-forwarding feature is fully wired and verified,
but OVERVIEW.md mentions translations **only** in the Goal line (line 30,
"…and translations"). Nothing in the body describes the mechanism. Verified
pieces the doc should cover:

- **Main provider hook:** `helpers/translation.py` —
  `async_register_sandbox_translation_provider` (line 501),
  `_async_overlay_sandbox_strings` (line 304, merges overlay before
  `_build_category_cache`), `DATA_SANDBOX_TRANSLATION_PROVIDERS` registry (line
  48), `async_invalidate` (line 189).
- **Sandbox component provider:** `components/sandbox/translation.py`
  (`SandboxTranslationProvider`): resolves owning group (loaded entry's
  `sandbox` field, else in-progress `SandboxFlowProxy.sandbox_group`), built-in
  carve-out via `is_built_in`, batches custom domains per group into one
  `sandbox/get_translations` RPC per language, 5s timeout → degrade-to-empty.
- **Registration:** `components/sandbox/__init__.py:104-109` registers the
  provider in `async_setup` and `_on_stop` unregisters it (line 121).
- **Catalog hook (picker):** `components/sandbox/catalog.py` re-exports
  `loader.SandboxCatalogProvider` / `SandboxIntegrationDescriptor` /
  `async_register_sandbox_catalog_provider`; `loader.async_get_integration_descriptions`
  merges sandbox-only customs into the picker (`loader.py:536-549`).
- **Wire:** `MSG_GET_TRANSLATIONS` in both `protocol.py` mirrors; proto pair
  `(GetTranslations, GetTranslationsResult)` in both `messages.py` registries
  (main `messages.py:41`).
- **Sandbox-side handler:** `hass_client/sandbox/__init__.py:262-283`
  (`_handle_get_translations`) + `_collect_component_strings` (356-383), reusing
  core's `_async_get_component_strings` to pre-fill `title` from
  `integration.name`.

**Why it matters:** the doc is a source-linked deep reference with dedicated
sections for every other surface (config-flow forwarding, entity bridge,
service/event mirror, store routing, integration source). Translations are now a
peer surface — a main core hook, a new RPC, a config-flow-aware group resolver,
a picker catalog hook — and warrant their own section.

### B. "Where to look in the code" table has no Translations row — HIGH
The table (lines 602-613) maps every concern to HA-core + sandbox files but
omits translations entirely. Missing row, e.g.:
`Translations | translation.py, catalog.py, helpers/translation.py, loader.py |
hass_client/sandbox/__init__.py (_handle_get_translations)`.

### C. Config-flow / entity translation behavior unmentioned — MEDIUM
The "How the sandbox differs from v1" table (lines 42-52) has no translations
row, and the Config-flow section (211-256) never notes that frontend form
labels for a sandboxed custom integration are served via the overlay (without
it they'd silently vanish — the exact gap `translation.py`'s docstring
describes). The picker `title`/name fallback (catalog hook) is likewise
unmentioned.

### D. `ALWAYS_MAIN` "Open follow-ups" only lists `ai_task, image` — LOW
The "Non-idempotent service handlers" follow-up (lines 551-554) and
`sandbox/CLAUDE.md` still frame `ALWAYS_MAIN` as the small `ai_task`/`image`
punt; neither acknowledges the broad-reader lockdown additions now in `const.py`
(ties to Drift #1).

## Verdict

OVERVIEW.md is **substantially accurate** on architecture, lifecycle, transport,
entity bridge (32 proxies), store routing, auth, and config-flow forwarding —
the structural backbone all checks out. But it has **one material routing
error** (the `ALWAYS_MAIN` deny-list is a third of its real size), **two
smaller lifecycle inaccuracies** (failed-setup state is `SETUP_ERROR` not
`SETUP_RETRY`; there is no ping loop at all, not a "disabled" one), and a
**whole-feature gap**: translation forwarding (shipped, fully wired, verified) is
absent from the body, the "differs from v1" table, the config-flow section, and
the "Where to look in the code" table. Must change: rewrite the `ALWAYS_MAIN`
paragraph, fix the SETUP_RETRY/ping claims, and add a Translations section +
table row.
