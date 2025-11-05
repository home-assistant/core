# Home Assistant Architecture - Quick Reference Guide

## Documentation Files

1. **HA_INTEGRATION_ARCHITECTURE.md** (676 lines)
   - Comprehensive deep-dive into every aspect of the architecture
   - Complete with code examples and patterns
   - Organized into 12 major sections

2. **ARCHITECTURE_ANALYSIS_SUMMARY.txt**
   - Executive summary of findings
   - Key files and locations
   - Design principles and patterns

3. **ARCHITECTURE_QUICK_REFERENCE.md** (this file)
   - Quick lookup guide
   - Common tasks and where to find them

---

## Architecture Overview Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    HOME ASSISTANT CORE                          │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐ │
│  │  EventBus    │  ServiceReg  │  StateMachine│  StateStore  │ │
│  │  (events)    │  (services)  │  (entities)  │  (history)   │ │
│  └──────────────┴──────────────┴──────────────┴──────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              hass.data (HassDict)                         │  │
│  │  Integration-specific data storage                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            ▲
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────────────────┐  ┌────────────────────┐  ┌──────────────────┐
│  INTEGRATION 1    │  │  INTEGRATION 2     │  │ INTEGRATION 3    │
│  (hue lights)     │  │  (weather)         │  │ (custom)         │
│                   │  │                    │  │                  │
│ • Platforms       │  │ • Platforms        │  │ • Platforms      │
│ • ConfigEntry     │  │ • ConfigEntry      │  │ • ConfigEntry    │
│ • runtime_data    │  │ • runtime_data     │  │ • runtime_data   │
│ • Entities        │  │ • Entities         │  │ • Entities       │
│ • Services        │  │ • Services         │  │ • Services       │
└───────────────────┘  └────────────────────┘  └──────────────────┘
```

---

## Finding Information

### I want to understand...

**How integrations load?**
- File: `homeassistant/loader.py` (1,772 lines)
- Section: "1. Integration Loading & Discovery"
- Key classes: `Integration`, `Manifest`

**The ConfigEntry lifecycle?**
- File: `homeassistant/config_entries.py` (147,876 lines)
- Section: "2. Integration Lifecycle"
- Key class: `ConfigEntry`

**How to write a new integration?**
- Section: "10. Standard Integration Structure"
- Section: "12. Common Patterns"
- Look for "Minimal Integration" example

**The hass object and what I can do with it?**
- File: `homeassistant/core.py` (99,399 lines)
- Section: "3. Core HomeAssistant Object & APIs"
- Key methods and properties documented

**How platforms work?**
- Section: "4. Entity & Platform System"
- File: `homeassistant/helpers/entity_component.py`
- Pattern: EntityComponent → Platform → Entities

**Data persistence and registries?**
- Section: "5. Data Persistence & Registries"
- Files: `entity_registry.py`, `device_registry.py`
- Patterns: ConfigEntry layers, Entity/Device tracking

**Device discovery?**
- Section: "7. Discovery Mechanisms"
- Types: Zeroconf, DHCP, SSDP, Bluetooth, USB, MQTT, HomeKit
- Flow: Device Detection → Manifest Match → ConfigFlow → ConfigEntry

**Config flows and UI configuration?**
- Section: "8. Config Flow (UI Configuration)"
- File: Config flows extend `config_entries.ConfigFlow`
- Steps: user, discovery, reauth, reconfigure, import

**Async programming guidelines?**
- Section: "12. Common Patterns" → "Async Programming Patterns"
- Key rule: All I/O must be async
- Executor: For blocking operations

**Security model?**
- Section: "9. Security & Isolation"
- Key insight: No process-level sandboxing
- Security: Import control, version validation, blocked list

**Startup process?**
- Section: "11. Startup & Bootstrap Process"
- File: `homeassistant/bootstrap.py` (37,656 lines)
- Stages: 0 (core), 1 (discovery), 2 (others), wrap-up

**Common integration patterns?**
- Section: "12. Common Patterns"
- Patterns: Coordinator+Entity, Services, Event Listeners, Unique IDs

---

## Key Classes & Where to Find Them

| Class | File | Purpose |
|-------|------|---------|
| `HomeAssistant` | core.py | Main object with event loop, bus, services, states |
| `Integration` | loader.py | Represents a loadable integration |
| `ConfigEntry` | config_entries.py | Persistent configuration storage |
| `Entity` | helpers/entity.py | Base class for all entities |
| `EntityComponent` | helpers/entity_component.py | Manages entities per domain |
| `EventBus` | core.py | Event firing/listening system |
| `ServiceRegistry` | core.py | Service registration/calling |
| `StateMachine` | core.py | Entity state storage |
| `EntityRegistry` | helpers/entity_registry.py | Tracks entities |
| `DeviceRegistry` | helpers/device_registry.py | Tracks devices |
| `DataUpdateCoordinator` | helpers/update_coordinator.py | Data polling pattern |
| `ConfigFlow` | data_entry_flow.py | UI configuration flows |

---

## Common Tasks & Where to Find Solutions

### Task: Write integration __init__.py

```python
DOMAIN = "my_integration"

