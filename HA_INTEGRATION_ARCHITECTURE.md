# Home Assistant Integration Architecture - Comprehensive Analysis

## Overview

Home Assistant is built on a component-based architecture where **integrations** (formerly called "components") are dynamically loaded Python modules that extend the core system. The architecture prioritizes:

1. **Asynchronous I/O** - All external operations are async to prevent blocking the event loop
2. **Dynamic Loading** - Integrations and platforms load on-demand with intelligent caching
3. **Configuration Management** - Flexible config flow UI + programmatic setup
4. **State Management** - Centralized entity/device tracking through registries
5. **Event-Driven** - Services, state changes, and events provide tight coupling mechanisms

---

## 1. Integration Loading & Discovery

### 1.1 Loader Architecture (`homeassistant/loader.py`)

The loader is responsible for discovering, parsing, and caching integrations.

**Key Components:**

```python
# Integration object - represents a loaded or loadable integration
class Integration:
    - domain: str                          # Unique identifier (e.g., "hue")
    - pkg_path: str                        # Python module path
    - manifest: Manifest                   # manifest.json data
    - file_path: pathlib.Path              # Disk location
    
    # Key methods:
    - async_get_component()                # Load integration module
    - async_get_platform(name)             # Load specific platform
    - async_get_platforms(names)           # Load multiple platforms
    - resolve_dependencies()               # Resolve dependency graph
```

**Integration Discovery Flow:**

1. **Resolution** - `async_get_integration(hass, domain)`
   - Check cache first (extremely fast)
   - Look in custom_components/
   - Look in homeassistant/components/
   - Parse manifest.json
   - Validate custom integration (version, blocking list)

2. **Dependency Resolution** - `resolve_integrations_dependencies()`
   - Recursive dependency graph resolution
   - Detects circular dependencies (raises error)
   - Validates all dependencies exist
   - Caches resolved dependency sets

3. **Module Loading** - Two strategies:
   ```
   import_executor=True (default):  Load in thread pool executor
   import_executor=False:            Load in event loop
   ```
   This prevents import deadlocks while avoiding event loop blocking.

**Blocked Custom Integrations:**

Home Assistant maintains a blocklist of malicious custom integrations with version constraints and reasons.

### 1.2 Platform Loading

Platforms are integration-specific implementations (e.g., "light.hue", "sensor.template").

**Preload Strategy:**

```python
BASE_PRELOAD_PLATFORMS = [
    "config_flow", "diagnostics", "condition", "trigger", "intent",
    "logbook", "recorder", "repairs", "system_health", ...
]
```

Preloaded platforms are imported early to avoid thundering herd of executor jobs.

---

## 2. Integration Lifecycle

### 2.1 Manifest Structure (`manifest.json`)

```json
{
  "domain": "hue",
  "name": "Philips Hue",
  "codeowners": ["@balloob"],
  "integration_type": "device",
  "iot_class": "local_polling",
  "quality_scale": "gold",
  "config_flow": true,
  "documentation": "https://...",
  "requirements": ["aiohue==4.0.0"],
  "dependencies": ["http"],
  "after_dependencies": ["recorder"],
  "version": "1.0.0",
  "import_executor": true,
  "single_config_entry": false,
  "zeroconf": ["_hue._tcp.local."],
  "dhcp": [{"hostname": "hue-*"}],
  "ssdp": [{"st": "upnp:rootdevice"}],
  "bluetooth": [{"service_uuid": "xxxx"}],
  "usb": [{"vid": "2047", "pid": "2073"}]
}
```

### 2.2 Setup Flow

```
Load Integration → Resolve Dependencies → Process Requirements → 
Load Module → Validate Config → Call async_setup() → 
Setup Config Entries → Fire EVENT_COMPONENT_LOADED
```

---

## 3. Core HomeAssistant Object & APIs

### 3.1 HomeAssistant Class

```python
class HomeAssistant:
    # Core attributes
    loop: asyncio.AbstractEventLoop
    state: CoreState (STARTING|RUNNING|STOPPING|FINAL_WRITE|STOPPED)
    
    # Core subsystems
    bus: EventBus                  # Fire/listen to events
    services: ServiceRegistry      # Register/call services  
    states: StateMachine           # Entity state storage
    config: Config                 # Configuration management
    data: HassDict[str, Any]       # Mutable dict for integration data
    
    # Methods
    async_add_job()               # Queue coroutine/callback
    async_create_task()           # Create and track task
    async_start()                 # Start core loop
    async_run()                   # Main entry point
```

