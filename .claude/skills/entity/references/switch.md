# Switch Entity Reference

## Basic Switch

```python
"""Switch platform for My Integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyIntegrationConfigEntry
from .entity import MyEntity


SWITCHES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="power",
        translation_key="power",
    ),
    SwitchEntityDescription(
        key="child_lock",
        translation_key="child_lock",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        MySwitch(coordinator, description)
        for description in SWITCHES
    )


class MySwitch(MyEntity, SwitchEntity):
    """Representation of a switch."""

    entity_description: SwitchEntityDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        return self.coordinator.data.get(self.entity_description.key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.client.async_set_state(
            self.entity_description.key, True
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.client.async_set_state(
            self.entity_description.key, False
        )
        await self.coordinator.async_request_refresh()
```

## Device Classes

| Class | Use For |
|-------|---------|
| `OUTLET` | Wall outlet |
| `SWITCH` | Generic switch (default) |

```python
from homeassistant.components.switch import SwitchDeviceClass

SwitchEntityDescription(
    key="outlet",
    device_class=SwitchDeviceClass.OUTLET,
)
```

## Optimistic Updates

For faster UI response:

```python
async def async_turn_on(self, **kwargs: Any) -> None:
    """Turn the switch on."""
    self._attr_is_on = True
    self.async_write_ha_state()

    await self.coordinator.client.async_set_state(True)
    await self.coordinator.async_request_refresh()
```
