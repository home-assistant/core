---
name: ha-integration-knowledge
description: Everything you need to know to build, test and review Home Assistant Integrations. If you're looking at an integration, you must use this as your primary reference.
---

## File Locations
- **Integration code**: `./homeassistant/components/<integration_domain>/`
- **Integration tests**: `./tests/components/<integration_domain>/`

## General guidelines

- When looking for examples, prefer integrations with the platinum or gold quality scale level first, but judge each pattern on its own: the level means the quality scale rules are met, not that every design choice is worth copying.
- Polling intervals are NOT user-configurable. Never add scan_interval, update_interval, or polling frequency options to config flows or config entries.
- Do NOT allow users to set config entry names in config flows. Names are automatically generated or can be customized later in UI. Exceptions: helper integrations may allow custom names, and a subentry flow may ask for one.
- In a reauth or reconfigure flow, guard the unique ID with `_abort_if_unique_id_mismatch()`, which compares against the entry being changed. `_abort_if_unique_id_configured()` stays right in the user flow.
- For entity actions and entity services, avoid requesting redundant defensive checks for fields already enforced by Home Assistant validation schemas and entity filters; only request extra guards when values bypass validation or are transformed unsafely.
- When validation guarantees a key is present, prefer direct dictionary indexing (`data["key"]`) over `.get("key")` so invalid assumptions fail fast.
- Integrations should be thin wrappers. Protocol parsing, device state machines, or other domain logic belong in a separate PyPI library, not in the integration itself. If unsure, ask before inlining.
- Integrations should not implement fixes or workarounds for limitations in libraries. Instead, the library should be updated to fix the issue. Code that exists only because of how Home Assistant models the device, or because of its setup, migration and unload lifecycle, is not a library workaround.

The following platforms have extra guidelines:
- **Diagnostics**: [`platform-diagnostics.md`](platform-diagnostics.md) for diagnostic data collection
- **Repairs**: [`platform-repairs.md`](platform-repairs.md) for user-actionable repair issues

## Entity platforms

- Ensure `async_added_to_hass()` and `async_will_remove_from_hass()` have symmetrical behavior. For example, if a subscription is created in `async_added_to_hass()`, it should be unsubscribed in `async_will_remove_from_hass()`. Also, if something is torn down in `async_will_remove_from_hass()`, it should be set up in `async_added_to_hass()`.
- Entity base class (e.g. `SensorEntity`, `TrackerEntity`) provide a stable API for child classes to inherit from. Do not suggest redeclaring or duplicating attributes, properties, or methods the base class already provides, and do not add guards against the parent's behavior changing — rely on the base class instead.
- Prefer separate entities (disabled by default if noisy) over `extra_state_attributes`.

## Errors

- Raising `ConfigEntryAuthFailed` from an action does not start a reauth flow; only setup and coordinator refreshes act on it. Call `entry.async_start_reauth(hass)` yourself, or `async_start_reauth_if_available()` where the integration may have no reauth step, and raise a `HomeAssistantError`.
- Reauth cannot fix an account limitation. In a coordinator update, raise `UpdateFailed` for a temporary one, such as a rate limit or a quota that resets on its own; a lasting one the user can act on, such as an expired subscription, belongs in a repair issue.

## Integration Quality Scale

- When validating the quality scale rules, check them at https://developers.home-assistant.io/docs/core/integration-quality-scale/rules
- When implementing or reviewing an integration, always consider the quality scale rules, since they promote best practices.

Template scale file: `./script/scaffold/templates/integration/integration/quality_scale.yaml`

### How Rules Apply
1. **Check `manifest.json`**: Look for `"quality_scale"` key to determine integration level
2. **Bronze Rules**: Required (`done` or `exempt`) as soon as `quality_scale` names a tier: `bronze`, `silver`, `gold` or `platinum`. Any other accepted value (`legacy`, `internal`, `no_score`, `custom`) is not a tier, so don't require the rules of that code
3. **Higher Tier Rules**: Only apply if integration targets that tier or higher
4. **Rule Status**: Check `quality_scale.yaml` in integration folder for:
   - `done`: Rule implemented
   - `exempt`: Rule doesn't apply (with reason in comment)
   - `todo`: Rule needs implementation


## Testing Requirements

- Tests should avoid interacting or mocking internal integration details. For more info, see https://developers.home-assistant.io/docs/development_testing/#writing-tests-for-integrations
