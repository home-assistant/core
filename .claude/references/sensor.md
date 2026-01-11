# Sensor Platform Reference

## Overview

Sensors are read-only entities that represent measurements, states, or information from devices and services. They display numeric values, strings, timestamps, or other data types.

## Basic Sensor Implementation

### Minimal Sensor

```python
"""Sensor platform for my_integration."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyConfigEntry
from .const import DOMAIN
from .coordinator import MyCoordinator
from .entity import MyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        MySensor(coordinator, device_id)
        for device_id in coordinator.data.devices
    )


class MySensor(MyEntity, SensorEntity):
    """Representation of a sensor."""

    def __init__(self, coordinator: MyCoordinator, device_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_temperature"
        self._attr_translation_key = "temperature"

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        if device := self.coordinator.data.devices.get(self.device_id):
            return device.temperature
        return None
```

## Sensor Properties

### Core Properties

```python
class MySensor(SensorEntity):
    """Sensor with all common properties."""

    # Basic identification
    _attr_has_entity_name = True  # Required
    _attr_translation_key = "temperature"  # For translations
    _attr_unique_id = "device_123_temp"  # Required

    # Device class and units
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1  # Decimal places

    # State class for statistics
    _attr_state_class = SensorStateClass.MEASUREMENT

    # Entity category
    _attr_entity_category = EntityCategory.DIAGNOSTIC  # If diagnostic

    # Availability
    _attr_entity_registry_enabled_default = False  # If noisy/less important

    @property
    def native_value(self) -> float | None:
        """Return sensor value."""
        return self.device.temperature

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.device_id in self.coordinator.data
```

## Device Classes

Use device classes for proper representation:

```python
from homeassistant.components.sensor import SensorDeviceClass

# Common device classes
_attr_device_class = SensorDeviceClass.TEMPERATURE
_attr_device_class = SensorDeviceClass.HUMIDITY
_attr_device_class = SensorDeviceClass.PRESSURE
_attr_device_class = SensorDeviceClass.BATTERY
_attr_device_class = SensorDeviceClass.ENERGY
_attr_device_class = SensorDeviceClass.POWER
_attr_device_class = SensorDeviceClass.VOLTAGE
_attr_device_class = SensorDeviceClass.CURRENT
_attr_device_class = SensorDeviceClass.TIMESTAMP
_attr_device_class = SensorDeviceClass.MONETARY
```

Benefits:
- Automatic unit conversion
- Proper UI representation
- Voice assistant integration
- Historical statistics

## State Classes

For long-term statistics support:

```python
from homeassistant.components.sensor import SensorStateClass

# Measurement - value at a point in time
_attr_state_class = SensorStateClass.MEASUREMENT
# Examples: temperature, humidity, power

# Total - cumulative value that can increase/decrease
_attr_state_class = SensorStateClass.TOTAL
# Examples: energy consumed, data transferred
# Use with last_reset for resettable totals

# Total increasing - cumulative value that only increases
_attr_state_class = SensorStateClass.TOTAL_INCREASING
# Examples: lifetime energy, odometer
```

### When to Use State Classes

✅ **Use MEASUREMENT for**:
- Temperature, humidity, pressure
- Current power usage
- Instantaneous values

✅ **Use TOTAL for**:
- Daily/monthly energy consumption (resets)
- Periodic counters

✅ **Use TOTAL_INCREASING for**:
- Lifetime energy consumption
- Monotonically increasing counters

❌ **Don't use state class for**:
- Text/string sensors
- Status sensors (enum values)
- Non-numeric sensors

## Unit of Measurement

### Using Standard Units

```python
from homeassistant.const import (
    UnitOfTemperature,
    UnitOfPower,
    UnitOfEnergy,
    PERCENTAGE,
)

# Temperature
_attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
# Auto-converts to user's preference (°F/°C/K)

# Power
_attr_native_unit_of_measurement = UnitOfPower.WATT

# Energy
_attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

# Percentage
_attr_native_unit_of_measurement = PERCENTAGE
```

### Custom Units

```python
# For non-standard units
_attr_native_unit_of_measurement = "AQI"  # Air Quality Index
_attr_native_unit_of_measurement = "ppm"  # Parts per million
```

## Entity Descriptions Pattern

For multiple similar sensors, use SensorEntityDescription:

```python
from dataclasses import dataclass
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.typing import StateType

@dataclass(frozen=True, kw_only=True)
class MySensorDescription(SensorEntityDescription):
    """Describes a sensor."""
    value_fn: Callable[[MyData], StateType]


SENSORS: tuple[MySensorDescription, ...] = (
    MySensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.temperature,
    ),
    MySensorDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.humidity,
    ),
)


class MySensor(MyEntity, SensorEntity):
    """Sensor using entity description."""

    entity_description: MySensorDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        description: MySensorDescription,
        device_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        if device := self.coordinator.data.devices.get(self.device_id):
            return self.entity_description.value_fn(device)
        return None
```

### Lambda Functions in EntityDescription

When lambdas get long, use proper formatting:

```python
# ❌ Bad - too long
SensorEntityDescription(
    key="temperature",
    value_fn=lambda data: round(data["temp_value"] * 1.8 + 32, 1) if data.get("temp_value") is not None else None,
)

# ✅ Good - wrapped properly
SensorEntityDescription(
    key="temperature",
    value_fn=lambda data: (
        round(data["temp_value"] * 1.8 + 32, 1)
        if data.get("temp_value") is not None
        else None
    ),
)
```

