# EnOcean Integration Quality Scale Checklist

## Bronze

| Rule | Status | Notes |
|------|--------|-------|
| [action-setup](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-setup) | ✅ | No custom service actions registered |
| [brands](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/brands) | ❌  | `homeassistant/brands/enocean.json` missing |
| [common-modules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/common-modules) | ✅ | `entity.py` holds shared `EnOceanEntity` base; no coordinator needed (push-based via dispatcher) |
| [config-flow](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow) | ✅ | `config_flow.py` exists; `manifest.json` has `"config_flow": true`; all step/error strings present; `data_description` provided for fields |
| [config-entry-unloading](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-entry-unloading) | ✅ | `async_unload_entry` in `__init__.py` unloads all platforms and stops the gateway |
| [dependency-transparency](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/dependency-transparency) | ✅ | `enocean-async` is on PyPI, Apache 2.0 licence, public GitHub source |
| [docs-high-level-description](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-high-level-description) | ✅ | HA docs describe the EnOcean standard and what the integration does |
| [docs-installation-instructions](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-installation-instructions) | ❌ | HA docs still describe the old YAML-based setup; needs updating for config-flow |
| [docs-removal-instructions](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-removal-instructions) | ❌ | No removal instructions in HA docs; add standard steps (Settings → Devices & Services → EnOcean → Delete) |
| [entity-unique-id](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-unique-id) | ✅ | `EnOceanEntity.__init__` sets `_attr_unique_id = f"{address}.{entity_key}"`; sensors append the observable suffix for uniqueness |
| [has-entity-name](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/has-entity-name) | ✅ | `_attr_has_entity_name = True` set on base; all names come from `_attr_translation_key` entries in `strings.json` |
| [runtime-data](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/runtime-data) | ✅ | `config_entry.runtime_data = gateway` set in `async_setup_entry`; typed alias `EnOceanConfigEntry = ConfigEntry[Gateway]` used throughout |
| [test-before-configure](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/test-before-configure) | ✅ | `validate_enocean_conf` instantiates and starts the `Gateway`; raises `ConnectionError` on failure, shown as `invalid_dongle_path` |
| [unique-config-entry](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/unique-config-entry) | ✅ | `async_set_unique_id` + `_abort_if_unique_id_configured()` in USB flow; `"single_config_entry": true` in `manifest.json` blocks a second user flow |

## Silver

| Rule | Status | Notes |
|------|--------|-------|
| [action-exceptions](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-exceptions) | ✅ | No custom service actions; rule has nothing to enforce |
| [config-flow-test-coverage](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow-test-coverage) | ❌ | `test_options_flow.py` rewritten to match current flow (no name field, imports from `const`); detect-form error path still never populates the `errors` dict so `invalid_dongle_path` is never shown on the detect form |
| [devices](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/devices) | ✅ | Gateway registered as device in `async_setup_entry` with manufacturer/model/serial/sw_version; each EnOcean device entity provides full `DeviceInfo` with `via_device` pointing to the gateway |
| [diagnostics](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/diagnostics) | ❌ | No `diagnostics.py`; implement `async_get_config_entry_diagnostics` returning gateway info and configured devices |
| [discovery](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/discovery) | ✅ | `async_step_usb` in config flow; `manifest.json` has `usb` discovery descriptor |
| [discovery-update-info](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/discovery-update-info) | ✅ | `_abort_if_unique_id_configured(updates={CONF_DEVICE: discovery_info.device})` updates the port when a known dongle is re-plugged at a new path |
| [docs-actions](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-actions) | ✅ | No custom service actions; no action documentation needed |
| [docs-configuration-parameters](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-configuration-parameters) | ❌ | HA docs still describe old YAML parameters; update to cover options-flow fields (device type, device ID, sender ID) |
| [entity-unavailable](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-unavailable) | ❌ | `EnOceanEntity` never sets `_attr_available = False`; entities keep their last state instead of going unavailable when the gateway disconnects |
| [inject-websession](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/inject-websession) | ✅ | Exempt — `enocean_async` uses a local serial/USB connection, not HTTP |
| [log-when-unavailable](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/log-when-unavailable) | ❌ | No logging on gateway disconnect or reconnect; add info-level log when availability changes |
| [parallel-updates](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/parallel-updates) | ✅ | `PARALLEL_UPDATES = 0` on `binary_sensor`, `event`, `sensor`; `PARALLEL_UPDATES = 1` on `button`, `cover`, `light`, `number`, `select`, `switch` |
| [reauthentication-flow](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reauthentication-flow) | ✅ | Exempt — local serial connection has no credentials to re-authenticate |
| [reconfiguration-flow](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reconfiguration-flow) | ❌ | No `async_step_reconfigure`; users cannot change the serial port without removing and re-adding the integration |
| [stale-devices](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/stale-devices) | ✅ | `async_cleanup_device_registry` in `__init__.py` removes device registry entries for EnOcean devices no longer present in the config options |
| [test-coverage](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/test-coverage) | ❌ | Zero test coverage for: `binary_sensor`, `sensor`, `switch`, `light`, `cover`, `number`, `select`, `button`, `entity`; existing `test_options_flow.py` is stale |

## Gold

| Rule | Status | Notes |
|------|--------|-------|
| [appropriate-polling](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/appropriate-polling) | ✅ | `iot_class: local_push`; `_attr_should_poll = False`; no `SCAN_INTERVAL`; observations arrive via gateway dispatcher |
| [async-dependency](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/async-dependency) | ✅ | `enocean_async` is asyncio-native; all gateway calls (`start`, `send_command`) are awaited |
| [exception-translations](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/exception-translations) | ❌ | Entity action methods (`async_turn_on`, `async_turn_off`, `async_press`, etc.) make bare `await gateway.send_command(...)` calls with no error handling; wrap failures in `HomeAssistantError` with translation keys and add an `exceptions` section to `strings.json` |
| [icon-translations](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/icon-translations) | ❌ | `icons.json` only has one entry (`sensor.window_handle`); enum sensors with no device class icon need explicit entries: `connection_status`, `cover_state`, `window_state` |
| [integration-owner](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/integration-owner) | ❌ | `"codeowners": []` in `manifest.json`; add at least one GitHub username |
| [repair-issues](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/repair-issues) | ✅ | No conditions in the integration warrant a persistent repair issue |

## Platinum

| Rule | Status | Notes |
|------|--------|-------|
| [strict-typing](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/strict-typing) | ✅ | Integration is listed in `.strict-typing`, uses typed config entries, and `enocean_async` ships a `py.typed` marker confirming PEP 561 compliance |
