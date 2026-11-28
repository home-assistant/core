# Device tracker platform

Platform exists as `homeassistant/components/<domain>/device_tracker.py`.

## Legacy device trackers

Legacy device tracker platforms define `get_scanner`, `async_get_scanner`, `setup_scanner` or `async_setup_scanner`, use `DeviceScanner` or the `DeviceTracker.see` or `DeviceTracker.async_see` callback, and store their devices in `known_devices.yaml`. They are deprecated and will be removed in Home Assistant 2027.5.

- Do not add new legacy device tracker platforms, and do not add features to existing ones.
- When an integration replaces a legacy platform with config entry based `ScannerEntity` or `TrackerEntity` entities, do not migrate the legacy device trackers. Entities from `known_devices.yaml` have no entity registry entry and keep claiming `device_tracker.<dev_id>` until the legacy device tracker is removed. A config entry entity that reuses that entity ID is then dropped at startup or gets an `_2` suffix, and the legacy entity keeps writing stale states.
- In reviews, flag any of these in a legacy to config entry migration:
  - Importing the device tracker YAML configuration with a `SOURCE_IMPORT` flow from the legacy platform setup
  - Reading or editing `known_devices.yaml` (`YAML_DEVICES`, `async_load_config`, `remove_device_from_config`, `load_yaml_config_file`)
  - Reusing legacy entity IDs, for example by setting `self.entity_id` to `device_tracker.<dev_id>`
  - Removing legacy states with `hass.states.async_remove`
  - Enabling entities based on `track` in `known_devices.yaml`
- Instead:
  - Keep the legacy platform working until it is removed.
  - From the legacy platform setup, raise a repair issue with `breaks_in_ha_version="2027.5.0"`. It should give users the same ordered steps as the breaking change section below, not only ask them to remove the platform from `configuration.yaml`. Use an integration specific translation key, because the core `deprecated_yaml` issue says the configuration was imported.
  - Only raise this repair for platforms that have a config entry replacement. If other platforms of the integration are still YAML only, do not ask users to remove those.
- The breaking change section of the PR must list the steps in this order:
  1. Remove the device tracker platform from `configuration.yaml`. While it is set up, it keeps adding devices to `known_devices.yaml`.
  2. Remove the entries of the tracked devices from `known_devices.yaml`, then restart Home Assistant. The legacy entity IDs stay in use until the restart.
  3. Set up the integration from the UI. If the new entities are `ScannerEntity` entities with a MAC address, enable the ones to use. They are disabled by default unless another integration already knows a device with that MAC address.
  4. If needed, change the entity IDs of the new device trackers to the ones used in `known_devices.yaml`.
