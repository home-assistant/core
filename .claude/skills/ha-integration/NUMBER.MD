# Number Platform Reference

Number entities represent numeric values that can be set.

## Basic Number

```python
"""Number platform for My Integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyIntegrationConfigEntry
from .entity import MyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up numbers from config entry."""
    coordinator = entry.runtime_data

    async_add_entities([
        TargetTemperatureNumber(coordinator),
    ])


class TargetTemperatureNumber(MyEntity, NumberEntity):
    """Target temperature number entity."""

    _attr_native_min_value = 16
    _attr_native_max_value = 30
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.SLIDER
    _attr_translation_key = "target_temperature"

    def __init__(self, coordinator: MyCoordinator) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.serial_number}_target_temp"

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.coordinator.data.target_temperature

    async def async_set_native_value(self, value: float) -> None:
        """Set the target temperature."""
        await self.coordinator.client.set_target_temperature(value)
        await self.coordinator.async_request_refresh()
```

## Number Modes

```python
from homeassistant.components.number import NumberMode

# Slider display in UI
_attr_mode = NumberMode.SLIDER

# Input box display in UI
_attr_mode = NumberMode.BOX

# Auto (slider if range <= 256, else box)
_attr_mode = NumberMode.AUTO
```

## Device Classes

```python
from homeassistant.components.number import NumberDeviceClass

# For temperature settings
_attr_device_class = NumberDeviceClass.TEMPERATURE

# Other device classes
NumberDeviceClass.HUMIDITY
NumberDeviceClass.POWER
NumberDeviceClass.VOLTAGE
NumberDeviceClass.CURRENT
```

## Entity Description Pattern

```python
from dataclasses import dataclass
from collections.abc import Callable, Coroutine
from typing import Any

from homeassistant.components.number import NumberEntityDescription, NumberMode


@dataclass(frozen=True, kw_only=True)
class MyNumberEntityDescription(NumberEntityDescription):
    """Describe My number entity."""

    value_fn: Callable[[MyData], float | None]
    set_value_fn: Callable[[MyClient, float], Coroutine[Any, Any, None]]


NUMBERS: tuple[MyNumberEntityDescription, ...] = (
    MyNumberEntityDescription(
        key="target_temperature",
        translation_key="target_temperature",
        native_min_value=16,
        native_max_value=30,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.SLIDER,
        value_fn=lambda data: data.target_temperature,
        set_value_fn=lambda client, value: client.set_target_temperature(value),
    ),
    MyNumberEntityDescription(
        key="brightness",
        translation_key="brightness",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.brightness,
        set_value_fn=lambda client, value: client.set_brightness(int(value)),
    ),
)


class MyNumber(MyEntity, NumberEntity):
    """Number using entity description."""

    entity_description: MyNumberEntityDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        description: MyNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.client.serial_number}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.entity_description.set_value_fn(self.coordinator.client, value)
        await self.coordinator.async_request_refresh()
```

## Dynamic Min/Max Values

```python
class DynamicRangeNumber(MyEntity, NumberEntity):
    """Number with dynamic range based on device capabilities."""

    _attr_translation_key = "fan_speed"

    @property
    def native_min_value(self) -> float:
        """Return minimum value."""
        return self.coordinator.data.fan_speed_min

    @property
    def native_max_value(self) -> float:
        """Return maximum value."""
        return self.coordinator.data.fan_speed_max

    @property
    def native_step(self) -> float:
        """Return step value."""
        return self.coordinator.data.fan_speed_step or 1
```

## Configuration Number

```python
class ConfigNumber(MyEntity, NumberEntity):
    """Configuration number entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 60
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "min"
    _attr_translation_key = "timeout"

    @property
    def native_value(self) -> float | None:
        """Return the timeout setting."""
        return self.coordinator.data.timeout_minutes

    async def async_set_native_value(self, value: float) -> None:
        """Set the timeout."""
        await self.coordinator.client.set_timeout(int(value))
        await self.coordinator.async_request_refresh()
```

## Translations

In `strings.json`:

```json
{
  "entity": {
    "number": {
      "target_temperature": {
        "name": "Target temperature"
      },
      "brightness": {
        "name": "Brightness"
      },
      "timeout": {
        "name": "Timeout"
      }
    }
  }
}
```
