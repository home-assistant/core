# Number Platform Reference

## Overview

Number entities allow users to control numeric values within a defined range. They're used for settings like volume, brightness, temperature setpoints, or any numeric configuration parameter.

## Basic Number Implementation

```python
"""Number platform for my_integration."""
from homeassistant.components.number import NumberEntity, NumberMode
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
    """Set up numbers."""
    coordinator = entry.runtime_data

    async_add_entities(
        MyNumber(coordinator, device_id)
        for device_id in coordinator.data.devices
    )


class MyNumber(MyEntity, NumberEntity):
    """Representation of a number."""

    _attr_has_entity_name = True
    _attr_translation_key = "volume"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1

    def __init__(self, coordinator: MyCoordinator, device_id: str) -> None:
        """Initialize the number."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_volume"

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if device := self.coordinator.data.devices.get(self.device_id):
            return device.volume
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.coordinator.client.set_volume(self.device_id, int(value))
        await self.coordinator.async_request_refresh()
```

## Number Properties

### Core Properties

```python
class MyNumber(NumberEntity):
    """Number with all common properties."""

    # Basic identification
    _attr_has_entity_name = True
    _attr_translation_key = "brightness"
    _attr_unique_id = "device_123_brightness"

    # Value range and step
    _attr_native_min_value = 0
    _attr_native_max_value = 255
    _attr_native_step = 1  # or 0.1 for decimals

    # Unit of measurement
    _attr_native_unit_of_measurement = PERCENTAGE  # or other units

    # Display mode
    _attr_mode = NumberMode.SLIDER  # or NumberMode.BOX, NumberMode.AUTO

    # Entity category
    _attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self) -> float | None:
        """Return current value."""
        return self.device.brightness

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.device.set_brightness(int(value))
```

### Required Properties

```python
# Minimum value
_attr_native_min_value = 0

# Maximum value
_attr_native_max_value = 100

# Step size (precision)
_attr_native_step = 1  # Integers
_attr_native_step = 0.1  # One decimal place
_attr_native_step = 0.01  # Two decimal places
```

### Current Value

```python
@property
def native_value(self) -> float | None:
    """Return the current value."""
    return self.device.current_value

# Or use attribute
_attr_native_value = 50.0
```

### Set Value Method

```python
async def async_set_native_value(self, value: float) -> None:
    """Update to new value."""
    await self.device.set_value(value)
    # Update state
    self._attr_native_value = value
    self.async_write_ha_state()
```

## Display Mode

Control how the number is displayed in the UI:

```python
from homeassistant.components.number import NumberMode

# Slider (default for ranges)
_attr_mode = NumberMode.SLIDER

# Input box (better for precise values or large ranges)
_attr_mode = NumberMode.BOX

# Auto (let HA decide based on range)
_attr_mode = NumberMode.AUTO
```

**When to use each**:
- `SLIDER`: Small ranges (0-100), settings like volume/brightness
- `BOX`: Large ranges, precise values, IDs or codes
- `AUTO`: Let Home Assistant decide (default)

## Device Class

Use device classes for proper representation:

```python
from homeassistant.components.number import NumberDeviceClass

# Common device classes
_attr_device_class = NumberDeviceClass.TEMPERATURE
_attr_device_class = NumberDeviceClass.HUMIDITY
_attr_device_class = NumberDeviceClass.VOLTAGE
_attr_device_class = NumberDeviceClass.CURRENT
_attr_device_class = NumberDeviceClass.POWER
_attr_device_class = NumberDeviceClass.BATTERY
_attr_device_class = NumberDeviceClass.DISTANCE
_attr_device_class = NumberDeviceClass.DURATION
```

## Units of Measurement

```python
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
)

# Percentage (0-100)
_attr_native_unit_of_measurement = PERCENTAGE

# Temperature
_attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

# Time
_attr_native_unit_of_measurement = UnitOfTime.SECONDS

# Custom units
_attr_native_unit_of_measurement = "dB"  # Decibels
```

## Entity Descriptions Pattern

For multiple number entities:

