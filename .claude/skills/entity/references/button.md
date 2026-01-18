# Button Entity Reference

## Basic Button

```python
"""Button platform for My Integration."""

from __future__ import annotations

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyIntegrationConfigEntry
from .entity import MyEntity


BUTTONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="restart",
        device_class=ButtonDeviceClass.RESTART,
        translation_key="restart",
    ),
    ButtonEntityDescription(
        key="identify",
        device_class=ButtonDeviceClass.IDENTIFY,
        translation_key="identify",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        MyButton(coordinator, description)
        for description in BUTTONS
    )


class MyButton(MyEntity, ButtonEntity):
    """Representation of a button."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    async def async_press(self) -> None:
        """Handle button press."""
        await self.coordinator.client.async_trigger_action(
            self.entity_description.key
        )
```

## Device Classes

| Class | Use For |
|-------|---------|
| `IDENTIFY` | Identify device (blink LED, beep) |
| `RESTART` | Restart/reboot device |
| `UPDATE` | Trigger firmware update |

## Configuration Buttons

```python
from homeassistant.const import EntityCategory

ButtonEntityDescription(
    key="restart",
    device_class=ButtonDeviceClass.RESTART,
    entity_category=EntityCategory.CONFIG,
    translation_key="restart",
)
```
