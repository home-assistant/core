# Connectivity Monitor Code Guide

This file is a developer-oriented explanation of the Python code in the
`connectivity_monitor` integration. It is meant to help you understand how the
integration is structured inside Home Assistant Core.

This is not the user documentation page for Home Assistant. Think of this file
as internal implementation notes.

## What The Integration Does

Connectivity Monitor creates sensor entities that answer one question:

- Can this target still be reached?

The integration supports several target families:

- Network targets: ICMP, TCP, UDP, Active Directory domain controller checks
- ZigBee targets through ZHA
- Matter targets
- ESPHome targets
- Bluetooth targets

The result is exposed as diagnostic-style sensors such as:

- A sensor per target
- An overview sensor per monitored host
- A special AD overview sensor for domain controller port groups

## High-Level Architecture

The code is split into a few main modules:

- `__init__.py`: integration lifecycle, config entry setup, unload, migration
- `config_flow.py`: UI flow for creating and updating entries
- `coordinator.py`: polling coordinator and runtime-data container
- `sensor.py`: entity creation, alert handling, and sensor classes
- `network.py`: network probing helpers for DNS, TCP, UDP, ICMP, MAC lookup
- `const.py`: constants and protocol names

In short:

1. The config flow builds a typed config entry.
2. `__init__.py` creates runtime objects for that entry.
3. `sensor.py` turns the config entry into entities.
4. `coordinator.py` polls all configured targets on a schedule.
5. The entities read coordinator data and convert it into HA states.
6. `AlertHandler` watches state changes and emits notifications or actions.

## Config Entry Model

Each config entry stores:

- `targets`: a list of target dictionaries
- `interval`: polling interval in seconds
- `dns_server`: DNS server used for hostname resolution

The integration uses typed entries instead of one mixed entry for everything.
Typical entry types are:

- `connectivity_monitor_network`
- `connectivity_monitor_zha`
- `connectivity_monitor_matter`
- `connectivity_monitor_esphome`
- `connectivity_monitor_bluetooth`

This is why the migration logic in `__init__.py` splits older v1 entries into
multiple typed entries.

## Runtime Objects

At setup time, `__init__.py` creates two runtime objects:

- `ConnectivityMonitorCoordinator`
- `AlertHandler`

They are stored in `entry.runtime_data` using the dataclass
`ConnectivityMonitorRuntimeData` from `coordinator.py`.

That means:

- Persistent config lives in `entry.data`
- Runtime-only state lives in `entry.runtime_data`

This is the current Home Assistant pattern and replaces older `hass.data`
storage.

## Setup Flow

The setup path is:

1. `async_setup_entry()` in `__init__.py` creates the coordinator and alert handler.
2. It performs `await coordinator.async_config_entry_first_refresh()`.
3. If that succeeds, runtime data is attached to the entry.
4. The sensor platform is forwarded.
5. `sensor.async_setup_entry()` reads `entry.runtime_data` and creates entities.

The first refresh is important because Home Assistant expects setup to fail early
if the integration cannot initialize correctly.

## Config Flow

`config_flow.py` is responsible for creating or extending typed entries.

Important ideas:

- The first step asks for the device type.
- Each device type has its own branch.
- Network targets may go through `network`, `port`, `dns`, and `interval`.
- Device-backed targets such as ZHA, Matter, ESPHome, and Bluetooth first pick
  a device, then configure alert behavior.

### Test Before Configure

For network targets, the flow now validates connectivity before finishing setup.

That happens in `_async_validate_network_target()`.

It builds a temporary `NetworkProbe` and checks whether the configured target is
actually reachable:

- ICMP tests a ping
- TCP and UDP test the configured port
- Active Directory checks multiple well-known DC ports and accepts success if at
  least one responds

If validation fails, the flow shows `cannot_connect` instead of creating or
updating the config entry.

## Coordinator

`ConnectivityMonitorCoordinator` in `coordinator.py` is the central polling
engine.

Its responsibilities are:

- group all targets for one config entry
- prepare network hosts once per polling cycle
- poll each target using the correct protocol-specific method
- store the latest result payload in `self.data`
- supply fallback payloads when an update fails

### Why `_target_key()` Exists

Coordinator data is stored in a dictionary keyed by a stable string such as:

- `ICMP:192.168.1.1`
- `TCP:192.168.1.1:443`
- `ZHA:00:11:22:33:44:55:66:77`

This lets the entities retrieve the right payload from the shared coordinator.

### Why `_sensor_platform()` Exists

`coordinator.py` lazily imports `sensor.py` through `_sensor_platform()`.

That looks unusual, but it avoids a circular import:

- `sensor.py` needs the coordinator type
- the coordinator sometimes needs helper functions that are re-exported through
  `sensor.py` for test patching compatibility

So the import is delayed until runtime.

## Network Probe

`network.py` contains low-level network checks.

`NetworkProbe` does four main things:

- resolves hostnames using the configured DNS server
- caches resolved IP addresses
- looks up MAC addresses from ARP output
- performs TCP, UDP, or ICMP reachability checks

This separation is useful because the coordinator should orchestrate polling,
not contain socket and DNS details directly.

## Sensor Platform

`sensor.py` contains two kinds of logic:

- entity construction
- alert behavior

### Entity Setup

`sensor.async_setup_entry()`:

- reads all configured targets from `entry.data`
- splits them by protocol family
- creates the right sensor classes
- removes obsolete entities from the entity registry
- removes orphaned devices when targets disappear

### Main Sensor Classes

- `ConnectivitySensor`: one sensor per network target
- `OverviewSensor`: one overall sensor per host
- `ADOverviewSensor`: special grouped view for AD domain controller checks
- `ZHASensor`: ZHA activity sensor
- `MatterSensor`: Matter activity sensor
- `ESPHomeSensor`: ESPHome activity sensor
- `BluetoothSensor`: Bluetooth activity sensor

All of them inherit from `ConnectivityMonitorEntity`, which itself inherits from
`CoordinatorEntity`. This means the entities refresh automatically when the
coordinator updates.

## AlertHandler

`AlertHandler` is the part of the integration that reacts to state changes over
time.

It is separate from the coordinator because polling and alert policy are not the
same problem:

- the coordinator answers "what is the current status?"
- the alert handler answers "has this been bad long enough to notify?"

`AlertHandler` keeps track of:

- when a device first became disconnected or inactive
- whether a notification was already sent
- whether an action was already fired
- short recovery flaps so they do not clear the alert too early

It uses a periodic timer plus entity state listeners to decide when to:

- send a notify call
- fire the `connectivity_monitor_alert` event
- trigger an automation or script configured as an alert action

## Options Flow

The options flow is also inside `config_flow.py`.

It does not create new entries. Instead, it edits the targets already stored in
the entry. It supports actions like:

- rename a monitored host
- modify alert settings
- remove a device
- remove a single sensor/target
- adjust general settings

## Static Card Registration

`__init__.py` also serves the `www` directory and registers a Lovelace resource
for `connectivity_monitor_card.js`.

This is unrelated to the polling logic, but it explains why the integration has
code that touches:

- HTTP static paths
- Lovelace resources
- `VERSION` from `manifest.json`

## Tests

The test layout mirrors the code layout:

- `test_config_flow.py`: config flow and options flow
- `test_init.py`: setup, unload, migration
- `test_sensor.py`: entity state and alert behavior
- `test_coordinator.py`: coordinator-specific behavior

If you want to change behavior, this is the fastest rule of thumb:

- Flow bug or validation bug: start with `test_config_flow.py`
- Runtime setup or migration bug: start with `test_init.py`
- Entity state or alert bug: start with `test_sensor.py`
- Polling/fallback/keying bug: start with `test_coordinator.py`

## Common Change Scenarios

### Add a new protocol type

You will usually need to touch:

- `const.py`
- `config_flow.py`
- `coordinator.py`
- `sensor.py`
- translations in `strings.json`
- tests

### Change alert behavior

You will usually work mostly in:

- `sensor.py` inside `AlertHandler`
- `test_sensor.py`

### Change network validation or probing

You will usually work in:

- `network.py`
- `config_flow.py`
- `coordinator.py`
- `test_config_flow.py`
- `test_coordinator.py`

## Mental Model

If you want one short mental model for the whole integration, use this:

- `config_flow.py` decides what should be monitored
- `__init__.py` wires runtime objects together
- `coordinator.py` collects fresh raw status
- `sensor.py` turns raw status into entities and alerts
- `network.py` performs the low-level network checks

That is the core of the Python code.