# Button Platform Reference

Button entities trigger actions when pressed.

## Basic Button

```python
"""Button platform for My Integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyIntegrationConfigEntry
from .entity import MyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons from config entry."""
    coordinator = entry.runtime_data

    async_add_entities([
        RestartButton(coordinator),
        IdentifyButton(coordinator),
    ])


class RestartButton(MyEntity, ButtonEntity):
    """Restart button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_translation_key = "restart"

    def __init__(self, coordinator: MyCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.serial_number}_restart"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.client.restart()
```

## Device Classes

| Device Class | Icon | Use Case |
|--------------|------|----------|
| `IDENTIFY` | mdi:crosshairs-question | Flash light/beep to locate device |
| `RESTART` | mdi:restart | Restart the device |
| `UPDATE` | mdi:package-up | Trigger firmware update |

## Entity Description Pattern

```python
from dataclasses import dataclass
from collections.abc import Callable, Coroutine
from typing import Any

from homeassistant.components.button import ButtonDeviceClass, ButtonEntityDescription


@dataclass(frozen=True, kw_only=True)
class MyButtonEntityDescription(ButtonEntityDescription):
    """Describe My button entity."""

    press_fn: Callable[[MyClient], Coroutine[Any, Any, None]]


BUTTONS: tuple[MyButtonEntityDescription, ...] = (
    MyButtonEntityDescription(
        key="restart",
        translation_key="restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda client: client.restart(),
    ),
    MyButtonEntityDescription(
        key="identify",
        translation_key="identify",
        device_class=ButtonDeviceClass.IDENTIFY,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda client: client.identify(),
    ),
    MyButtonEntityDescription(
        key="factory_reset",
        translation_key="factory_reset",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda client: client.factory_reset(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons from config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        MyButton(coordinator, description)
        for description in BUTTONS
    )


class MyButton(MyEntity, ButtonEntity):
    """Button using entity description."""

    entity_description: MyButtonEntityDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        description: MyButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.client.serial_number}_{description.key}"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(self.coordinator.client)
```

## Identify Button

```python
class IdentifyButton(MyEntity, ButtonEntity):
    """Identify button to locate the device."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "identify"

    async def async_press(self) -> None:
        """Flash the device LED to identify it."""
        await self.coordinator.client.identify()
```

## Error Handling

```python
from homeassistant.exceptions import HomeAssistantError


class SafeButton(MyEntity, ButtonEntity):
    """Button with error handling."""

    async def async_press(self) -> None:
        """Handle the button press with error handling."""
        try:
            await self.coordinator.client.perform_action()
        except MyDeviceError as err:
            raise HomeAssistantError(f"Failed to perform action: {err}") from err
```

## Confirmation Buttons

For dangerous operations, consider using a diagnostic category and clear naming:

```python
class FactoryResetButton(MyEntity, ButtonEntity):
    """Factory reset button."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "factory_reset"
    _attr_entity_registry_enabled_default = False  # Disabled by default

    async def async_press(self) -> None:
        """Perform factory reset."""
        await self.coordinator.client.factory_reset()
```

## Translations

In `strings.json`:

```json
{
  "entity": {
    "button": {
      "restart": {
        "name": "Restart"
      },
      "identify": {
        "name": "Identify"
      },
      "factory_reset": {
        "name": "Factory reset"
      }
    }
  }
}
```
