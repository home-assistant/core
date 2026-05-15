# iTach IP2IR Integration Architecture

This document explains how the iTach IP2IR Home Assistant integration is structured, how its runtime components work together, and how the Home Assistant integration layer relates to the bundled `pyitach` protocol layer.

The integration is designed around one physical Global Caché iTach IP2IR network infrared controller, one or more physical infrared-capable output ports, and optional user-created virtual remote entities.

The document is intended for:

- Home Assistant contributors
- future maintainers
- reviewers
- protocol-layer developers
- advanced users extending the integration

---

# 1. High-Level Overview

The integration allows Home Assistant to transmit infrared commands through a Global Caché iTach IP2IR device.

The integration is fully local. It communicates directly with the iTach device over the local network and does not depend on any cloud service.

At a high level, the architecture is:

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

Optional virtual remotes add another layer:

```text
Remote Entity
  ↓
Named IR Command Parsing
  ↓
Infrared Entity
  ↓
pyitach Client
  ↓
iTach IR Port
```

The remote entity does not communicate with the hardware directly. It resolves its configured infrared entity and delegates transmission to that entity.

Remote entities intentionally delegate transmission to infrared entities rather than communicating directly with the protocol layer.

This preserves:

- one transport ownership model
- one availability model
- one protocol translation path
- one hardware abstraction layer

Related Home Assistant concepts:

- Infrared building block:
  https://developers.home-assistant.io/docs/core/entity/infrared/

- Remote entity platform:
  https://developers.home-assistant.io/docs/core/entity/remote/

---

# 2. iTach Hardware and Protocol Summary

The Global Caché iTach IP2IR is a local-network infrared controller. It exposes a TCP command API, normally on port `4998`, and sends infrared commands through numbered connector ports.

The integration uses the iTach API to:

- query device modules with `getdevices`
- query network information with `get_NET`
- query firmware information with `getversion`
- query infrared connector modes with `get_IR`
- transmit infrared commands with `sendir`

The iTach protocol is sequential. Commands are sent over a TCP connection and responses are read back from the same connection. Infrared transmission completion is reported through `completeir` responses.

The bundled `pyitach` layer owns this protocol behavior so the Home Assistant entity layer does not need to construct or parse raw iTach messages directly.

---

# 3. Architectural Separation Principles

The integration intentionally separates:

- Home Assistant entity logic
- runtime orchestration
- protocol communication
- command parsing
- discovery handling

This separation exists to improve:

- testability
- maintainability
- Home Assistant Core portability
- protocol reuse
- runtime reliability
- contributor onboarding

The `pyitach` layer should remain largely Home Assistant agnostic.

Home Assistant-specific concepts such as:

- entities
- ConfigEntry lifecycle management
- diagnostics
- repairs
- translations
- Home Assistant exceptions

should remain in the integration layer rather than inside the protocol layer.

This separation is one of the most important long-term maintainability goals of the integration.

Bundling `pyitach` within the integration allows protocol evolution, integration-specific optimizations, and synchronized testing without requiring immediate external package release coordination.

---

# 4. Design Goals

The integration is designed to provide:

- fully local operation
- UI-based setup
- DHCP and UDP beacon discovery
- stable device identification
- automatic host/IP recovery
- dynamic infrared capability detection
- Home Assistant infrared-domain support for physical infrared output ports
- Home Assistant remote-platform support through optional virtual remote entities
- named infrared command management
- safe command validation
- diagnostics
- repair issues
- unload/reload support
- strong automated test coverage

The integration intentionally focuses on infrared transmission. It does not expose non-infrared iTach capabilities as entities.

---

# 5. Discovery Architecture

Discovery is implemented in `discovery.py`.

The integration uses two discovery paths:

- Home Assistant DHCP discovery
- Global Caché UDP beacon discovery

DHCP discovery is handled by Home Assistant and enters the integration through the config flow.