### 3.2 hass.data Dictionary

Primary way integrations store state:

```python
# Store integration data
hass.data[DOMAIN] = {
    "client": MyAPIClient(...),
    "coordinator": MyCoordinator(...),
}

# Or with type-safe HassKey
MY_KEY: HassKey[dict] = HassKey("my_domain")
hass.data[MY_KEY] = {...}
```

### 3.3 ConfigEntry

Persistence mechanism for integration configuration:

```python
class ConfigEntry:
    entry_id: str                          # Unique ID
    domain: str                            # Integration name
    title: str                             # Display name
    data: MappingProxyType[str, Any]       # Persistent config (immutable)
    runtime_data: Any                      # Mutable runtime state
    options: MappingProxyType[str, Any]    # User-configurable options
    state: ConfigEntryState                # LOADED|SETUP_ERROR|SETUP_RETRY
    
    # Lifecycle methods
    async_setup_locked()
    async_unload()
    async_remove()
    async_on_unload(callback)
    async_create_task()
```

**Runtime Data Type Hint (Platinum-tier):**

```python
type MyIntegrationConfigEntry = ConfigEntry[MyClientType]

async def async_setup_entry(hass: HomeAssistant, entry: MyIntegrationConfigEntry) -> bool:
    client = MyClientType(entry.data[CONF_API_KEY])
    entry.runtime_data = client
    return True
```

### 3.4 Event System

```python
# Fire event
hass.bus.async_fire(EVENT_STATE_CHANGED, {"entity_id": "light.kitchen"})

# Listen to event  
def on_state_change(event):
    new_state = event.data.get("new_state")

listener = hass.bus.async_listen(EVENT_STATE_CHANGED, on_state_change)

# Cleanup
listener()  # Callable for removal
```

### 3.5 Service System

```python
# Register service
async def handle_service(call: ServiceCall) -> None:
    entity_ids = call.data.get(ATTR_ENTITY_ID)
    # ... handle ...

hass.services.async_register(
    DOMAIN, "my_service",
    handle_service,
    schema=SERVICE_SCHEMA,
)

# Call service
await hass.services.async_call(
    "light", "turn_on",
    {"entity_id": "light.kitchen", "brightness": 255},
)
```

### 3.6 State Machine

```python
# Set state
hass.states.async_set("light.kitchen", "on", {"brightness": 255})

# Get state
state = hass.states.get("light.kitchen")
if state:
    current = state.state
    brightness = state.attributes.get("brightness")
```

---

## 4. Entity & Platform System

### 4.1 Entity Component

Manages entities (instances of sensors, lights, etc.):

```python
class EntityComponent:
    domain: str                    # "light", "switch", etc.
    async_add_entities(entities)   # Add entities
    async_setup_platforms(config)  # Setup platforms
```

### 4.2 Entity Base Class

```python
class Entity:
    _attr_name: str | None
    _attr_unique_id: str                              # Must be unique per domain
    _attr_device_info: DeviceInfo
    _attr_available: bool
    _attr_has_entity_name: bool
    _attr_entity_category: EntityCategory             # DIAGNOSTIC|CONFIG
    
    async def async_added_to_hass()
    async def async_will_remove_from_hass()
    async def async_update()
```

### 4.3 Specific Entity Types

```python
class SensorEntity(Entity):
    _attr_native_value: float | str | None
    _attr_device_class: SensorDeviceClass

class LightEntity(Entity):
    _attr_is_on: bool
    async def async_turn_on(**kwargs)
    async def async_turn_off()
```

---

## 5. Data Persistence & Registries

### 5.1 ConfigEntry Data Layers

```python
# entry.data - Persistent config (immutable)
{"host": "192.168.1.100", "api_key": "abc123..."}

# entry.options - User-configurable (mutable)
{"poll_interval": 30, "scan_interval": 60}

# entry.runtime_data - In-memory only
{"client": MyClient(...), "last_sync": datetime.now()}
```

### 5.2 Entity Registry

