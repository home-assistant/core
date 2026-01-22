# Select Platform Reference

Select entities allow choosing from a predefined list of options.

## Basic Select

```python
"""Select platform for My Integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyIntegrationConfigEntry
from .entity import MyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up selects from config entry."""
    coordinator = entry.runtime_data

    async_add_entities([
        ModeSelect(coordinator),
    ])


class ModeSelect(MyEntity, SelectEntity):
    """Mode select entity."""

    _attr_options = ["auto", "cool", "heat", "fan_only", "dry"]
    _attr_translation_key = "mode"

    def __init__(self, coordinator: MyCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.serial_number}_mode"

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        return self.coordinator.data.mode

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.coordinator.client.set_mode(option)
        await self.coordinator.async_request_refresh()
```

## Entity Description Pattern

```python
from dataclasses import dataclass
from collections.abc import Callable, Coroutine
from typing import Any

from homeassistant.components.select import SelectEntityDescription


@dataclass(frozen=True, kw_only=True)
class MySelectEntityDescription(SelectEntityDescription):
    """Describe My select entity."""

    current_option_fn: Callable[[MyData], str | None]
    select_option_fn: Callable[[MyClient, str], Coroutine[Any, Any, None]]


SELECTS: tuple[MySelectEntityDescription, ...] = (
    MySelectEntityDescription(
        key="mode",
        translation_key="mode",
        options=["auto", "cool", "heat", "fan_only", "dry"],
        current_option_fn=lambda data: data.mode,
        select_option_fn=lambda client, option: client.set_mode(option),
    ),
    MySelectEntityDescription(
        key="fan_speed",
        translation_key="fan_speed",
        options=["low", "medium", "high", "auto"],
        entity_category=EntityCategory.CONFIG,
        current_option_fn=lambda data: data.fan_speed,
        select_option_fn=lambda client, option: client.set_fan_speed(option),
    ),
)


class MySelect(MyEntity, SelectEntity):
    """Select using entity description."""

    entity_description: MySelectEntityDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        description: MySelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.client.serial_number}_{description.key}"

    @property
    def options(self) -> list[str]:
        """Return available options."""
        return list(self.entity_description.options)

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        return self.entity_description.current_option_fn(self.coordinator.data)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await self.entity_description.select_option_fn(self.coordinator.client, option)
        await self.coordinator.async_request_refresh()
```

## Dynamic Options

```python
class DynamicSelect(MyEntity, SelectEntity):
    """Select with options from device."""

    _attr_translation_key = "preset"

    @property
    def options(self) -> list[str]:
        """Return available presets from device."""
        return self.coordinator.data.available_presets

    @property
    def current_option(self) -> str | None:
        """Return current preset."""
        return self.coordinator.data.current_preset

    async def async_select_option(self, option: str) -> None:
        """Select a preset."""
        await self.coordinator.client.set_preset(option)
        await self.coordinator.async_request_refresh()
```

## Configuration Select

```python
class ConfigSelect(MyEntity, SelectEntity):
    """Configuration select (settings)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = ["silent", "normal", "boost"]
    _attr_translation_key = "performance_mode"

    @property
    def current_option(self) -> str | None:
        """Return current performance mode."""
        return self.coordinator.data.performance_mode

    async def async_select_option(self, option: str) -> None:
        """Set performance mode."""
        await self.coordinator.client.set_performance_mode(option)
        await self.coordinator.async_request_refresh()
```

## Translations

In `strings.json`:

```json
{
  "entity": {
    "select": {
      "mode": {
        "name": "Mode",
        "state": {
          "auto": "Auto",
          "cool": "Cool",
          "heat": "Heat",
          "fan_only": "Fan only",
          "dry": "Dry"
        }
      },
      "fan_speed": {
        "name": "Fan speed",
        "state": {
          "low": "Low",
          "medium": "Medium",
          "high": "High",
          "auto": "Auto"
        }
      },
      "performance_mode": {
        "name": "Performance mode",
        "state": {
          "silent": "Silent",
          "normal": "Normal",
          "boost": "Boost"
        }
      }
    }
  }
}
```

## Icon by State

In `strings.json`:

```json
{
  "entity": {
    "select": {
      "mode": {
        "name": "Mode",
        "default": "mdi:thermostat",
        "state": {
          "auto": "Auto",
          "cool": "Cool",
          "heat": "Heat"
        },
        "state_icons": {
          "auto": "mdi:thermostat-auto",
          "cool": "mdi:snowflake",
          "heat": "mdi:fire"
        }
      }
    }
  }
}
```

Note: State icons are defined in `icons.json`:

```json
{
  "entity": {
    "select": {
      "mode": {
        "default": "mdi:thermostat",
        "state": {
          "auto": "mdi:thermostat-auto",
          "cool": "mdi:snowflake",
          "heat": "mdi:fire"
        }
      }
    }
  }
}
```
