---
name: ha-integration-knowledge
description: Everything you need to know to build, test and review Home Assistant Integrations. If you're looking at an integration, you must use this as your primary reference.
---

## File Locations
- **Integration code**: `./homeassistant/components/<integration_domain>/`
- **Integration tests**: `./tests/components/<integration_domain>/`

## General guidelines

- When looking for examples, prefer integrations with the Platinum or Gold quality scale level first — that tier only certifies the specific rules tracked below, not every design choice in the code, so still judge whether a pattern makes sense on its own merits rather than copying it on tier alone.
- Polling intervals are NOT user-configurable. Never add scan_interval, update_interval, or polling frequency options to config flows or config entries.
- Do NOT allow users to set config entry names in config flows. Names are automatically generated or can be customized later in UI. Exceptions: helper integrations may allow custom names, and subentry flows may legitimately ask for one (e.g. naming a conversation-agent subentry). Most other `CONF_NAME` fields still found in config flows — even ones with an approving review comment attached, like local_file's — are grandfathered legacy code, not sanctioned examples to copy; a path- or URL-based source that needs to tell multiple instances apart should auto-derive a distinguishing title from the configured value instead (as the `file` and `generic` integrations do) — check that the derived title actually captures what makes two entries distinct, since deriving from only part of the value (e.g. a URL's host, not its full path) can still leave genuinely different sources with the same title.
- For entity actions and entity services, avoid requesting redundant defensive checks for fields already enforced by Home Assistant validation schemas and entity filters; only request extra guards when values bypass validation or are transformed unsafely.
- When validation guarantees a key is present, prefer direct dictionary indexing (`data["key"]`) over `.get("key")` so invalid assumptions fail fast.
- Integrations should be thin wrappers. Protocol parsing, device state machines, or other domain logic belong in a separate PyPI library, not in the integration itself. If unsure, ask before inlining.
- Integrations should not patch around bugs or limitations in a library's own behavior — fix the library instead. Logic that only exists because of Home Assistant's own lifecycle (for example, handing an authenticated session off from `async_migrate_entry` to `async_setup_entry` to avoid a duplicate login) is integration-specific glue, not a library workaround.
- Keep each pull request to a single change; add reauth, reconfigure, diagnostics, repairs, and extra platforms in follow-up PRs, and bump dependencies separately.
- Be batteries-included: set everything up and let users disable what they don't want; don't make them choose which accounts or devices to add — except an open-ended result set from a query (e.g. every station within a search radius) genuinely needs a picker, unlike a finite set of accounts or devices behind one hub.
- Guidance below tagged with a quality-scale tier (for example "(Silver: `parallel-updates`)") is required from that tier upward. Before applying or flagging it, check the integration's target tier (`quality_scale` in `manifest.json`) and its `quality_scale.yaml` for documented exemptions — see "Integration Quality Scale" below. For integrations below that tier, treat it as a suggestion, not a requirement.

The following platforms have extra guidelines:
- **Diagnostics**: [`platform-diagnostics.md`](platform-diagnostics.md) for diagnostic data collection
- **Repairs**: [`platform-repairs.md`](platform-repairs.md) for user-actionable repair issues

## Entity platforms

- Ensure `async_added_to_hass()` and `async_will_remove_from_hass()` have symmetrical behavior. For example, if a subscription is created in `async_added_to_hass()`, it should be unsubscribed in `async_will_remove_from_hass()`. Also, if something is torn down in `async_will_remove_from_hass()`, it should be set up in `async_added_to_hass()`.
- Register subscriptions and listeners in `async_added_to_hass()` (removed via `async_on_remove()`), not `__init__()`. (Bronze: `entity-event-setup`)
- Entity base class (e.g. `SensorEntity`, `TrackerEntity`) provide a stable API for child classes to inherit from. Do not suggest redeclaring or duplicating attributes, properties, or methods the base class already provides, and do not add guards against the parent's behavior changing — rely on the base class instead.
- Give every entity a stable `unique_id` from a persistent identifier the device or service provides (serial, account/installation id, or a MAC via `format_mac()`), combined with a per-entity key when one identifier backs multiple entities (for example `f"{serial}_{description.key}"`); the config entry id is a valid last-resort fallback when no such identifier exists. Never derive it from a user-entered value (host, IP, username), a client-side enumeration index (list position), or the entity name — a port or zone number counts as a persistent identifier like a serial when the device's own protocol addresses that item by it (in commands, not just incidentally in one response), not when it's merely the position of that item within a list the client happened to receive. (Bronze: `entity-unique-id`)
- Set `_attr_has_entity_name = True`, and omit `translation_key` when a `device_class` already names the entity uniquely — keep it when multiple entities on the same device share that `device_class` and need disambiguating. (Bronze: `has-entity-name`)
- Set `PARALLEL_UPDATES` explicitly in every entity platform file: `0` when there is no need to limit concurrent calls (always true for a read-only platform, coordinator- or push-based; for an action platform, only when nothing about the backend needs that protection), a bounded value (typically `1`) otherwise. (Silver: `parallel-updates`)
- Prefer separate entities (disabled by default if noisy) over `extra_state_attributes`.

## Setup and coordinators

