---
name: ha-integration-knowledge
description: Everything you need to know to build, test and review Home Assistant Integrations. If you're looking at an integration, you must use this as your primary reference.
---

## File Locations
- **Integration code**: `./homeassistant/components/<integration_domain>/`
- **Integration tests**: `./tests/components/<integration_domain>/`

## General guidelines

- When looking for examples, prefer integrations with the platinum or gold quality scale level first.
- Polling intervals are NOT user-configurable. Never add scan_interval, update_interval, or polling frequency options to config flows or config entries.
- Do NOT allow users to set config entry names in config flows. Names are automatically generated or can be customized later in UI. Exception: helper integrations may allow custom names.
- For entity actions and entity services, avoid requesting redundant defensive checks for fields already enforced by Home Assistant validation schemas and entity filters; only request extra guards when values bypass validation or are transformed unsafely.
- When validation guarantees a key is present, prefer direct dictionary indexing (`data["key"]`) over `.get("key")` so invalid assumptions fail fast.
- Integrations should be thin wrappers. Protocol parsing, device state machines, or other domain logic belong in a separate PyPI library, not in the integration itself. If unsure, ask before inlining.
- Integrations should not implement fixes or workarounds for limitations in libraries. Instead, the library should be updated to fix the issue.
- Keep each pull request to a single change; add reauth, reconfigure, diagnostics, repairs, and extra platforms in follow-up PRs, and bump dependencies separately.
- Be batteries-included: set everything up and let users disable what they don't want; don't make them choose which accounts or devices to add.
- Guidance below tagged with a quality-scale tier (for example "(Silver: `parallel-updates`)") is required from that tier upward. Before applying or flagging it, check the integration's target tier (`quality_scale` in `manifest.json`) and its `quality_scale.yaml` for documented exemptions — see "Integration Quality Scale" below. For integrations below that tier, treat it as a suggestion, not a requirement.

The following platforms have extra guidelines:
- **Diagnostics**: [`platform-diagnostics.md`](platform-diagnostics.md) for diagnostic data collection
- **Repairs**: [`platform-repairs.md`](platform-repairs.md) for user-actionable repair issues

## Entity platforms

- Ensure `async_added_to_hass()` and `async_will_remove_from_hass()` have symmetrical behavior. For example, if a subscription is created in `async_added_to_hass()`, it should be unsubscribed in `async_will_remove_from_hass()`. Also, if something is torn down in `async_will_remove_from_hass()`, it should be set up in `async_added_to_hass()`.
- Register subscriptions and listeners in `async_added_to_hass()` (removed via `async_on_remove()`), not `__init__()`. (Bronze: `entity-event-setup`)
- Entity base class (e.g. `SensorEntity`, `TrackerEntity`) provide a stable API for child classes to inherit from. Do not suggest redeclaring or duplicating attributes, properties, or methods the base class already provides, and do not add guards against the parent's behavior changing — rely on the base class instead.
- Give every entity a stable `unique_id` from a persistent identifier the device or service provides (serial, account/installation id, or a MAC via `format_mac()`), combined with a per-entity key when one identifier backs multiple entities (for example `f"{serial}_{description.key}"`); the config entry id is a valid last-resort fallback when no such identifier exists. Never derive it from a user-entered value (host, IP, username), an index, or the entity name. (Bronze: `entity-unique-id`)
- Set `_attr_has_entity_name = True`, and omit `translation_key` when a `device_class` already names the entity. (Bronze: `has-entity-name`)
- Set `PARALLEL_UPDATES` explicitly in every entity platform file: `0` for read-only platforms of coordinator-based integrations, a bounded value (typically `1`) where actions call the device. (Silver: `parallel-updates`)
- Prefer separate entities (disabled by default if noisy) over `extra_state_attributes`.

## Setup and coordinators

- Create the client in `async_setup_entry()` and store it on the typed `entry.runtime_data`, not `hass.data`. If the integration has shared polled data, use a `DataUpdateCoordinator` in `coordinator.py` with a shared base entity in `entity.py`, and type the coordinator's `config_entry`; a push-only integration (webhook, subscription) can legitimately have no coordinator or runtime data at all. (Bronze: `runtime-data`, `common-modules`)
- After an action, request a coordinator refresh instead of writing entity state manually — or set optimistic state only after the command succeeds.

## Errors

- During setup, raise `ConfigEntryNotReady` for transient failures (offline device, timeout), `ConfigEntryAuthFailed` only for invalid credentials (it starts a reauthentication flow), and `ConfigEntryError` for other non-retryable failures. In actions, raise `ServiceValidationError` for user errors and `HomeAssistantError` for device errors. (Bronze: `test-before-setup`; Silver: `action-exceptions`)
- Don't put raw or stringified library exceptions into user-facing translated messages; use exception translation keys and chain the original exception (`raise ... from err`) instead of logging it separately. (Gold: `exception-translations`)

## Config flow

- Validate the connection before creating the entry (integrations with nothing to test — webhook-based, helpers, runtime auto-discovery — are exempt). (Bronze: `test-before-configure`)
- Use `TextSelector` / `NumberSelector` / `SelectSelector` and `add_suggested_values_to_schema()` for the form schema.
- Set a `unique_id` when a stable identifier exists and guard duplicates with `_abort_if_unique_id_configured()` (check for a mismatch on reconfigure or reauth); without a stable identifier, guard duplicates with `_async_abort_entries_match()` instead — don't invent a unique id. (Bronze: `unique-config-entry`)

## Translations

- Keep user-facing text in `strings.json`, in Sentence case (third person for action descriptions). Reuse shared strings via `[%key:common::...%]`, and translate + `snake_case` enum options instead of hardcoding display text. (translated entity/enum naming — Gold: `entity-translations`; the style conventions apply generally)

## Integration Quality Scale

- When validating the quality scale rules, check them at https://developers.home-assistant.io/docs/core/integration-quality-scale/rules
- When implementing or reviewing an integration, always consider the quality scale rules, since they promote best practices.

Template scale file: `./script/scaffold/templates/integration/integration/quality_scale.yaml`

### How Rules Apply
1. **Check `manifest.json`**: Look for `"quality_scale"` key to determine integration level
2. **Bronze Rules**: Always required for any integration with quality scale
3. **Higher Tier Rules**: Only apply if integration targets that tier or higher
4. **Rule Status**: Check `quality_scale.yaml` in integration folder for:
   - `done`: Rule implemented
   - `exempt`: Rule doesn't apply (with reason in comment)
   - `todo`: Rule needs implementation


## Testing Requirements

- Tests should avoid interacting or mocking internal integration details. For more info, see https://developers.home-assistant.io/docs/development_testing/#writing-tests-for-integrations
- Test through the public surface: set the integration up via `hass` and assert entity state and the entity/device registries (`snapshot_platform` preferred). Do not call the coordinator, dispatcher, or `runtime_data` directly. For polling integrations, drive updates with `freezer` + `async_fire_time_changed`; push integrations (webhook, subscription) must instead exercise their real update path (e.g. posting to the webhook), since time advancement doesn't trigger those.
- Patch the third-party library, not integration internals, and put shared fixtures in `conftest.py`. Every config-flow test must end in `CREATE_ENTRY` or `ABORT`, and assert the `unique_id` when the flow assigns one (some integrations are legitimately exempt from `unique-config-entry`). (Bronze: `config-flow-test-coverage`)