UDP discovery is started by the integration in `async_setup()`. It runs as a shared integration-level listener rather than as part of any individual ConfigEntry or entity.

This allows the integration to:

- discover devices before entries exist
- continue tracking configured devices independently of entity lifecycle state
- track IP address changes
- avoid duplicate listeners
- avoid entity lifecycle coupling

UDP discovery is used for:

- finding iTach devices on the network
- mapping hosts to stable Global Caché device IDs
- starting discovery flows
- detecting host/IP changes for already configured devices

UDP discovery supplements configuration but is not required for runtime operation after setup completes.

Discovery responsibilities include:

- listening for discovery beacons
- parsing beacon payloads
- normalizing discovered host values
- normalizing device identifiers
- filtering unsupported devices
- preventing duplicate discovery flows
- updating known host/device mappings
- reloading ConfigEntries after automatic host updates

Discovery intentionally exists outside entity lifecycle management.

If discovery were tied to entity lifecycle:

- IP changes could be missed
- unloaded entities could stop host tracking
- duplicate listeners could appear
- startup ordering would become more fragile

Discovery is started once at integration setup time and is shared across ConfigEntries.

It stops cleanly when Home Assistant stops.

---

# 6. Network Discovery Caveats

UDP discovery binds to the Global Caché discovery port and joins the discovery multicast group using default/all-interface operating-system behavior.

The implementation does not currently select interfaces through Home Assistant network helpers.

Complex network layouts such as:

- VLANs
- Docker bridge networking
- restricted multicast forwarding
- multiple network interfaces

may prevent discovery beacons from reaching Home Assistant.

Manual setup by host/IP remains the fallback path.

---

# 7. Device Identity

The integration avoids using IP addresses as stable identifiers.

The preferred stable identity is a normalized Global Caché device identifier:

```text
GlobalCache_XXXXXXXXXXXX
```

The device ID is used as the ConfigEntry unique ID.

This allows the integration to distinguish:

- the same physical device at a new IP address
- a different device at the same IP address
- duplicate setup attempts
- DHCP-discovered devices
- manually configured devices

When discovery finds a known device ID at a new host, the integration can update the stored host and reload the ConfigEntry.

The architecture assumes:

- device IDs remain stable across DHCP changes
- discovery beacons accurately identify devices
- one physical device maps to one stable identifier

---

# 8. Config Flow

`config_flow.py` handles setup, discovery confirmation, and reconfiguration.

Manual setup responsibilities:

- accept host and port
- optionally accept a user-provided device ID
- validate the target device
- query infrared capability
- normalize the device ID
- create the ConfigEntry

Discovery flow responsibilities:

- receive host, port, model, and device ID from discovery
- set the device ID as the unique ID
- prevent duplicate entries
- ask the user to confirm setup
- create the ConfigEntry

Reconfiguration responsibilities:

- allow host and port updates
- validate the new target before saving
- preserve existing configuration on failure

The config flow intentionally validates devices before entity creation in order to:

- fail early
- avoid invalid runtime state
- prevent partially configured entries
- improve diagnostics

---

# 9. Runtime Setup

`__init__.py` manages integration lifecycle setup and unload handling.

Responsibilities include:

- starting shared UDP discovery
- creating one `ItachClient` per ConfigEntry
- creating runtime data
- forwarding platform setup
- handling unload cleanup
- closing runtime clients

Reloading a ConfigEntry recreates runtime clients, refreshes capabilities, rebuilds entities, and restarts runtime orchestration associated with that entry.

Runtime-only objects are stored in `entry.runtime_data`.

Shared integration state is stored in:

```python
hass.data[DOMAIN]
```

Persistent state is stored in:

```python
ConfigEntry.data
ConfigEntry.options
```

Remote definitions and named command mappings are stored in ConfigEntry options rather than runtime-only state.

The integration intentionally does not persist:

- TCP connection state
- socket objects
- active tasks
- transient protocol responses
- runtime availability state

---

# 10. Data Ownership Model

