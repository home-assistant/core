# Connectivity Monitor Test Documentation

This file explains what the tests in `tests/components/connectivity_monitor` are verifying.
It is written as a plain-language guide for readers who are not yet comfortable reading the Python tests directly.

## What This Test Suite Covers

The Connectivity Monitor integration supports several monitored target types:

- Network targets such as ICMP, TCP, UDP, and Active Directory domain controllers
- ZHA devices
- Matter devices
- ESPHome devices
- Bluetooth devices

The tests in this folder verify four main areas:

1. Config flows: creating entries, validating input, and editing/removing configured targets.
2. Integration lifecycle: setup, unload, and migration from older config entry formats.
3. Sensor behavior: state, attributes, and icons for each monitored target type.
4. Alert handling: delayed notifications and actions for outages and recoveries.

Most tests mock the real network or device lookups. That keeps the suite deterministic and proves the integration logic without depending on actual devices.

## How To Run These Tests

From the repository root, you can run just this integration's test folder with pytest.

If your virtual environment is already activated, a common command is:

```bash
python -m pytest tests/components/connectivity_monitor -q
```

If you want to call the interpreter explicitly, use the Python executable from your Home Assistant development environment. In this workspace that is commonly:

```bash
/home/vscode/.local/ha-venv/bin/python -m pytest tests/components/connectivity_monitor -q
```

If your checkout uses a local `.venv`, the equivalent command would be:

```bash
/workspaces/homeassistant_core/.venv/bin/python -m pytest tests/components/connectivity_monitor -q
```

You can also run a single test file if you only want one part of the suite:

```bash
python -m pytest tests/components/connectivity_monitor/test_config_flow.py -q
python -m pytest tests/components/connectivity_monitor/test_init.py -q
python -m pytest tests/components/connectivity_monitor/test_sensor.py -q
```

## What Successful Output Looks Like

For a passing run, pytest usually prints a row of dots, then a final summary with the number of passed tests. The exact number of dots, runtime, and plugin lines can vary by environment.

Example:

```text
 tests/components/connectivity_monitor/test_config_flow.py ✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓                               52% █████▎
 tests/components/connectivity_monitor/test_init.py ✓✓                                                                           55% █████▌
 tests/components/connectivity_monitor/test_sensor.py ✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓                                        100% ██████████

Results (4.63s):
      75 passed
```

Possible variations are still normal, for example:

- The total passed count may change when tests are added or removed.
- The runtime will vary from machine to machine.
- Home Assistant's pytest setup may print a few extra plugin or warning lines before the summary.
- If something fails, you will see `F` characters in the progress line and then a failure report below the summary header.
- There could be deprecation warnings. Some of them are from the integration self and should be resolved, others could be from Home Assistant self and can't be solved by the integration.

## Shared Fixtures In `conftest.py`

These fixtures are used by multiple test files:

| Fixture | Purpose |
| --- | --- |
| `mock_setup_entry` | Patches the integration setup and unload functions during config flow tests so a successful setup can be assumed without loading the full integration. |
| `network_target` | Returns a simple network device definition: host `192.168.1.1`, protocol `ICMP`, device name `Router`. |
| `network_config_entry` | Builds a version 2 mock config entry for a network monitor using `network_target`, a 30 second interval, and the default DNS server. |

## `test_config_flow.py`

This module verifies that the integration's setup wizard and options flow guide the user through the right steps and store the right data.

### Entry Creation And Validation

| Test | What it proves |
| --- | --- |
| `test_user_step_shows_device_type_selector` | The first user-facing step opens correctly and lets the user choose what kind of device they want to monitor. |
| `test_network_flow_create_first_entry` | A first network monitor can be created through the `user -> network -> dns -> interval` flow, and the saved entry includes alert defaults. |
| `test_network_flow_tcp_includes_port_step` | TCP monitoring requires a separate port step before DNS and interval configuration, and the chosen port is stored. |
| `test_network_flow_udp_includes_port_step` | UDP monitoring follows the same extra port step and stores the UDP port correctly. |
| `test_network_flow_active_directory_expands_targets` | Choosing the Active Directory domain controller option expands one logical device into eight TCP targets, one for each required AD DC port. |
| `test_network_flow_invalid_dns_server` | Invalid DNS server input keeps the flow on the DNS step and shows the `invalid_dns_server` error. |
| `test_network_flow_updates_existing_typed_entry` | If the network typed entry already exists, adding another network device appends a new target to that entry and reloads it instead of creating a second network entry. |