```python
from homeassistant.helpers import entity_registry as er

registry = er.async_get(hass)

# Create entity
entry = registry.async_get_or_create(
    "light", "hue", "light_1",
    config_entry=config_entry,
)

# Update entity
registry.async_update_entity(entry.entity_id, name="Kitchen Light")

# Query
entry = registry.async_get("light.kitchen")
```

### 5.3 Device Registry

```python
from homeassistant.helpers import device_registry as dr

registry = dr.async_get(hass)

# Create device
device = registry.async_get_or_create(
    config_entry_id=config_entry.entry_id,
    identifiers={(DOMAIN, device_id)},
    name="Hue Bridge",
)
```

### 5.4 Storage Helper

```python
from homeassistant.helpers.storage import Store

store = Store(hass, version=1, key="my_integration.data")

# Save
await store.async_save({"last_sync": "2024-01-01"})

# Load
data = await store.async_load()
```

---

## 6. Data Update Coordinator Pattern

Standard pattern for polling data:

```python
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

class MyCoordinator(DataUpdateCoordinator[MyData]):
    def __init__(self, hass, client, config_entry):
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
            config_entry=config_entry,
        )
        self.client = client
    
    async def _async_update_data(self):
        try:
            return await self.client.fetch_data()
        except MyException as err:
            raise UpdateFailed(f"API error: {err}") from err

# Setup
coordinator = MyCoordinator(hass, client, entry)
await coordinator.async_config_entry_first_refresh()
entry.runtime_data = coordinator

# Entity usage
class MyEntity(CoordinatorEntity[MyCoordinator], SensorEntity):
    @property
    def native_value(self):
        return self.coordinator.data["temperature"]
    
    @property
    def available(self):
        return self.coordinator.last_update_success
```

---

## 7. Discovery Mechanisms

Home Assistant automatically discovers integrations via:

**Zeroconf (mDNS):**
```json
"zeroconf": ["_hue._tcp.local."]
```

**DHCP:**
```json
"dhcp": [{"hostname": "hue-*", "macaddress": "1A2B3C*"}]
```

**SSDP (UPnP):**
```json
"ssdp": [{"st": "upnp:rootdevice", "manufacturer": "Philips"}]
```

**Bluetooth:**
```json
"bluetooth": [{"service_uuid": "12345678"}]
```

**USB:**
```json
"usb": [{"vid": "1234", "pid": "5678"}]
```

Discovery flow:
```
Device Detected → Match Manifest Config → 
Fire Discovery Event → async_step_discovery() → 
ConfigEntry Created
```

---

## 8. Config Flow (UI Configuration)

```python
from homeassistant import config_entries
import voluptuous as vol

class MyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 1
    
    async def async_step_user(self, user_input=None):
        """User adds integration manually"""
        if user_input is not None:
            try:
                client = MyClient(user_input[CONF_HOST])
                await client.test_connection()
            except Exception:
                return self.async_show_form(..., errors={"base": "cannot_connect"})
            
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_API_KEY): str,
            }),
        )
    
    async def async_step_discovery(self, discovery_info):
        """Called on device discovery"""
        await self.async_set_unique_id(discovery_info["serial"])
        self._abort_if_unique_id_configured()
        return self.async_show_form(...)
    
    async def async_step_reauth(self, user_input=None):
        """Handle reauthentication"""
        entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return self.async_update_reload_and_abort(
            entry,
            data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]},
            reason="reauth_successful",
        )
```

---

## 9. Security & Isolation

### 9.1 Security Model

Home Assistant has **NO PROCESS-LEVEL SANDBOXING**. All integrations run in same Python process.

**Security mechanisms:**

1. **Import Control** - Blocked integrations list with version constraints
2. **Version Validation** - Custom integrations must declare version
3. **Dependency Isolation** - Single pip installation per dependency
4. **Config Entry Isolation** - Logical separation via unique_id
5. **Permission System** - Admin context required for dangerous operations
6. **Safe Attributes** - Runtime data immutable from outside

### 9.2 Best Practices

- Use `ConfigEntry.runtime_data` for secrets (not `hass.data`)
- Clear sensitive data on unload
- Validate all external input
- Never expose credentials in diagnostics/logs
- Use HTTPS for cloud APIs
- Implement rate limiting

---

## 10. Standard Integration Structure

