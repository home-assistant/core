# Select Entity Reference

## Basic Select

```python
"""Select platform for My Integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyIntegrationConfigEntry
from .entity import MyEntity


SELECTS: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="mode",
        options=["auto", "heat", "cool", "fan"],
        translation_key="mode",
    ),
    SelectEntityDescription(
        key="preset",
        options=["home", "away", "sleep", "eco"],
        translation_key="preset",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up selects from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        MySelect(coordinator, description)
        for description in SELECTS
    )


class MySelect(MyEntity, SelectEntity):
    """Representation of a select."""

    entity_description: SelectEntityDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        description: SelectEntityDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        return self.coordinator.data.get(self.entity_description.key)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await self.coordinator.client.async_set_option(
            self.entity_description.key, option
        )
        await self.coordinator.async_request_refresh()
```

## Dynamic Options

```python
class MySelect(MyEntity, SelectEntity):
    """Select with dynamic options."""

    @property
    def options(self) -> list[str]:
        """Return available options."""
        return self.coordinator.data.available_modes

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        return self.coordinator.data.current_mode
```

## Option Translations

In `strings.json`:

```json
{
  "entity": {
    "select": {
      "mode": {
        "name": "Mode",
        "state": {
          "auto": "Automatic",
          "heat": "Heating",
          "cool": "Cooling",
          "fan": "Fan only"
        }
      }
    }
  }
}
```

## Configuration Selects

```python
from homeassistant.const import EntityCategory

SelectEntityDescription(
    key="language",
    options=["en", "de", "fr", "es"],
    entity_category=EntityCategory.CONFIG,
    translation_key="language",
)
```
