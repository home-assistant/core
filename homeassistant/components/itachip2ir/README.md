# iTach IP2IR

The iTach IP2IR integration provides Home Assistant [`infrared`](https://www.home-assistant.io/integrations/infrared/) entities for the Global Caché iTach IP2IR infrared controller.

The integration automatically detects infrared-capable ports and creates infrared entities for ports configured for infrared transmission.

## Features

- DHCP and UDP discovery support
- Automatic creation and reconciliation of infrared entities
- Transmission of infrared timing data
- Diagnostics and repairs support
- Availability tracking and automatic recovery

## Supported devices

Only Global Caché iTach IP2IR devices are supported.

Other Global Caché device types are ignored during discovery.

## Installation

Once included in Home Assistant Core, the integration can be added from the Home Assistant user interface.

Navigate to:

```text
Settings → Devices & services → Add integration
```

Search for:

```text
iTach IP2IR
```

## Setup

Devices can be added either through discovery or manual configuration.

Supported discovery methods:
- DHCP discovery
- Global Caché UDP discovery beacons

The integration uses the device MAC address as the unique identifier to avoid duplicate device creation.

Discovery may not function across VLANs, segmented networks, restrictive firewall configurations, or Docker bridge networks that block UDP multicast traffic.

Manual configuration requires:
- host or IP address
- optional TCP port (defaults to 4998)

The integration attempts to retrieve the device identifier automatically during setup.

## Infrared entities

The iTach IP2IR hardware contains three configurable physical ports. Each port may be configured through the device as one of the following modes:

- IR Out
- IR Blaster Out
- Sensor In
- Sensor Notify
- LED Lighting

Infrared entities are only created for ports configured as:
- IR Out
- IR Blaster Out

Example entities:

```text
IR Port 1
IR Port 2
IR Blaster Port 3
```

## Infrared transmission

The integration uses Home Assistant's [`infrared`](https://www.home-assistant.io/integrations/infrared/) domain and operates on infrared timing data.

Example:

```yaml
action: infrared.send_command
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

Infrared timing data is validated before transmission.

## Using remotes

This integration does not create Home Assistant `remote` entities.

Users who want reusable named commands or `remote.send_command` support can use the separate `virtual_remote` helper integration with the infrared entities exposed by this integration.

## Port reconciliation

If a physical port configuration is changed outside of Home Assistant (for example, changing a port from `Sensor In` to `IR Out`), the integration can synchronize these changes through the integration options flow.

Navigate to:

```text
Settings → Devices & services → iTach IP2IR → Configure
```

When a user triggers a refresh, the integration re-queries the device configuration and automatically adds, enables, or disables entities to match the current hardware configuration.

## Availability and recovery

If the iTach device becomes unreachable:
- affected infrared entities are marked unavailable
- service calls raise Home Assistant errors
- warnings are logged

Entities automatically return to an available state once communication is re-established.

## Diagnostics

Diagnostics are available from:

```text
Settings → Devices & services → iTach IP2IR → Download diagnostics
```

Diagnostics include:
- integration configuration
- configured host and TCP port
- detected infrared-capable ports
- connector output modes
- firmware information when available
- connection or firmware query errors

Diagnostics automatically redact stable identifiers such as:
- MAC addresses
- unique IDs
- device identifiers

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
- VLAN or Docker bridge isolation is not preventing discovery traffic

### Infrared commands do not work

Check:
- the IR emitter is connected to the expected physical iTach port
- the port is configured as `IR Out` or `IR Blaster Out`
- the infrared timing data is valid
- the carrier frequency matches the target device requirements

### Enable debug logging

The integration uses the `pyitach` library for communication with the iTach hardware.

Add the following to `configuration.yaml`:

```yaml
logger:
  logs:
    homeassistant.components.itachip2ir: debug
    pyitach: debug
```

## Known limitations

The following limitations currently apply:

- infrared learning functionality is not implemented
- infrared protocol decoding is not provided
- firmware updates are not supported through this integration

## Removing the integration

Navigate to:

```text
Settings → Devices & services → iTach IP2IR → Delete
```

Removing the integration removes:
- associated infrared entities
- stored integration configuration

The physical iTach hardware configuration is not modified.