```text
ConfigEntry.data
 ├── host
 ├── port
 └── device_id

ConfigEntry.options
 └── virtual remotes

entry.runtime_data
 ├── ItachClient
 ├── capabilities
 └── runtime caches

hass.data[DOMAIN]
 └── shared discovery state
```

---

# 11. Connection Lifecycle and Health

The integration creates one `ItachClient` per ConfigEntry and reuses its TCP connection across commands. The client does not open and close a socket for every command.

To avoid reusing stale idle sockets, the client treats connections idle for more than 15 seconds as stale. Before sending another command, it closes and reopens the connection.

The integration does not currently run a periodic heartbeat.

Connectivity is verified during:

- setup
- reconfiguration
- capability refresh
- command execution

A future enhancement could add an optional lightweight heartbeat if field testing shows idle TCP connections are a recurring source of unavailable states.

The integration is fully asyncio-based and does not use dedicated worker threads for protocol transport.

---

# 12. Physical vs Logical Entities

The integration intentionally separates physical infrared output entities from logical remote entities.

Infrared entities model physical infrared output connectors.

Remote entities model logical user devices.

Example:

```text
Physical iTach Device
 ├── Infrared Port 1 Entity
 ├── Infrared Port 2 Entity
 └── Infrared Port 3 Entity

Virtual Remote Entities
 ├── Living Room TV
 ├── AV Receiver
 └── Projector
```

This separation allows:

- multiple logical devices to share one physical infrared output
- remotes to be reconfigured independently of hardware
- command organization independent of connector layout
- cleaner user-facing abstractions

---

# 13. Infrared Platform

`infrared.py` exposes physical iTach infrared-capable output ports as Home Assistant infrared entities.

Each usable infrared-capable output port becomes one infrared entity.

The infrared entity responsibilities include:

- representing one iTach infrared output port
- exposing device information
- transmitting normalized infrared timing sequences
- converting normalized command data to iTach `sendir`
- using the shared runtime client
- surfacing connection and command errors
- reporting availability

The infrared entity is the only entity type that directly sends commands to the `pyitach` client.

Related Home Assistant developer documentation:

https://developers.home-assistant.io/docs/core/entity/infrared/

---

# 14. State Management

Infrared entities are effectively stateless transmitters.

They do not know whether the controlled external device actually changed state after an infrared command is sent.

The iTach protocol does not provide bidirectional device-state feedback.

The integration therefore cannot reliably determine:

- device power state
- active input source
- playback state
- volume level
- menu state

without additional external integrations.

Entity availability reflects the ability to communicate with the iTach device, not the state of the external infrared-controlled hardware.

The entity state therefore represents transmitter availability rather than the actual runtime state of the controlled television, receiver, projector, air conditioner, or other infrared-controlled hardware.

If state metadata is exposed, it should be limited to transmitter-side information such as:

```text
last transmission timestamp
```

and should not imply that the controlled device successfully entered a specific runtime state.

---

# 15. Remote Platform

`remote.py` exposes optional virtual remote entities.

Remote entities are logical Home Assistant remotes created by the user.

A remote entity:

- has a user-defined name
- stores named infrared commands
- references one infrared entity
- delegates all transmission to the infrared entity
- does not communicate with the iTach hardware directly

This architecture allows users to model logical devices such as:

- televisions
- AV receivers
- air conditioners
- projectors
- HDMI switches

Named commands belong to the remote entity and remain independent from the underlying infrared entity implementation.

Related Home Assistant developer documentation:

https://developers.home-assistant.io/docs/core/entity/remote/

---

# 16. Infrared Payload Format Boundaries

The infrared entity transmits normalized Home Assistant infrared command objects. It does not accept arbitrary raw Global Caché `sendir` strings directly.

The remote layer accepts supported user command formats and normalizes them through `command.py` before delegating to the infrared entity.

Supported payload styles currently include:

- JSON timing arrays
- JSON objects containing `timings`
- plain text timing sequences
- optional carrier-frequency prefixes
- learned raw Pronto hex beginning with `0000`

Normalized infrared timings are represented in microseconds before conversion into iTach `sendir` cycle timing units.

The final hardware layer converts normalized timing data into iTach `sendir` commands.

---

# 17. Command Parsing

`command.py` contains higher-level command parsing used by the remote platform.

The parser validates and normalizes user-provided command payloads before they are transmitted through the infrared entity layer.

Supported payloads include:

- normalized timing arrays
- structured timing payloads
- compatible raw infrared payload formats

This preserves separation between:

```text
remote command storage/parsing
  ↓
infrared timing transmission
  ↓
iTach sendir protocol
```

---

# 18. pyitach Protocol Layer

The bundled `pyitach` package is the low-level iTach protocol/client layer.

It is intentionally kept mostly independent from Home Assistant internals.

`pyitach` provides:

- asynchronous TCP client support
- iTach command generation
- response parsing
- discovery beacon parsing
- infrared capability helpers
- device identifier normalization
- typed exceptions
- protocol validation

Important files include:

```text
pyitach/_client.py
pyitach/_protocol.py
pyitach/_discovery.py
pyitach/_capabilities.py
pyitach/_identity.py
pyitach/_exceptions.py
```

The protocol layer intentionally avoids:

- entity logic
- Home Assistant runtime dependencies
- Home Assistant ConfigEntry behavior
- Home Assistant diagnostics logic

This keeps the protocol layer reusable and independently testable.

---

# 19. Capability Detection

Capability detection uses iTach protocol calls such as:

- `getdevices`
- `get_IR`

The resulting capability model contains:

- infrared module number
- number of ports
- connector modes
- enabled infrared output ports

The integration uses this capability model to determine which infrared entities should be created.

Fallback behavior exists for incomplete connector-mode reporting.

Only infrared-capable outputs are exposed as infrared entities.

Unsupported connector types are intentionally ignored.

---

# 20. Concurrency Model

The integration uses one `ItachClient` per ConfigEntry.

All infrared output ports on the same physical iTach device share the same TCP command channel.

Because the iTach protocol is sequential, infrared commands must be serialized through the shared per-entry client rather than written concurrently to the socket.

This means commands sent to different infrared ports on the same physical device are still coordinated through the same client lock and response-processing pipeline.

This avoids:

```text
overlapping sendir commands
interleaved responses
mis-matched completeir responses
stale response handling errors
```

The client therefore guarantees ordered command execution and ordered response processing across all infrared ports belonging to the same iTach device.

Using one shared client per device also guarantees:

- centralized reconnect logic
- predictable runtime ownership
- lower socket overhead
- consistent protocol sequencing
- simpler diagnostics

The architecture assumes:

- protocol responses are ordered
- the protocol is sequential
- `completeir` corresponds to the most recent request
- one client owns one TCP connection

---

# 21. Concurrency Deep Dive

| Scenario | Behavior |
|---|---|
| Two remotes send commands simultaneously | Both commands serialize through the same client |
| Two different infrared ports transmit simultaneously | Requests still serialize because they share one TCP socket |
| One command times out | Error surfaces to the caller and the client may reconnect |
| A stale response arrives | Response matching logic ignores or rejects stale data |

---

# 22. Typical Runtime Flow

Typical virtual remote transmission flow:

```text
User calls remote.send_command
  ↓
Remote entity resolves command
  ↓
Command parser normalizes payload
  ↓
Infrared entity validates availability
  ↓
ItachClient serializes request
  ↓
sendir command written to TCP socket
  ↓
iTach processes command
  ↓
completeir response received
  ↓
response matched to request
  ↓
task completes
```

Direct infrared transmissions skip the remote-command abstraction layer and call the infrared entity directly.

---

# 23. Failure Recovery Examples

Scenario: Device receives a new DHCP address

