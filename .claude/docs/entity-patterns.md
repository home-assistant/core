# Entity Development Patterns

## Unique IDs

Every entity must have a unique ID for registry tracking.

**Requirements**:
- Must be unique per platform (not per integration)
- Don't include integration domain or platform in ID

**Implementation**:
```python
class MySensor(SensorEntity):
    def __init__(self, device_id: str) -> None:
        self._attr_unique_id = f"{device_id}_temperature"
```

**Acceptable ID sources**:
- Device serial numbers
- MAC addresses (use `format_mac` from device registry)
- Physical identifiers (printed/EEPROM)
- Config entry ID as last resort: `f"{entry.entry_id}-battery"`

**Never use**:
- IP addresses, hostnames, URLs
- Device names
- Email addresses, usernames

## Entity Naming

Use `has_entity_name` for proper naming:
```python
class MySensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, device: Device, field: str) -> None:
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=device.name,
        )
        self._attr_name = field  # e.g., "temperature", "humidity"
```

For the device itself, set `_attr_name = None`.

## Entity Availability

Mark entities unavailable when data cannot be fetched:

**Coordinator pattern**:
```python
@property
def available(self) -> bool:
    """Return if entity is available."""
    return super().available and self.identifier in self.coordinator.data
```

**Direct update pattern**:
```python
async def async_update(self) -> None:
    """Update entity."""
    try:
        data = await self.client.get_data()
    except MyException:
        self._attr_available = False
    else:
        self._attr_available = True
        self._attr_native_value = data.value
```

## Event Lifecycle Management

Subscribe in `async_added_to_hass`:
```python
async def async_added_to_hass(self) -> None:
    """Subscribe to events."""
    self.async_on_remove(
        self.client.events.subscribe("my_event", self._handle_event)
    )
```

- Unsubscribe in `async_will_remove_from_hass` if not using `async_on_remove`
- Never subscribe in `__init__` or other methods

## State Handling

- Unknown values: Use `None` (not "unknown" or "unavailable")
- Availability: Implement `available` property instead of using "unavailable" state

## Entity Descriptions

For multiline lambdas, wrap in parentheses:
```python
SensorEntityDescription(
    key="temperature",
    name="Temperature",
    value_fn=lambda data: (
        round(data["temp_value"] * 1.8 + 32, 1)
        if data.get("temp_value") is not None
        else None
    ),
)
```

## Conditional Entity Creation

### supported_fn Pattern

Filter entities based on device capabilities at setup time:
```python
from collections.abc import Callable
from dataclasses import dataclass

@dataclass(frozen=True, kw_only=True)
class MyEntityDescription(SensorEntityDescription):
    """Entity description with conditional support."""

    supported_fn: Callable[[MyCoordinator], bool] = lambda _: True


ENTITIES = (
    MyEntityDescription(
        key="steam_level",
        supported_fn=lambda coord: coord.device.model in ("Pro", "Premium"),
    ),
)

# In async_setup_entry:
async_add_entities(
    MyEntity(coordinator, desc)
    for desc in ENTITIES
    if desc.supported_fn(coordinator)
)
```

### available_fn Pattern

Dynamic availability based on runtime state:
```python
@dataclass(frozen=True, kw_only=True)
class MyEntityDescription(SensorEntityDescription):
    """Entity description with dynamic availability."""

    available_fn: Callable[[MyCoordinator], bool] = lambda _: True


ENTITIES = (
    MyEntityDescription(
        key="brewing_time",
        # Only available when actively brewing
        available_fn=lambda coord: coord.device.state == "brewing",
    ),
)

# In entity class:
@property
def available(self) -> bool:
    """Return if entity is available."""
    return (
        super().available
        and self.entity_description.available_fn(self.coordinator)
    )
```

## Typed Value Functions

Define `value_fn` with proper type hints matching the data source:

```python
from collections.abc import Callable
from datetime import datetime
from homeassistant.helpers.typing import StateType

# Pattern 1: Accessing coordinator.data dict
value_fn: Callable[[dict[str, Any]], StateType | None]

# Pattern 2: Accessing typed library objects
value_fn: Callable[[MyLibraryDataClass], StateType | datetime | None]

# Pattern 3: Accessing widget/enum-keyed dicts
value_fn: Callable[[dict[WidgetType, BaseWidget]], StateType | None]
```

Usage in entity:
```python
@property
def native_value(self) -> StateType | datetime | None:
    """Return the sensor value."""
    return self.entity_description.value_fn(self.coordinator.data)
```

## Extra State Attributes

- All attribute keys must always be present
- Unknown values: Use `None`
- Provide descriptive attributes

## Entity Categories

Set `_attr_entity_category` for proper categorization:

| Category | Use Case | Examples |
|----------|----------|----------|
| `None` (default) | Primary entity state | Power switch, temperature |
| `EntityCategory.CONFIG` | User-adjustable settings | Target temperature, mode |
| `EntityCategory.DIAGNOSTIC` | Device health/status info | Signal strength, uptime, counters |

**Guidelines**:
- Sensors for internal stats, counters, timers → `DIAGNOSTIC`
- Sensors for measurements users actively monitor → `None`
- Settings/configuration entities → `CONFIG`

```python
from homeassistant.const import EntityCategory

class MySensor(SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
```

Or in entity descriptions:
```python
MySensorEntityDescription(
    key="total_operations",
    entity_category=EntityCategory.DIAGNOSTIC,
    ...
)
```

## Device Classes

Use when available for proper context:
```python
class MyTemperatureSensor(SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
```

Provides: unit conversion, voice control, UI representation

## Disabled by Default

Disable noisy or less popular entities:
```python
class MySignalStrengthSensor(SensorEntity):
    _attr_entity_registry_enabled_default = False
```

## Performance Optimization

```python
# Use __slots__ for memory efficiency
class MySensor(SensorEntity):
    __slots__ = ("_attr_native_value", "_attr_available")

    @property
    def should_poll(self) -> bool:
        """Disable polling when using coordinator."""
        return False
```
