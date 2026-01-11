# Binary Sensor Platform Reference

## Overview

Binary sensors are read-only entities that represent an on/off, true/false, or open/closed state. They are simpler than regular sensors and don't have units or numeric values.

## Basic Binary Sensor Implementation

```python
"""Binary sensor platform for my_integration."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyConfigEntry
from .coordinator import MyCoordinator
from .entity import MyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        MyBinarySensor(coordinator, device_id)
        for device_id in coordinator.data.devices
    )


class MyBinarySensor(MyEntity, BinarySensorEntity):
    """Representation of a binary sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "motion"
    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(self, coordinator: MyCoordinator, device_id: str) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_motion"

    @property
    def is_on(self) -> bool | None:
        """Return true if motion is detected."""
        if device := self.coordinator.data.devices.get(self.device_id):
            return device.motion_detected
        return None
```

## Binary Sensor State

The core property for binary sensors is `is_on`:

```python
@property
def is_on(self) -> bool | None:
    """Return true if the binary sensor is on."""
    return self.device.is_active

# Alternatively, use attribute
_attr_is_on = True  # or False, or None
```

**State Meaning**:
- `True` / `"on"` - Active/detected/open
- `False` / `"off"` - Inactive/not detected/closed
- `None` - Unknown (displays as "unavailable")

## Device Classes

Binary sensors should use device classes for proper representation:

```python
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

# Common device classes
_attr_device_class = BinarySensorDeviceClass.MOTION
_attr_device_class = BinarySensorDeviceClass.OCCUPANCY
_attr_device_class = BinarySensorDeviceClass.DOOR
_attr_device_class = BinarySensorDeviceClass.WINDOW
_attr_device_class = BinarySensorDeviceClass.OPENING
_attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
_attr_device_class = BinarySensorDeviceClass.BATTERY
_attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
_attr_device_class = BinarySensorDeviceClass.PROBLEM
_attr_device_class = BinarySensorDeviceClass.RUNNING
_attr_device_class = BinarySensorDeviceClass.SMOKE
_attr_device_class = BinarySensorDeviceClass.MOISTURE
_attr_device_class = BinarySensorDeviceClass.LOCK
_attr_device_class = BinarySensorDeviceClass.TAMPER
_attr_device_class = BinarySensorDeviceClass.PLUG
_attr_device_class = BinarySensorDeviceClass.POWER
```

### Device Class Selection Guide

**Detection Sensors**:
- Motion detector → `MOTION`
- Presence detector → `OCCUPANCY`
- Smoke detector → `SMOKE`
- Water leak detector → `MOISTURE`

**Contact Sensors**:
- Door sensor → `DOOR`
- Window sensor → `WINDOW`
- Generic contact → `OPENING`

**Status Sensors**:
- Network connection → `CONNECTIVITY`
- Device running → `RUNNING`
- Low battery → `BATTERY`
- Charging state → `BATTERY_CHARGING`
- Problem/fault → `PROBLEM`
- Tamper detection → `TAMPER`

**Power Sensors**:
- Outlet state → `PLUG`
- Power state → `POWER`
- Lock state → `LOCK`

## Entity Descriptions Pattern

For multiple similar binary sensors:

```python
from dataclasses import dataclass
from collections.abc import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)

@dataclass(frozen=True, kw_only=True)
class MyBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a binary sensor."""
    is_on_fn: Callable[[MyData], bool | None]


BINARY_SENSORS: tuple[MyBinarySensorDescription, ...] = (
    MyBinarySensorDescription(
        key="motion",
        translation_key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        is_on_fn=lambda data: data.motion_detected,
    ),
    MyBinarySensorDescription(
        key="door",
        translation_key="door",
        device_class=BinarySensorDeviceClass.DOOR,
        is_on_fn=lambda data: data.door_open,
    ),
    MyBinarySensorDescription(
        key="battery_low",
        translation_key="battery_low",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.battery_level < 20,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        MyBinarySensor(coordinator, device_id, description)
        for device_id in coordinator.data.devices
        for description in BINARY_SENSORS
    )


class MyBinarySensor(MyEntity, BinarySensorEntity):
    """Binary sensor using entity description."""

    entity_description: MyBinarySensorDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        device_id: str,
        description: MyBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if device := self.coordinator.data.devices.get(self.device_id):
            return self.entity_description.is_on_fn(device)
        return None
```

## Entity Category

Mark diagnostic or configuration binary sensors:

```python
from homeassistant.helpers.entity import EntityCategory

# Diagnostic sensors
_attr_entity_category = EntityCategory.DIAGNOSTIC
# Examples: connectivity, update available, battery low

# Config sensors
_attr_entity_category = EntityCategory.CONFIG
# Examples: configuration status
```

## State Inversion

For some sensors, you may need to invert the logic:

```python
class MyBinarySensor(BinarySensorEntity):
    """Binary sensor with inverted state."""

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        if self.device.is_closed:
            return False  # Closed = off for door sensor
        if self.device.is_open:
            return True   # Open = on for door sensor
        return None
```

## Push-Updated Binary Sensor

For event-driven sensors:

```python
class MyPushBinarySensor(BinarySensorEntity):
    """Push-updated binary sensor."""

    _attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates when added."""
        self.async_on_remove(
            self.device.subscribe_state(self._handle_state_update)
        )

    @callback
    def _handle_state_update(self, state: bool) -> None:
        """Handle state update from device."""
        self._attr_is_on = state
        self.async_write_ha_state()
```

## Testing Binary Sensors

### Snapshot Testing

```python
"""Test binary sensors."""
import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    init_integration,
) -> None:
    """Test binary sensor entities."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )
```

### State Testing

```python
async def test_binary_sensor_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test binary sensor states."""
    await init_integration(hass, mock_config_entry)

    # Test on state
    state = hass.states.get("binary_sensor.my_device_motion")
    assert state
    assert state.state == "on"
    assert state.attributes["device_class"] == "motion"

    # Test off state
    state = hass.states.get("binary_sensor.my_device_door")
    assert state
    assert state.state == "off"
    assert state.attributes["device_class"] == "door"
```

## Common Patterns

### Pattern 1: Coordinator-Based

```python
class MyBinarySensor(CoordinatorEntity[MyCoordinator], BinarySensorEntity):
    """Coordinator-based binary sensor."""

    _attr_should_poll = False

    @property
    def is_on(self) -> bool | None:
        """Get state from coordinator data."""
        if device := self.coordinator.data.devices.get(self.device_id):
            return device.is_active
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.device_id in self.coordinator.data
```

### Pattern 2: Event-Driven

```python
class MyEventBinarySensor(BinarySensorEntity):
    """Event-driven binary sensor."""

    _attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to events."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_event",
                self._handle_event,
            )
        )

    @callback
    def _handle_event(self, event_type: str, active: bool) -> None:
        """Handle incoming event."""
        if event_type == self.event_type:
            self._attr_is_on = active
            self.async_write_ha_state()
```

### Pattern 3: Calculated/Derived

```python
class MyCalculatedBinarySensor(BinarySensorEntity):
    """Binary sensor calculated from other sensors."""

    _attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to source sensors."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                ["sensor.temperature", "sensor.humidity"],
                self._handle_source_update,
            )
        )

    @callback
    def _handle_source_update(self, event: Event) -> None:
        """Recalculate when sources change."""
        temp = self.hass.states.get("sensor.temperature")
        humidity = self.hass.states.get("sensor.humidity")

        if temp and humidity:
            # Example: high comfort if temp 20-25 and humidity 30-60
            temp_ok = 20 <= float(temp.state) <= 25
            humidity_ok = 30 <= float(humidity.state) <= 60
            self._attr_is_on = temp_ok and humidity_ok
            self.async_write_ha_state()
```

## Best Practices

### ✅ DO

- Use appropriate device classes
- Return `None` for unknown state
- Use `is_on` property (not state)
- Implement unique IDs
- Use entity descriptions for similar sensors
- Mark diagnostic sensors with entity_category
- Use translation keys for entity names
- Handle availability properly

### ❌ DON'T

- Return strings like "on"/"off" from is_on
- Use regular Sensor for binary states
- Hardcode entity names
- Create binary sensors without device classes (when available)
- Use unavailable/unknown as state values
- Block the event loop
- Poll unnecessarily (use coordinator or events)

## Disabled by Default

For less important binary sensors:

```python
class MyConnectivitySensor(BinarySensorEntity):
    """Connectivity sensor - diagnostic."""

    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
```

## Troubleshooting

### Binary Sensor Not Appearing

Check:
- [ ] Unique ID is set
- [ ] Platform is in PLATFORMS list
- [ ] Entity is added with async_add_entities
- [ ] is_on returns bool or None (not string)

### State Not Updating

Check:
- [ ] Coordinator is updating (if used)
- [ ] Event subscriptions are working
- [ ] is_on returns correct value
- [ ] async_write_ha_state() is called (push updates)

### Wrong Icon

Check:
- [ ] Device class is set correctly
- [ ] Device class matches sensor purpose
- [ ] Icon translations if using Gold tier

## Quality Scale Considerations

- **Bronze**: Unique ID required
- **Gold**: Entity translations, device class, entity category
- **Platinum**: Full type hints

## References

- [Binary Sensor Documentation](https://developers.home-assistant.io/docs/core/entity/binary-sensor)
- [Device Classes](https://www.home-assistant.io/integrations/binary_sensor/#device-class)