```text
UDP discovery detects new host
  ↓
Known device ID matches existing ConfigEntry
  ↓
ConfigEntry host updated
  ↓
Entry reloaded automatically
```

Scenario: Device becomes temporarily unreachable

```text
Infrared entities become unavailable
  ↓
Commands raise Home Assistant errors
  ↓
Reconnect attempted
  ↓
Normal operation resumes automatically
```

Scenario: Duplicate discovery beacon received

```text
Discovery flow already in progress
  ↓
Duplicate flow suppressed
```

---

# 24. Diagnostics

`diagnostics.py` exposes structured diagnostic data for the ConfigEntry.

Diagnostics include:

- ConfigEntry data
- runtime host and port
- detected infrared module
- detected infrared ports
- connector modes
- enabled infrared ports

Sensitive values are redacted where applicable.

Diagnostics reuse existing runtime state whenever possible.

The diagnostics layer should avoid creating unnecessary new network connections.

---

# 25. Repairs

`repairs.py` creates user-visible repair issues for important integration problems.

Repair issues may be created for:

- cannot connect
- no infrared ports
- invalid configuration

Repairs help users understand both the problem and the corrective action.

Repair logic intentionally remains separate from protocol transport logic.

---

# 26. Error Handling

The integration separates low-level protocol errors from Home Assistant user-facing errors.

`pyitach` raises typed exceptions such as:

- `ItachConnectionError`
- `ItachCommandError`
- `ItachResponseError`
- `ItachBusyError`
- `ItachIdentityError`

The Home Assistant layer converts these into:

- config flow errors
- unavailable entities
- service errors
- repair issues
- diagnostics information

This separation keeps protocol behavior reusable while preserving clean Home Assistant user experience handling.

---

# 27. Testing Architecture

The test suite covers:

- config flow
- discovery
- setup and unload
- diagnostics
- repairs
- infrared entities
- remote entities
- options flow
- command parsing
- pyitach client behavior
- protocol parsing
- error paths

The architecture is designed to remain testable through strong separation between:

```text
Home Assistant integration layer
```

and:

```text
pyitach protocol layer
```

The protocol layer can be tested largely independently from Home Assistant runtime behavior.

---

# 28. Component Responsibility Table

| File | Responsibility |
|---|---|
| `config_flow.py` | Setup and validation |
| `options_flow.py` | User-editable runtime configuration |
| `discovery.py` | UDP discovery and host tracking |
| `infrared.py` | Physical infrared entities |
| `remote.py` | Logical remote entities |
| `command.py` | Command parsing |
| `diagnostics.py` | Diagnostics export |
| `repairs.py` | Repair issue generation |
| `pyitach/_client.py` | TCP transport and serialization |
| `pyitach/_protocol.py` | Protocol encoding/parsing |
| `pyitach/_discovery.py` | Discovery beacon parsing |
| `pyitach/_capabilities.py` | Capability detection |
| `pyitach/_identity.py` | Device ID normalization |

---

# 29. Future Extension Areas

Potential future expansion areas include:

- infrared learning support
- additional Global Caché models
- protocol decoding helpers
- import/export of remote definitions
- command libraries
- learned-command storage helpers
- additional diagnostics tooling

Future enhancements should preserve the separation between:

- Home Assistant integration logic
- protocol transport logic
- command parsing
- discovery orchestration

---

# 30. Summary

The integration is layered intentionally:

```text
Discovery
  ↓
Config Flow
  ↓
Runtime Setup
  ↓
Infrared Entities
  ↓
Optional Remote Entities
  ↓
pyitach Client
  ↓
iTach IP2IR Hardware
```

The Home Assistant layer handles:

- configuration
- entities
- diagnostics
- repairs
- translations
- user-facing behavior

The `pyitach` layer handles:

- local network communication
- protocol parsing
- command generation
- discovery parsing
- capability detection

This separation keeps the integration maintainable, testable, and suitable for both custom-component use and Home Assistant Core migration.