### Discovery Flows With No Or Already-Added Devices

| Test | What it proves |
| --- | --- |
| `test_zha_flow_without_available_devices` | The ZHA flow shows the ZHA device selection step but reports `no_zha_devices` when discovery finds none. |
| `test_shared_device_flow_without_available_devices` | The Matter, ESPHome, and Bluetooth flows each show the correct selection step and the correct `no_*_devices` error when discovery returns nothing. |
| `test_shared_device_flow_when_all_devices_already_added` | ZHA, Matter, ESPHome, and Bluetooth flows detect when every discovered device is already configured and report `all_*_devices_added` instead of offering duplicates. |
| `test_import_flow_aborts_when_typed_entry_exists` | Automatic import during migration aborts with `already_configured` if the typed entry for that protocol already exists. |

### Creating Typed Entries For Non-Network Devices

| Test | What it proves |
| --- | --- |
| `test_matter_flow_create_first_typed_entry` | The first Matter entry is created from discovered device metadata, stores alert defaults, then collects DNS and interval settings. |
| `test_zha_flow_create_first_entry` | The first ZHA entry is created from a selected discovered device and stores its IEEE address, inactive timeout, and optional metadata. |
| `test_esphome_flow_create_first_entry` | The first ESPHome entry stores the selected device ID plus discovered metadata such as model, manufacturer, identifier, and MAC address. |
| `test_bluetooth_flow_create_first_entry` | The first Bluetooth entry stores the selected Bluetooth address and discovered metadata such as model and manufacturer. |

### Updating Existing Typed Entries With Additional Devices

| Test | What it proves |
| --- | --- |
| `test_zha_flow_updates_existing_typed_entry` | Adding a second ZHA device appends it to the existing ZigBee Monitor entry, preserves the original target, and reloads the entry. |
| `test_esphome_flow_updates_existing_typed_entry` | Adding a second ESPHome device appends the new device to the existing ESPHome Monitor entry and preserves discovered metadata. |
| `test_bluetooth_flow_updates_existing_typed_entry` | Adding a second Bluetooth device appends it to the existing Bluetooth Monitor entry and preserves discovered metadata. |

### Options Flow: General Settings And Network Device Management

| Test | What it proves |
| --- | --- |
| `test_options_flow_shows_network_menu` | Opening options for a network entry lands on the expected menu step. |
| `test_options_flow_updates_general_settings` | The options flow can update shared settings such as polling interval and DNS server, then reload the entry. |
| `test_options_flow_updates_network_alert_settings` | Alert settings edited for a network device are applied to all targets belonging to that same host, not just one target. |
| `test_options_flow_rename_network_device` | Changing a network device's host and device name updates stored targets and removes the old device registry entry. |
| `test_options_flow_rejects_blank_rename_host` | Blank host values are rejected during rename and the flow stays on the rename step with an `invalid_host` error. |
| `test_options_flow_remove_network_device` | Removing a network device deletes all targets for that host and removes its device registry entry. |
| `test_options_flow_remove_single_sensor` | Removing one network sensor deletes only that one target and removes the matching entity registry entry. |
| `test_options_flow_cleanup_orphaned_devices` | Cleanup removes device registry entries that no longer have any entities while preserving still-linked devices. |

### Options Flow: Protocol-Specific Alert Editing And Removal

| Test | What it proves |
| --- | --- |
| `test_options_flow_updates_protocol_specific_alert_settings` | ZHA, Matter, ESPHome, and Bluetooth entries each have protocol-specific alert configuration paths that update alert settings correctly. |
| `test_options_flow_removes_protocol_specific_device` | ZHA, Matter, ESPHome, and Bluetooth entries can remove a monitored device through protocol-specific options flow steps, and the matching entity registry entry is deleted. |

## `test_init.py`

This module focuses on integration lifecycle behavior.

| Test | What it proves |
| --- | --- |
| `test_load_unload_entry` | A normal network config entry sets up successfully, creates sensor entities, cleans up the alert handler on unload, and removes integration runtime data from `hass.data`. |
| `test_migrate_entry_splits_legacy_targets` | A legacy version 1 mixed entry is migrated into version 2 by keeping network targets in the network entry and importing separate typed entries for ZHA, Matter, ESPHome, and Bluetooth targets. |

## `test_sensor.py`

This module verifies the runtime sensor entities, their attributes, state transitions, overview behavior, and alert timing.

### Network Sensor State And Coordinator Behavior