- Create the client in `async_setup_entry()` and store it on the typed `entry.runtime_data`, not `hass.data`. A push-only integration (webhook, subscription) with nothing to hold between calls can legitimately have no coordinator or runtime data at all. (Bronze: `runtime-data`)
- If the integration has shared polled data, use a `DataUpdateCoordinator` in `coordinator.py` and type its `config_entry` when it belongs to one — a coordinator backing something broader than a single entry (e.g. a shared dashboard connection) legitimately has none.
- Put a shared base entity in `entity.py` once more than one platform needs it; a single-platform integration can define its entity class directly in that platform file. (Bronze: `common-modules`)
- After an action, update entity state through the coordinator rather than writing it directly: request a refresh, push the new value with the coordinator's own `async_set_updated_data()`, or rely on an already-active push-based coordinator to pick it up. If none of those fit, set optimistic state only after the command succeeds.

## Errors

- During setup, raise `ConfigEntryNotReady` for transient failures (offline device, timeout) and `ConfigEntryError` for other non-retryable ones. (Bronze: `test-before-setup`)
- During setup or a coordinator update, raise `ConfigEntryAuthFailed` whenever reauthenticating would actually restore access (invalid credentials, a revoked or insufficient scope) — it starts a reauthentication flow. An account limitation that reauth can't fix (an expired subscription, quota exceeded) should be a repair issue instead.
- In an action, `ConfigEntryAuthFailed` reaching the service-call dispatcher does not start reauth on its own: call `entry.async_start_reauth_if_available(hass)` (or `async_start_reauth()`) explicitly, then raise a translated `HomeAssistantError`.
- In actions, raise `ServiceValidationError` for user errors and `HomeAssistantError` for device errors. (Silver: `action-exceptions`)
- Don't put raw or stringified library exceptions into user-facing translated messages; use exception translation keys and chain the original exception (`raise ... from err`) instead of logging it separately. (Gold: `exception-translations`)

## Config flow

- Validate the connection before creating the entry. Exempt: nothing to test at all (webhook-based, helpers), or the connection was already exercised earlier in the same flow — during automatic discovery, for example — making a second validation at entry-creation redundant. (Bronze: `test-before-configure`)
- Use typed selectors (`TextSelector`, `NumberSelector`, `SelectSelector`, `BooleanSelector`, etc.) for the form schema, and `add_suggested_values_to_schema()` to prefill a form that has values to suggest — it has nothing to do on a form with no defaults to prefill.
- Set a `unique_id` when a stable identifier exists and guard duplicates with `_abort_if_unique_id_configured()` (check for a mismatch on reconfigure or reauth). Without a stable identifier, guard duplicates with `_async_abort_entries_match()` instead — don't invent a unique id. The two can also be combined: `_async_abort_entries_match()` as an early, pre-probe check before a stable identifier is known, alongside `_abort_if_unique_id_configured()` once it is, to also catch entries added before the integration supported unique ids. (Bronze: `unique-config-entry`)

## Translations

- Keep user-facing text in `strings.json`, in Sentence case (third person for action descriptions). Reuse shared strings via `[%key:common::...%]`, and translate + `snake_case` enum options instead of hardcoding display text. These conventions apply regardless of tier; translating the entity name itself is the Gold-tier `entity-translations` rule specifically.

## Integration Quality Scale

- When validating the quality scale rules, check them at https://developers.home-assistant.io/docs/core/integration-quality-scale/rules
- When implementing or reviewing an integration, always consider the quality scale rules, since they promote best practices.

Template scale file: `./script/scaffold/templates/integration/integration/quality_scale.yaml`

### How Rules Apply
1. **Check `manifest.json`**: Look for `"quality_scale"` key to determine integration level
2. **Bronze Rules**: Always required (must be `done` or `exempt`) for any integration with quality scale
3. **Higher Tier Rules**: Every rule at every tier must still be listed in `quality_scale.yaml` (`todo` is fine below the target tier) — only enforcement (must be `done` or `exempt`) is gated by the integration's target tier
4. **Rule Status**: Check `quality_scale.yaml` in integration folder for:
   - `done`: Rule implemented
   - `exempt`: Rule doesn't apply (with reason in comment)
   - `todo`: Rule needs implementation


## Testing Requirements

- Tests should avoid interacting or mocking internal integration details. For more info, see https://developers.home-assistant.io/docs/development_testing/#writing-tests-for-integrations
- Test through the public surface: set the integration up via `hass` and assert entity state and the entity/device registries (`snapshot_platform` preferred); entity/platform tests should not reach into the coordinator or `runtime_data` directly, except calling `coordinator.async_refresh()` to force an immediate, deterministic update. A dedicated `test_coordinator.py` calling the coordinator's own methods directly, including private ones, to test its update/error logic is a separate, accepted pattern.
- For polling integrations, prefer driving updates with `freezer` + `async_fire_time_changed` when testing polling-interval behavior itself; push integrations (webhook, subscription) must instead exercise their real update path (e.g. posting to the webhook), since time advancement doesn't trigger those.
- Patch the third-party library, not integration internals, and put shared fixtures in `conftest.py`. A config-flow test should end in `CREATE_ENTRY`, `ABORT`, or a `FORM` that asserts a specific persistent error, unless it's deliberately scoped to one intermediate transition and leaves completion to another test in the file (for example, a test that verifies a discovery flow falls back to manual entry after a timeout). Assert the `unique_id` when the flow assigns one (some integrations are legitimately exempt from `unique-config-entry`). (Bronze: `config-flow-test-coverage`)