## Timestamp Sensors

For datetime values:

```python
from datetime import datetime
from homeassistant.components.sensor import SensorDeviceClass

class MyTimestampSensor(SensorEntity):
    """Timestamp sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return timestamp."""
        return self.device.last_update
```

## Enum Sensors

For sensors with fixed set of possible values:

```python
from enum import StrEnum
from homeassistant.components.sensor import SensorEntity

class OperationMode(StrEnum):
    """Operation modes."""
    AUTO = "auto"
    MANUAL = "manual"
    ECO = "eco"


class MyModeSensor(SensorEntity):
    """Mode sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [mode.value for mode in OperationMode]

    @property
    def native_value(self) -> str | None:
        """Return current mode."""
        return self.device.mode
```

## Entity Category

Mark diagnostic or configuration sensors:

```python
from homeassistant.helpers.entity import EntityCategory

# Diagnostic sensors (technical info)
_attr_entity_category = EntityCategory.DIAGNOSTIC
# Examples: signal strength, uptime, IP address

# Config sensors (device settings)
_attr_entity_category = EntityCategory.CONFIG
# Examples: current mode setting, configuration values
```

## Disabled by Default

For noisy or less important sensors:

```python
class MySignalStrengthSensor(SensorEntity):
    """Signal strength sensor - noisy."""

    _attr_entity_registry_enabled_default = False
```

## Dynamic Sensor Addition

For devices that appear after setup:

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors with dynamic addition."""
    coordinator = entry.runtime_data
    known_devices: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        """Add newly discovered devices."""
        current_devices = set(coordinator.data.devices.keys())
        new_devices = current_devices - known_devices

        if new_devices:
            known_devices.update(new_devices)
            async_add_entities(
                MySensor(coordinator, device_id)
                for device_id in new_devices
            )

    # Initial setup
    _add_new_devices()

    # Listen for new devices
    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))
```

## Testing Sensors

### Test with Snapshots

```python
"""Test sensors."""
import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    init_integration,
) -> None:
    """Test sensor entities."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )
```

### Test Sensor Values

```python
async def test_sensor_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor values are correct."""
    await init_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.my_device_temperature")
    assert state
    assert state.state == "22.5"
    assert state.attributes["unit_of_measurement"] == "°C"
    assert state.attributes["device_class"] == "temperature"
```

## Best Practices

### ✅ DO

- Use device classes when available
- Set state classes for statistics
- Use standard units of measurement
- Implement unique IDs
- Use entity descriptions for similar sensors
- Mark diagnostic sensors with entity_category
- Disable noisy sensors by default
- Return None for unknown values
- Use translation keys for entity names

### ❌ DON'T

- Hardcode entity names
- Use string "unavailable" or "unknown" as state
- Mix units (always use native_unit_of_measurement)
- Create sensors without unique IDs
- Poll in sensor update if using coordinator
- Block the event loop
- Use state class for non-numeric sensors

## Common Patterns

### Pattern 1: Coordinator-Based Sensor

```python
class MySensor(CoordinatorEntity[MyCoordinator], SensorEntity):
    """Coordinator-based sensor."""

    _attr_should_poll = False  # Coordinator handles updates

    @property
    def native_value(self) -> StateType:
        """Get value from coordinator data."""
        return self.coordinator.data.get(self.key)
```

### Pattern 2: Push-Updated Sensor

```python
class MyPushSensor(SensorEntity):
    """Push-updated sensor."""

    _attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self.async_on_remove(
            self.device.subscribe(self._handle_update)
        )

    @callback
    def _handle_update(self, value: float) -> None:
        """Handle push update."""
        self._attr_native_value = value
        self.async_write_ha_state()
```

### Pattern 3: Calculated Sensor

```python
class MyCalculatedSensor(SensorEntity):
    """Calculated from other sensors."""

    _attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to source sensors."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                ["sensor.source1", "sensor.source2"],
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self, event: Event) -> None:
        """Recalculate when sources change."""
        # Calculate new value
        self._attr_native_value = self._calculate()
        self.async_write_ha_state()
```

## Troubleshooting

### Sensor Not Appearing

Check:
- [ ] Unique ID is set
- [ ] Platform is in PLATFORMS list
- [ ] async_setup_entry is called
- [ ] Entity is added with async_add_entities

### Values Not Updating

Check:
- [ ] Coordinator is updating
- [ ] Entity is available
- [ ] native_value returns correct data
- [ ] should_poll is False for coordinator

### Units Not Converting

Check:
- [ ] Using standard unit constants
- [ ] Device class is set correctly
- [ ] Unit matches device class

### Statistics Not Working

Check:
- [ ] State class is set
- [ ] Values are numeric
- [ ] Device class is appropriate
- [ ] Units are consistent

## Quality Scale Considerations

- **Bronze**: Unique ID required
- **Gold**: Entity translations, device class, entity category
- **Platinum**: Full type hints

## References

- [Sensor Documentation](https://developers.home-assistant.io/docs/core/entity/sensor)
- [Device Classes](https://www.home-assistant.io/integrations/sensor/#device-class)
- [State Classes](https://developers.home-assistant.io/docs/core/entity/sensor/#available-state-classes)
