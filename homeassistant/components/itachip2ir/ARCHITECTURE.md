# iTach IP2IR Integration Architecture

This document describes the structure of the iTach IP2IR Home Assistant integration and how its runtime components interact.

The integration provides Home Assistant `infrared` entities for physical infrared-capable output ports on Global Caché iTach IP2IR devices.

The integration communicates directly with the device over the local network and does not depend on any cloud service.

---

# 1. High-Level Overview

At a high level, the runtime architecture is:

```text
Home Assistant
  ↓
Config Flow / Discovery / Options Flow
  ↓
ConfigEntry
  ↓
Runtime Data
  ↓
Infrared Entities
  ↓
pyitach Client
  ↓
Global Caché iTach IP2IR
```

The integration focuses on low-level infrared transmission through the Home Assistant `infrared` domain.

Related Home Assistant developer documentation:

- Infrared building block:
  https://developers.home-assistant.io/docs/core/entity/infrared/

---

# 2. iTach Hardware and Protocol Summary

The Global Caché iTach IP2IR is a local-network infrared controller.

The device exposes a TCP command API, normally on port `4998`, and transmits infrared commands through numbered physical connector ports.

The integration uses the protocol to:

- Query device information
- Query infrared connector modes
- Detect infrared-capable ports
- Transmit infrared commands

The protocol is sequential. Commands are sent over a TCP connection and responses are received through the same connection.

Infrared transmission completion is reported through `completeir` responses.

Low-level protocol handling is implemented by the external `pyitach` library.

---

# 3. Design Goals

The integration architecture prioritizes:

- Strict separation between Home Assistant runtime behavior and low-level protocol handling
- Concurrency safety for the sequential iTach TCP protocol
- Resilience against DHCP and host/IP changes
- Clean unload and reload handling
- Strong automated testability

---

# 4. Architectural Separation

The integration separates:

- Home Assistant entity logic
- Runtime orchestration
- Discovery handling
- Protocol communication

The Home Assistant integration layer is responsible for:

- ConfigEntry lifecycle management
- Entities
- Diagnostics
- Repairs
- Translations
- User-facing errors

The `pyitach` library is responsible for:

- TCP communication
- Protocol parsing
- Discovery beacon parsing
- Capability detection
- Device identifier normalization

---

# 5. Discovery Architecture

Discovery is implemented in `discovery.py`.

The integration supports:

- Home Assistant DHCP discovery
- Global Caché UDP beacon discovery

DHCP discovery is handled by Home Assistant and enters the integration through the config flow.

UDP discovery runs as a shared listener started during integration setup.

Discovery responsibilities include:

- Listening for discovery beacons
- Parsing beacon payloads
- Normalizing discovered hosts
- Normalizing device identifiers
- Filtering unsupported devices
- Suppressing duplicate discovery flows
- Tracking host/IP changes

Discovery is managed outside entity lifecycle state so device tracking continues independently from individual entities.

UDP discovery supplements configuration but is not required for runtime operation after setup completes.

---

# 6. Device Identity

The integration avoids using IP addresses as stable identifiers.

The preferred stable identity is the Global Caché device identifier derived from the device MAC address.

The device identifier is used as the ConfigEntry unique ID.

This allows the integration to distinguish:

- The same device at a new IP address
- A different device at the same IP address
- Duplicate setup attempts

When discovery detects a known device at a new host address, the integration updates the stored host and reloads the ConfigEntry automatically.

---

# 7. Config Flow

`config_flow.py` handles setup, discovery confirmation, and reconfiguration.

Manual setup responsibilities:

- Accept host and port
- Validate the target device
- Query infrared capability
- Normalize the device identifier
- Create the ConfigEntry

Discovery flow responsibilities:

- Receive discovery information
- Prevent duplicate entries
- Ask the user to confirm setup
- Create the ConfigEntry

Reconfiguration responsibilities:

- Allow host and port updates
- Validate the new target before saving

The config flow validates the device before entity creation to avoid partially configured runtime state.

---

# 8. Runtime Setup

`__init__.py` manages integration setup and unload handling.

Responsibilities include:

- Starting shared UDP discovery
- Creating one `ItachClient` per ConfigEntry
- Creating runtime data
- Forwarding platform setup
- Handling unload cleanup
- Closing runtime clients

Runtime-only objects are stored in:

```python
entry.runtime_data
```

Shared integration state is stored in:

```python
hass.data[DOMAIN]
```

Persistent configuration is stored in:

```python
ConfigEntry.data
ConfigEntry.options
```