async def async_setup_entry(hass, entry):
    # See Section 10.2: Minimal Integration
    ...

async def async_unload_entry(hass, entry):
    # See Section 10.2: Minimal Integration
    ...
```
Reference: Section 10.2, 12

### Task: Create entities for integration

```python
class MySensor(CoordinatorEntity[MyCoordinator], SensorEntity):
    # See Section 4.2 & 4.3: Entity Base Class
    # See Section 12: Coordinator + Entity pattern
    ...
```
Reference: Section 4, 12

### Task: Register a service

```python
async def async_setup(hass, config):
    # See Section 12: Service Registration pattern
    ...
```
Reference: Section 3.5, 12

### Task: Add event listener

```python
listener = hass.bus.async_listen(EVENT_NAME, callback)
# See Section 12: Event Listener pattern
```
Reference: Section 3.4, 12

### Task: Store integration data

```python
# Use ConfigEntry.runtime_data for mutable state
entry.runtime_data = {"client": client}

# Use hass.data for shared state
hass.data[DOMAIN] = {...}

# Use Storage helper for persistent non-config data
store = Store(hass, version=1, key="my_integration.data")
```
Reference: Section 5.1

### Task: Create config flow

See full example in Section 8 and Section 2.1 for manifest requirements.

### Task: Understand discovery

See Section 7 for all 7 discovery types (Zeroconf, DHCP, SSDP, Bluetooth, USB, MQTT, HomeKit).

### Task: Handle async/await correctly

- All I/O operations: async
- Blocking I/O: Use `hass.async_add_executor_job()`
- Never block event loop
- See Section 12 for patterns

Reference: Section 3.1, 12

### Task: Debug integration not loading

Check:
1. manifest.json syntax (Section 2.1)
2. Dependency resolution errors (Section 1.1)
3. Integration not in cache (Section 1.1)
4. Custom integration version invalid (Section 1.1)

### Task: Implement data polling

Use DataUpdateCoordinator pattern:

```python
class MyCoordinator(DataUpdateCoordinator[MyData]):
    async def _async_update_data(self):
        # See Section 6
        ...
```
Reference: Section 6

---

## Architecture Patterns Quick Lookup

| Pattern | Location | Example |
|---------|----------|---------|
| Coordinator+Entity | Section 12 | Data polling with shared state |
| Service Registration | Section 12 | Custom service handling |
| Event Listener | Section 12 | React to events |
| Unique ID Dedup | Section 12 | Prevent duplicate ConfigEntries |
| ConfigEntry Setup | Section 2.3 | Integration initialization |
| Config Flow | Section 8 | UI configuration |
| Entity Discovery | Section 4.4 | Platform loading |
| Dependency Injection | Section 13 | Pass hass, config_entry |
| Factory Pattern | Section 13 | Lazy entity/platform creation |
| Registry Pattern | Section 13 | Entity/Device tracking |

---

## File Sizes (for estimation)

| File | Lines | Purpose |
|------|-------|---------|
| homeassistant/loader.py | 1,772 | Integration discovery/loading |
| homeassistant/core.py | 2,000+ | HomeAssistant, bus, services, states |
| homeassistant/config_entries.py | 2,000+ | ConfigEntry lifecycle |
| homeassistant/setup.py | 900+ | Component setup orchestration |
| homeassistant/bootstrap.py | 1,000+ | System startup |
| homeassistant/helpers/entity_component.py | 600+ | Entity management |
| homeassistant/helpers/update_coordinator.py | 400+ | Data update pattern |

---

## Testing Checklist for New Integrations

- [ ] Understand loader.py mechanism (Section 1)
- [ ] Create valid manifest.json (Section 2.1)
- [ ] Implement async_setup_entry (Section 2.3)
- [ ] Implement async_unload_entry (Section 2.3)
- [ ] Design config flow for UI setup (Section 8)
- [ ] Create entities with unique IDs (Section 4.2, 5.2)
- [ ] Use ConfigEntry.runtime_data for mutable state (Section 5.1)
- [ ] Implement data coordinator if polling (Section 6)
- [ ] Handle discovery if applicable (Section 7)
- [ ] All I/O operations async (Section 12)
- [ ] Error handling with specific exceptions
- [ ] Write tests with proper mocking
- [ ] Document integration properly

---

## Key Insight

**Loose Coupling Through Events & Services**

Integrations don't directly reference each other. Instead:
- Integration A fires events: `hass.bus.async_fire(...)`
- Integration B listens: `hass.bus.async_listen(...)`
- Integration A calls service: `hass.services.async_call(...)`
- Integration B handles: `hass.services.async_register(...)`
- Integration A reads state: `hass.states.get(...)`
- Integration B sets state: `hass.states.async_set(...)`

This design allows hundreds of integrations to coexist without dependency hell.

---

## Related Documentation

- CLAUDE.md - Developer guidelines and quality scales (in /home/user/core/)
- Official Docs: https://developers.home-assistant.io/

---

Last Updated: November 4, 2025
Analysis Based On: Home Assistant Core codebase examination