```
homeassistant/components/my_integration/
├── __init__.py                 # async_setup_entry, async_unload_entry
├── manifest.json               # Metadata
├── const.py                    # Constants
├── config_flow.py              # UI configuration
├── coordinator.py              # Data update coordinator
├── models.py                   # Data classes
├── entity.py                   # Base entity classes
├── strings.json                # Translations
├── services.yaml               # Service definitions
├── sensor.py                   # Sensor platform
├── light.py                    # Light platform
├── diagnostics.py              # Diagnostics export
├── quality_scale.yaml          # Quality scale rules
└── translations/               # i18n
```

### Minimal Integration

```python
# __init__.py
DOMAIN = "my_integration"

async def async_setup_entry(hass, entry):
    """Set up from config entry"""
    client = MyClient(entry.data[CONF_HOST])
    entry.runtime_data = client
    
    await hass.config_entries.async_forward_entry_setups(
        entry, PLATFORMS
    )
    return True

async def async_unload_entry(hass, entry):
    """Unload config entry"""
    return await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
```

---

## 11. Startup & Bootstrap Process

### Bootstrap Stages

```
Stage 0: Core Infrastructure
  ├── Logging & HTTP deps
  ├── Frontend
  ├── Recorder
  ├── Debugger
  └── Zeroconf

Stage 1: Discovery
  ├── Bluetooth
  ├── DHCP
  ├── SSDP
  ├── USB
  └── MQTT Eventstream

Stage 2: Other Integrations
  └── From config.yaml

Wrap-up:
  ├── Automations/Scripts
  ├── EVENT_HOMEASSISTANT_STARTED
  └── System Operational
```

---

## 12. Common Patterns

### Coordinator + Entity

```python
class MyCoordinator(DataUpdateCoordinator[dict]):
    async def _async_update_data(self):
        return await self.client.fetch_data()

class MySensor(CoordinatorEntity[MyCoordinator], SensorEntity):
    @property
    def native_value(self):
        return self.coordinator.data["temperature"]
    
    @property
    def available(self):
        return self.coordinator.last_update_success
```

### Service Registration

```python
async def async_setup(hass, config):
    async def handle_service(call: ServiceCall):
        # ... handle ...
    
    hass.services.async_register(
        DOMAIN, SERVICE_NAME,
        handle_service,
        schema=SCHEMA,
    )
    return True
```

### Event Listener

```python
async def async_setup_entry(hass, entry):
    async def on_event(event):
        await process(event.data)
    
    listener = hass.bus.async_listen(EVENT_NAME, on_event)
    entry.async_on_unload(listener)
```

---

## Summary Table

| Aspect | Details |
|--------|---------|
| **Modularity** | Dynamic loading; platforms on-demand; intelligent caching |
| **Async** | All I/O async; blocking in executor; no event loop blocking |
| **Config** | `data` (persistent) + `options` (user) + `runtime_data` (ephemeral) |
| **State** | StateMachine; EntityRegistry; DeviceRegistry |
| **Discovery** | Zeroconf, DHCP, SSDP, Bluetooth, USB, MQTT |
| **Dependencies** | Graph-based resolution; circular dependency detection |
| **Platforms** | Integration-specific implementations |
| **Lifecycle** | Load → Setup → Running → Unload/Reload |
| **Storage** | hass.data, ConfigEntry, Registries, Storage helper |
| **Security** | No sandboxing; permission system; blocked list |

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `homeassistant/loader.py` | Integration discovery and loading |
| `homeassistant/core.py` | HomeAssistant object, bus, services, states |
| `homeassistant/config_entries.py` | ConfigEntry lifecycle and management |
| `homeassistant/setup.py` | Component setup orchestration |
| `homeassistant/bootstrap.py` | System startup and loading stages |
| `homeassistant/helpers/entity_component.py` | Entity component framework |
| `homeassistant/helpers/update_coordinator.py` | Data update coordinator pattern |
| `homeassistant/helpers/entity_registry.py` | Entity tracking registry |
| `homeassistant/helpers/device_registry.py` | Device tracking registry |
| `homeassistant/helpers/entity.py` | Base entity class |

---

This architecture is designed for:
- **Reliability** - No single integration can crash the system
- **Performance** - Async-first, lazy loading, intelligent caching
- **Flexibility** - Integrate any Python library with proper lifecycle management
- **Extensibility** - Services, events, conditions, triggers, diagnostics

