# iTach IP2IR

The **iTach IP2IR** integration implements the [infrared](https://www.home-assistant.io/integrations/infrared/) and [remote](https://www.home-assistant.io/integrations/remote/) entities to send IR commands to the Global Caché iTach IP2IR infrared controller.

The integration dynamically queries the iTach device configuration and automatically creates infrared entities for ports configured for infrared output. The user can optionally create virtual remote entities and associate them with an infrared entity.

The remote entity sends the IR command through the associated infrared entity; it does not directly control the underlying hardware.

```text
┌─────────────────────────────────┐
│          Remote Layer           │
├─────────────────────────────────┤
│         Infrared Layer          │
├─────────────────────────────────┤
│        IR Emitter Layer         │
└─────────────────────────────────┘
```

The integration provides the following features:

### Infrared entities

- discovery-based setup
- automatic detection of infrared-capable ports
- dynamic creation of infrared entities based on iTach port capabilities
- infrared entity reconciliation after iTach port reconfiguration
- transmission of normalized infrared timing sequences through the iTach hardware

### Remote entities

- optional creation of virtual remote entities through the options flow
- storage of reusable named infrared commands
- reassignment of associated infrared entities through the options flow
- support for `remote.send_command`
- support for user-facing command formats such as:
    - Pronto Hex
    - raw timing strings
    - JSON timing arrays

## Installation

Once included in Home Assistant Core, the integration can be added from the Home Assistant user interface.

To add the integration, navigate to:

Settings → Devices & services → Add integration

Search for:

iTach IP2IR

## Setup

Global Caché iTach IP2IR devices can be added either through discovered devices or manually added devices. To make sure that the same device does not get added multiple times, the MAC address is used as a unique identifier.

The integration supports two types of auto-discovery. DHCP discovery relies on the device sending DHCP requests and is natively supported by Home Assistant. The second discovery mechanism uses the Global Caché UDP discovery protocol. The integration listens for Global Caché UDP discovery beacons after the first iTach device has been configured.

Discovery may not work across VLANs, segmented networks, restrictive firewall configurations, or Docker bridge networks that block UDP multicast traffic.

A device can be added manually by providing the IP address, optional TCP port number (defaults to the standard iTach API port) and a unique ID. It is strongly recommended to use the actual MAC address of the iTach device. If another ID is used, auto-discovery may discover the same device as a new device because of the MAC address being different.

## Supported devices

Only Global Caché iTach IP2IR devices are supported.

The integration validates discovered Global Caché devices and automatically ignores unsupported hardware that does not provide infrared-capable ports.

## Infrared

Home Assistant introduced the [`infrared`](https://www.home-assistant.io/integrations/infrared/) domain to provide a standardized low-level interface for transmitting infrared timing sequences independently from device-specific remote implementations. Historically, many integrations implemented infrared transmission through custom `remote` entities, resulting in duplicated infrared parsing, validation, and transmission logic across integrations.

The infrared domain separates:
- low-level infrared transmission

from

- higher-level remote control abstractions.

This allows integrations to expose physical infrared-capable output ports directly while still supporting optional remote-style interfaces on top of the infrared layer.

The Global Caché iTach IP2IR hardware contains three configurable physical ports. Each port can be independently configured through the iTach hardware configuration as one of the following modes:

- IR Out
- IR Blaster Out
- Sensor In
- Sensor Notify
- LED Lighting

The integration dynamically queries the iTach hardware during setup and automatically determines:
- the number of available ports
- the configuration of each port
- which ports support infrared transmission

Infrared entities are only created for ports configured as:
- IR Out
- IR Blaster Out

Ports configured for:
- Sensor In
- Sensor Notify
- LED Lighting

are intentionally ignored because they do not support infrared transmission.

Each infrared entity represents one physical infrared-capable iTach port.

For example:

```text
IR Port 1
IR Port 2
IR Blaster Port 3
```

The infrared entity provides the low-level infrared transmission layer used by the integration. It is responsible for:
- transmitting infrared timing sequences through the iTach hardware
- exposing the physical infrared-capable output port to Home Assistant

The infrared entity itself operates on normalized infrared timing sequences. Higher-level command formats such as:
- Pronto Hex
- raw timing strings
- JSON timing arrays

are handled by the optional remote entity layer before being converted into normalized infrared timing sequences.

The iTach hardware configuration can be changed outside Home Assistant at any time. For example, a port previously configured as `Sensor In` may later be reconfigured as `IR Out`.

The integration therefore provides infrared entity reconciliation through the options flow. When the user performs a refresh, the integration re-queries the physical iTach port configuration and updates the Home Assistant infrared entities accordingly.

Depending on the updated hardware configuration, the integration may:
- create new infrared entities for newly-enabled infrared ports
- re-enable previously disabled infrared entities
- disable infrared entities for ports no longer configured for infrared transmission

This allows the Home Assistant entity model to remain synchronized with the actual physical iTach hardware configuration without recreating the integration.

### Direct infrared transmission examples

Advanced users may choose to interact directly with the infrared entity instead of using the optional remote entity abstraction layer.

The infrared entity operates on normalized infrared timing sequences.

Example:

```yaml
service: infrared.send_command
target:
  entity_id: infrared.ir_port_1
data:
  command:
    carrier_frequency: 38000
    timings:
      - 9000
      - 4500
      - 560
      - 560
      - 560
      - 1690
      - 560
      - 560
```

The infrared entity does not directly support higher-level user-facing infrared formats such as:
- Pronto Hex
- raw timing strings
- JSON timing arrays

These formats are instead handled by the optional remote entity layer before being normalized into infrared timing sequences.

## Availability and Recovery

If the iTach device becomes unreachable:
- affected infrared entities are marked unavailable
- service calls raise Home Assistant errors
- warning messages are logged

When communication is restored, the entities automatically recover and become available again.

## Diagnostics

Diagnostics are available from:

Settings → Devices & services → iTach IP2IR → Download diagnostics

Diagnostics include:
- integration configuration
- configured host and TCP port
- detected infrared-capable ports
- connector output modes
- firmware version information when available
- connection or firmware query errors

Diagnostics automatically redact stable identifiers such as:
- MAC addresses
- unique IDs
- device identifiers

## Remote

Before Home Assistant introduced the [`infrared`](https://www.home-assistant.io/integrations/infrared/) domain, infrared integrations commonly exposed infrared transmission through the [`remote`](https://www.home-assistant.io/integrations/remote/) domain. The remote domain provides a higher-level abstraction designed around reusable named commands and user-facing remote control interactions.

The iTach IP2IR integration therefore separates:
- low-level infrared transmission

from

- higher-level remote control abstractions.

The infrared entity provides direct access to the physical infrared-capable output port, while the optional remote entity provides a reusable command-oriented interface on top of the infrared layer.

Remote entities are optional and are not automatically created when the integration is added. Users can create any number of virtual remote entities through the integration options flow.

Each virtual remote entity is associated with one infrared entity. Multiple virtual remotes may use the same infrared entity. This allows users to organize infrared commands by appliance or room while still using the same physical infrared-capable iTach port.

For example:

```text
Living Room TV Remote
    └── IR Port 1

AV Receiver Remote
    └── IR Port 1

Bedroom TV Remote
    └── IR Blaster Port 3
```

The remote entity itself does not directly communicate with the iTach hardware. Instead, the remote entity passes infrared commands to the associated infrared entity, which then performs the actual infrared transmission through the physical iTach port.

This layered architecture separates:
- command storage and remote-style interactions

from

- physical infrared transmission.

Each remote entity can store reusable named infrared commands. Named commands allow Home Assistant automations, scripts, and dashboards to reference logical command names instead of repeatedly specifying raw infrared payloads.

For example:

```text
power_on
volume_up
volume_down
input_hdmi1
```

The integration supports several user-facing infrared command formats, including:

- Pronto Hex
- raw timing strings
- JSON timing arrays

The remote entity automatically validates and normalizes supported command formats before passing normalized infrared timing sequences to the associated infrared entity.

Infrared commands can be:
- added
- edited
- removed

through the integration options flow.

Infrared commands are associated with the virtual remote entity itself rather than the physical infrared entity. This means the stored commands remain available even if the associated infrared entity becomes temporarily unavailable or disabled due to iTach port reconfiguration.

The associated infrared entity for a remote can also be changed through the options flow. This allows users to reassign a virtual remote to a different infrared-capable iTach port without recreating the remote entity or losing stored infrared commands.

Typical use cases include:
- moving an appliance to a different physical iTach output port
- switching from an IR emitter port to an IR blaster port
- recovering from iTach port reconfiguration changes
- reorganizing room-specific infrared transmitters

The remote entity supports Home Assistant's standard `remote.send_command` service.

This allows automations and scripts such as:

```yaml
service: remote.send_command
target:
  entity_id: remote.living_room_tv
data:
  command: power_on
```

### Pronto Hex example

```yaml
service: remote.send_command
target:
  entity_id: remote.living_room_tv
data:
  command: |
    0000 006D 0022 0002 0157 00AC 0016 0016
    0016 0016 0016 0016 0016 0016 0016 0016
```

The remote entity therefore provides a stable, reusable, user-friendly abstraction layer for organizing and transmitting infrared commands independently from the underlying physical iTach hardware configuration.

## Troubleshooting

### The integration cannot connect

Check:
- the iTach device is powered on
- the configured IP address is correct
- TCP port `4998` is reachable
- firewall rules allow Home Assistant to communicate with the device

### No devices are discovered

Check:
- Home Assistant and the iTach device are on the same subnet
- UDP multicast traffic is not blocked
- firewall rules allow UDP discovery traffic
- VLAN or Docker bridge network isolation is not preventing discovery traffic

### Infrared commands do not work

Check:
- the IR emitter is connected to the expected physical iTach port
- the iTach port is configured as `IR Out` or `IR Blaster Out`
- the infrared timing data or command format is valid
- the carrier frequency matches the target device requirements

### Enable debug logging

Add the following to `configuration.yaml`:

```yaml
logger:
  logs:
    homeassistant.components.itachip2ir: debug
    homeassistant.components.itachip2ir.pyitach: debug
```

## Known limitations

The integration currently focuses exclusively on infrared transmission through the Home Assistant `infrared` and `remote` domains.

The following limitations currently apply:

- infrared learning functionality is not currently implemented
- Home Assistant infrared learning APIs and workflows are still evolving
- only infrared-capable iTach ports are exposed as Home Assistant entities
- ports configured as:
    - Sensor In
    - Sensor Notify
    - LED Lighting

  are intentionally ignored by the integration
- infrared protocol decoding and protocol identification are not provided by the integration
- infrared commands must be supplied as supported infrared payload formats or normalized infrared timing sequences
- firmware updates are not supported through this integration and must be performed using vendor-supported tools

The integration is intentionally focused on providing a stable, standards-based infrared transmission implementation aligned with the Home Assistant infrared architecture.

## Removing the integration

To remove the integration, navigate to:

Settings → Devices & services → iTach IP2IR → Delete

Removing the integration automatically removes:
- associated infrared entities
- associated remote entities
- stored virtual remote configuration
- stored infrared commands

The physical iTach device configuration is not modified.
