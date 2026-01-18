# Number Entity Reference

## Basic Number

```python
"""Number platform for My Integration."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyIntegrationConfigEntry
from .entity import MyEntity


NUMBERS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="target_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=5,
        native_max_value=35,
        native_step=0.5,
        translation_key="target_temperature",
    ),
    NumberEntityDescription(
        key="brightness",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        translation_key="brightness",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up numbers from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        MyNumber(coordinator, description)
        for description in NUMBERS
    )


class MyNumber(MyEntity, NumberEntity):
    """Representation of a number."""

    entity_description: NumberEntityDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.coordinator.data.get(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.coordinator.client.async_set_value(
            self.entity_description.key, value
        )
        await self.coordinator.async_request_refresh()
```

## Number Modes

| Mode | Display |
|------|---------|
| `AUTO` | Best for the situation (default) |
| `BOX` | Text input box |
| `SLIDER` | Slider control |

## Common Device Classes

| Class | Example Use |
|-------|-------------|
| `TEMPERATURE` | Target temperature |
| `HUMIDITY` | Target humidity |
| `POWER` | Power limit |
| `VOLTAGE` | Voltage setting |

## Configuration Numbers

```python
from homeassistant.const import EntityCategory

NumberEntityDescription(
    key="polling_interval",
    native_min_value=10,
    native_max_value=300,
    native_step=10,
    entity_category=EntityCategory.CONFIG,
    translation_key="polling_interval",
)
```