```python
from dataclasses import dataclass
from collections.abc import Awaitable, Callable

from homeassistant.components.number import NumberEntityDescription, NumberMode


@dataclass(frozen=True, kw_only=True)
class MyNumberDescription(NumberEntityDescription):
    """Describes a number."""
    value_fn: Callable[[MyData], float | None]
    set_fn: Callable[[MyClient, str, float], Awaitable[None]]


NUMBERS: tuple[MyNumberDescription, ...] = (
    MyNumberDescription(
        key="volume",
        translation_key="volume",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.volume,
        set_fn=lambda client, device_id, value: client.set_volume(device_id, int(value)),
    ),
    MyNumberDescription(
        key="temperature_setpoint",
        translation_key="temperature_setpoint",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=16,
        native_max_value=30,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.SLIDER,
        value_fn=lambda data: data.target_temperature,
        set_fn=lambda client, device_id, value: client.set_temperature(device_id, value),
    ),
)


class MyNumber(MyEntity, NumberEntity):
    """Number using entity description."""

    entity_description: MyNumberDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        device_id: str,
        description: MyNumberDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return current value."""
        if device := self.coordinator.data.devices.get(self.device_id):
            return self.entity_description.value_fn(device)
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.entity_description.set_fn(
            self.coordinator.client,
            self.device_id,
            value,
        )
        await self.coordinator.async_request_refresh()
```

## Value Validation

Home Assistant validates against min/max/step, but you can add custom validation:

```python
async def async_set_native_value(self, value: float) -> None:
    """Set value with custom validation."""
    # Custom validation
    if value % 5 != 0:
        raise ValueError("Value must be multiple of 5")

    await self.device.set_value(value)
    await self.coordinator.async_request_refresh()
```

## State Update Patterns

### Pattern 1: Optimistic Update

```python
async def async_set_native_value(self, value: float) -> None:
    """Set value with optimistic update."""
    # Update immediately
    self._attr_native_value = value
    self.async_write_ha_state()

    try:
        await self.device.set_value(value)
    except DeviceError:
        # Revert on error
        await self.coordinator.async_request_refresh()
        raise
```

### Pattern 2: Coordinator Refresh

```python
async def async_set_native_value(self, value: float) -> None:
    """Set value and refresh."""
    await self.device.set_value(value)
    # Get actual value from device
    await self.coordinator.async_request_refresh()
```

### Pattern 3: Direct State Update

```python
async def async_set_native_value(self, value: float) -> None:
    """Set value with direct state update."""
    new_value = await self.device.set_value(value)
    # Device returns actual value
    self._attr_native_value = new_value
    self.async_write_ha_state()
```

## Testing Numbers

### Snapshot Testing

```python
"""Test numbers."""
import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_numbers(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    init_integration,
) -> None:
    """Test number entities."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )
```

### Value Testing

```python
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)


async def test_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device,
) -> None:
    """Test setting number value."""
    await init_integration(hass, mock_config_entry)

    # Check initial value
    state = hass.states.get("number.my_device_volume")
    assert state
    assert state.state == "50"
    assert state.attributes["min"] == 0
    assert state.attributes["max"] == 100
    assert state.attributes["step"] == 1

    # Set new value
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.my_device_volume",
            ATTR_VALUE: 75,
        },
        blocking=True,
    )

    mock_device.set_volume.assert_called_once_with(75)

    # Verify state updated
    state = hass.states.get("number.my_device_volume")
    assert state.state == "75"
```

## Common Number Types

### Volume Control

```python
class VolumeNumber(NumberEntity):
    """Volume control."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
```

### Temperature Setpoint

```python
class TemperatureNumber(NumberEntity):
    """Temperature setpoint."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_min_value = 16.0
    _attr_native_max_value = 30.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.SLIDER
```

### Duration Setting

```python
class DurationNumber(NumberEntity):
    """Duration setting."""

    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_min_value = 0
    _attr_native_max_value = 3600
    _attr_native_step = 60  # 1 minute steps
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX
```

## Best Practices

### ✅ DO

- Set appropriate min/max/step values
- Use device class when available
- Use standard units
- Set display mode appropriately
- Implement unique IDs
- Use translation keys
- Mark config numbers with entity_category
- Handle value updates properly

### ❌ DON'T

- Allow invalid ranges (min > max)
- Use zero or negative step
- Block the event loop
- Ignore validation errors
- Create numbers without min/max/step
- Hardcode entity names
- Use for binary values (use switch)
- Use for selection from list (use select)

## Troubleshooting

### Number Not Appearing

Check:
- [ ] Unique ID is set
- [ ] Platform is in PLATFORMS list
- [ ] min/max/step are all set
- [ ] Entity is added with async_add_entities

### Value Not Updating

Check:
- [ ] async_set_native_value is called
- [ ] Coordinator refresh is working
- [ ] native_value returns correct value
- [ ] Value is within min/max range

### UI Shows Wrong Control Type

Check:
- [ ] mode is set correctly
- [ ] Range is appropriate for mode
- [ ] Step size is reasonable

## Quality Scale Considerations

- **Bronze**: Unique ID required
- **Gold**: Entity translations, device class, entity category
- **Platinum**: Full type hints

## References

- [Number Documentation](https://developers.home-assistant.io/docs/core/entity/number)
- [Number Integration](https://www.home-assistant.io/integrations/number/)