The integration does not persist transient runtime state such as:

- TCP sockets
- Active tasks
- Runtime availability state

---

# 9. Connection Lifecycle

The integration creates one `ItachClient` per ConfigEntry and reuses the TCP connection across commands.

The client reconnects automatically if the connection becomes stale or unavailable.

Connectivity is verified during:

- Setup
- Reconfiguration
- Capability refresh
- Command execution

The integration is fully asyncio-based and does not use dedicated transport worker threads.

---

# 10. Infrared Platform

`infrared.py` exposes physical infrared-capable output ports as Home Assistant infrared entities.

Each infrared-capable output port becomes one infrared entity.

Entity responsibilities include:

- Representing one physical infrared output port
- Exposing device information
- Transmitting infrared timing data
- Converting normalized timing data into iTach protocol commands
- Surfacing connection and command errors
- Reporting availability

The infrared entity is the only entity type that directly communicates with the runtime `ItachClient`.

Related Home Assistant developer documentation:

https://developers.home-assistant.io/docs/core/entity/infrared/

---

# 11. Infrared Payload Handling

The integration transmits normalized Home Assistant infrared timing payloads.

The integration validates:

- Carrier frequency
- Timing structure
- Timing values

before converting the payload into iTach `sendir` commands.

The integration does not expose raw iTach protocol commands directly to Home Assistant users.

---

# 12. Capability Detection

Capability detection uses iTach protocol queries to determine:

- Available infrared modules
- Connector modes
- Enabled infrared output ports

Only ports configured for infrared transmission are exposed as Home Assistant entities.

Ports configured for sensors or LED functionality are ignored.

Fallback handling exists for incomplete connector-mode reporting.

---

# 13. Concurrency Model

The integration uses one `ItachClient` per physical iTach device.

All infrared ports on the same device share the same TCP connection and command-processing pipeline.

Because the protocol is sequential, infrared commands are serialized through the shared client rather than transmitted concurrently.

This prevents:

- Overlapping commands
- Interleaved responses
- Mismatched `completeir` responses
- Stale response handling issues

Using one shared client per device also centralizes:

- Reconnect logic
- Protocol sequencing
- Runtime ownership
- Diagnostics

---

# 14. State Management

Infrared entities are stateless transmitters.

Because the iTach protocol provides no downstream state feedback from target appliances, entity availability reflects exclusively the connection status to the iTach controller itself.

Higher-level appliance state tracking must be handled by separate integrations or helper entities.

---

# 15. Diagnostics

`diagnostics.py` exposes structured diagnostic data for the ConfigEntry.

Diagnostics include:

- ConfigEntry data
- Runtime host and port
- Detected infrared ports
- Connector modes
- Enabled infrared ports
- Runtime connection errors

Sensitive identifiers are redacted where appropriate.

Diagnostics reuse existing runtime state whenever possible instead of creating unnecessary network connections.

---

# 16. Repairs

`repairs.py` creates Home Assistant repair issues for important integration problems.

Repair issues may be created for:

- Connection failures
- Invalid configuration
- Missing infrared-capable ports

---

# 17. Error Handling

The `pyitach` library raises typed protocol exceptions such as:

- `ItachConnectionError`
- `ItachCommandError`
- `ItachResponseError`
- `ItachBusyError`
- `ItachIdentityError`

The Home Assistant integration layer converts these into:

- Config flow errors
- Unavailable entities
- Action errors
- Repair issues
- Diagnostics information

---

# 18. Testing Architecture

The test suite covers:

- Config flow
- Discovery
- Setup and unload
- Diagnostics
- Repairs
- Infrared entities
- Options flow
- Protocol error paths

The protocol layer can be tested independently from Home Assistant runtime behavior.

---

# 19. Component Responsibility Table

| File | Responsibility |
|---|---|
| `config_flow.py` | Setup and validation |
| `options_flow.py` | Runtime configuration updates |
| `discovery.py` | UDP discovery and host tracking |
| `infrared.py` | Physical infrared entities |
| `diagnostics.py` | Diagnostics export |
| `repairs.py` | Repair issue generation |
| `pyitach.client` | TCP transport and serialization |
| `pyitach.protocol` | Protocol encoding/parsing |
| `pyitach.discovery` | Discovery beacon parsing |
| `pyitach.capabilities` | Capability detection |
| `pyitach.identity` | Device ID normalization |

---

# 20. Future Extension Areas

Potential future enhancements include:

- Infrared learning support
- Additional Global Caché device models
- Protocol decoding helpers
- Additional diagnostics tooling
