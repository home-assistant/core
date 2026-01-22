# Switch Platform Reference

Switches control on/off functionality.

## Basic Switch

```python
"""Switch platform for My Integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyIntegrationConfigEntry
from .entity import MyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches from config entry."""
    coordinator = entry.runtime_data

    async_add_entities([
        PowerSwitch(coordinator),
    ])


class PowerSwitch(MyEntity, SwitchEntity):
    """Power switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_translation_key = "power"

    def __init__(self, coordinator: MyCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.serial_number}_power"

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.coordinator.data.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.client.turn_on()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.client.turn_off()
        await self.coordinator.async_request_refresh()
```

## Device Classes

| Device Class | Use Case |
|--------------|----------|
| `OUTLET` | Electrical outlet |
| `SWITCH` | Generic switch |

## Entity Description Pattern

```python
from dataclasses import dataclass
from collections.abc import Callable, Coroutine
from typing import Any

from homeassistant.components.switch import SwitchEntityDescription


@dataclass(frozen=True, kw_only=True)
class MySwitchEntityDescription(SwitchEntityDescription):
    """Describe My switch entity."""

    is_on_fn: Callable[[MyData], bool | None]
    turn_on_fn: Callable[[MyClient], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[MyClient], Coroutine[Any, Any, None]]


SWITCHES: tuple[MySwitchEntityDescription, ...] = (
    MySwitchEntityDescription(
        key="power",
        translation_key="power",
        device_class=SwitchDeviceClass.SWITCH,
        is_on_fn=lambda data: data.is_on,
        turn_on_fn=lambda client: client.turn_on(),
        turn_off_fn=lambda client: client.turn_off(),
    ),
    MySwitchEntityDescription(
        key="child_lock",
        translation_key="child_lock",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda data: data.child_lock_enabled,
        turn_on_fn=lambda client: client.set_child_lock(True),
        turn_off_fn=lambda client: client.set_child_lock(False),
    ),
)


class MySwitch(MyEntity, SwitchEntity):
    """Switch using entity description."""

    entity_description: MySwitchEntityDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        description: MySwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.client.serial_number}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.turn_on_fn(self.coordinator.client)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.turn_off_fn(self.coordinator.client)
        await self.coordinator.async_request_refresh()
```

## Configuration Switch

```python
class ConfigSwitch(MyEntity, SwitchEntity):
    """Configuration switch (e.g., enable/disable a feature)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "auto_mode"

    @property
    def is_on(self) -> bool | None:
        """Return true if auto mode is enabled."""
        return self.coordinator.data.auto_mode_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable auto mode."""
        await self.coordinator.client.set_auto_mode(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable auto mode."""
        await self.coordinator.client.set_auto_mode(False)
        await self.coordinator.async_request_refresh()
```

## Optimistic Updates

For devices with slow response:

```python
class OptimisticSwitch(MyEntity, SwitchEntity):
    """Switch with optimistic state updates."""

    _attr_assumed_state = True  # Indicates state may not be accurate

    def __init__(self, coordinator: MyCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._optimistic_state: bool | None = None

    @property
    def is_on(self) -> bool | None:
        """Return optimistic state if set, otherwise coordinator state."""
        if self._optimistic_state is not None:
            return self._optimistic_state
        return self.coordinator.data.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on with optimistic update."""
        self._optimistic_state = True
        self.async_write_ha_state()
        try:
            await self.coordinator.client.turn_on()
        finally:
            self._optimistic_state = None
            await self.coordinator.async_request_refresh()
```

## Error Handling

```python
from homeassistant.exceptions import HomeAssistantError


class RobustSwitch(MyEntity, SwitchEntity):
    """Switch with proper error handling."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.coordinator.client.turn_on()
        except MyDeviceError as err:
            raise HomeAssistantError(f"Failed to turn on: {err}") from err

        await self.coordinator.async_request_refresh()
```

## Translations

In `strings.json`:

```json
{
  "entity": {
    "switch": {
      "power": {
        "name": "Power"
      },
      "child_lock": {
        "name": "Child lock"
      },
      "auto_mode": {
        "name": "Auto mode"
      }
    }
  }
}
```
