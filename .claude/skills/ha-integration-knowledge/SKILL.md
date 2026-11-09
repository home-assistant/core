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
- Do not add entities for data that Home Assistant intentionally only exposes through an action, for example weather forecasts (`weather.get_forecasts`).
- In config flows, map known failures to the matching standard error (for example `invalid_auth`, `cannot_connect`) without logging them. If unexpected exceptions are caught, log them with `_LOGGER.exception()` and map them to `unknown`. Do not mix translated and untranslated text in an error shown to the user.
- Bump dependencies in a standalone PR that contains only the compatibility adjustments the bump requires. Features that need the new version go in a follow-up PR.

The following platforms have extra guidelines:
- **Device tracker**: [`platform-device-tracker.md`](platform-device-tracker.md) for replacing legacy device trackers
- **Diagnostics**: [`platform-diagnostics.md`](platform-diagnostics.md) for diagnostic data collection
- **Repairs**: [`platform-repairs.md`](platform-repairs.md) for user-actionable repair issues

## Entity platforms

- Ensure `async_added_to_hass()` and `async_will_remove_from_hass()` have symmetrical behavior. For example, if a subscription is created in `async_added_to_hass()`, it should be unsubscribed in `async_will_remove_from_hass()`. Also, if something is torn down in `async_will_remove_from_hass()`, it should be set up in `async_added_to_hass()`.
- Use `_attr_*` attributes instead of properties for values that never change. Define them as class attributes only when the value is shared by all instances.
- When overriding `available`, combine it with the parent's value (`return super().available and ...`).
- Entity base class (e.g. `SensorEntity`, `TrackerEntity`) provide a stable API for child classes to inherit from. Do not suggest redeclaring or duplicating attributes, properties, or methods the base class already provides, and do not add guards against the parent's behavior changing — rely on the base class instead.

## Actions

- Action names and action fields are defined in `<Prefix>Service` and `<Prefix>ServiceArgument` `StrEnum`s, using the integration's usual class prefix (for example `TadoService`, `AITaskServiceArgument`). Integrations define them in `services.py`, or in `const.py` when other modules need them; entity platforms define them in `const.py` and export them.
- The members cover the registered actions and their fields as listed in `services.yaml`. Do not add members for actions that are not registered, such as stale `services.yaml` entries or description templates for legacy per-platform actions.
- Use the members for action registration, schema keys and `call.data` lookups instead of raw strings or other string constants (whatever their prefix, for example `SERVICE_*`, `ATTR_*` or `CONF_*`). Shared selector fields such as `config_entry_id`, `device_id` and `entity_id` keep using the `homeassistant.const` constants.
- Only request these enums, as a blocking change, when a PR adds an integration's first actions (a new `services.yaml`). Do not flag or suggest them for an integration that already has actions.

## Integration Quality Scale

- When validating the quality scale rules, check them at https://contributors.home-assistant.io/core/quality-scale/rules/
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

- Tests should avoid interacting or mocking internal integration details. For more info, see https://contributors.home-assistant.io/core/development/tests/#test-through-home-assistant
- Define shared mocks as fixtures in `conftest.py` so every platform test can reuse them, including a `mock_config_entry`. Give it a `unique_id` when the integration's config entries have one.
- Load substantial or reused mock API data from JSON fixture files with `load_json_object_fixture` or `load_json_array_fixture` from `pytest_homeassistant.common` (or their `async_` variants) instead of building it inline with `json.dumps()`.
- Do not manually assert values that a snapshot test already covers.
- When a `Platform` member or an `ATTR_*` constant exists for a value, use it instead of a string literal.
- Patch objects where they are used, not where they are defined.
- To give one test different mock data, parametrize the fixture that provides it with `pytest.mark.parametrize` instead of patching again inside the test. Use `indirect=True` when the fixture reads the value from `request.param`.