| Test | What it proves |
| --- | --- |
| `test_network_sensors_expose_expected_state` | A simple ICMP network target creates both a target sensor and an overview sensor with the expected state, latency, address attributes, and icons. |
| `test_coordinator_refresh_uses_default_data_on_failure` | If a later refresh raises an exception, the coordinator falls back to default disconnected data instead of leaving stale connected data in place. |
| `test_overview_sensor_shows_partially_connected` | A normal overview sensor reports `Partially Connected` when one target for a device is up and another is down. |

### Protocol-Specific Sensor State

| Test | What it proves |
| --- | --- |
| `test_zha_sensor_exposes_expected_state_and_attributes` | A ZHA sensor reports `Active` for a recently seen device and exposes the expected IEEE, timeout, last-seen, and icon attributes. |
| `test_protocol_specific_sensors_expose_expected_state` | Matter, ESPHome, and Bluetooth sensors each expose the expected active state, identifier attribute, monitor type, and icon. The Bluetooth variant also verifies RSSI, source, and connectable attributes. |
| `test_protocol_specific_sensors_show_unknown_when_device_missing` | ZHA, Matter, ESPHome, and Bluetooth sensors all fall back to `Unknown` when no usable device data is available from the coordinator or helper lookup. |

### Network Alert Handling

| Test | What it proves |
| --- | --- |
| `test_alert_handler_triggers_notification_and_action_after_delays` | For a network overview sensor, notification and automation action are triggered only after their separate configured outage delays have elapsed. |
| `test_alert_handler_sends_recovery_after_confirmed_reconnect` | After an outage has been reported, a recovery notification and recovery action are emitted only after the device stays connected long enough to count as recovered. |
| `test_alert_handler_cancels_recovery_when_device_flaps` | A short reconnect that quickly drops again does not incorrectly produce recovery side effects. |
| `test_alert_handler_does_not_repeat_notification_or_action` | Repeated timer ticks after an outage has already been reported do not send duplicate notifications or action events. |
| `test_alert_handler_handles_startup_offline_entity` | Devices that are already offline during startup still begin their alert delay countdown correctly and eventually notify. |

### ZHA Inactivity And Timeout Rules

| Test | What it proves |
| --- | --- |
| `test_zha_sensor_shows_inactive_when_last_seen_exceeds_timeout` | A ZHA sensor becomes `Inactive` when the device's last-seen timestamp is older than the configured inactive timeout. |
| `test_zha_sensor_shows_inactive_when_device_not_found_in_zha` | If the ZHA helper cannot find the device at all, the sensor still reports `Inactive`, but without `last_seen` or `minutes_ago` attributes. |
| `test_zha_sensor_shows_unknown_when_coordinator_has_no_data` | If the ZHA coordinator returns no data for the target, the sensor reports `Unknown`. |

### Alert Handling For ZHA, Matter, ESPHome, And Bluetooth

These tests reuse a parametrized matrix so the same alert rules are verified for each non-network protocol.

| Test | What it proves |
| --- | --- |
| `test_protocol_alert_triggers_notification_and_action_after_delays` | ZHA, Matter, ESPHome, and Bluetooth sensors each trigger notification and action only after the configured inactive/offline delays have passed. |
| `test_protocol_alert_sends_recovery_after_confirmed_reactivation` | ZHA, Matter, ESPHome, and Bluetooth sensors each send recovery side effects only after the device stays active long enough to confirm recovery. |
| `test_protocol_alert_does_not_repeat_notification_or_action` | ZHA, Matter, ESPHome, and Bluetooth sensors do not repeatedly fire duplicate side effects on later timer ticks. |

### Active Directory Overview Behavior

| Test | What it proves |
| --- | --- |
| `test_ad_overview_sensor_shows_connected_when_all_ports_up` | The special AD overview sensor reports `Connected` when every required domain controller port is reachable. |
| `test_ad_overview_sensor_shows_partially_connected_when_some_ports_down` | The AD overview sensor reports `Partially Connected` when only some required AD ports are reachable. |
| `test_ad_overview_sensor_shows_not_connected_when_all_ports_down` | The AD overview sensor reports `Not Connected` when none of the required AD ports are reachable. |

## Reading Pattern Used By Most Tests

Most tests here follow the same shape:

1. Build a fake Home Assistant config entry or start a config flow.
2. Patch low-level functions such as network probes or discovery helpers.
3. Call the integration code under test.
4. Assert on the resulting flow step, stored config data, entity state, emitted events, or registry changes.

That means you can usually read each test as: "given this setup, when the integration does this, then these outcomes must be true."