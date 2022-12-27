"""Button platform for CoolMasterNet integration."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import CoolmasterEntity, async_add_entities_for_platform


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the CoolMasterNet button platform."""
    async_add_entities_for_platform(
        hass, config_entry, async_add_entities, CoolmasterResetFilter
    )


class CoolmasterResetFilter(CoolmasterEntity, ButtonEntity):
    """Reset the clean filter timer (once filter was cleaned)."""

    _attr_has_entity_name = True
    entity_description = ButtonEntityDescription(
        key="reset_filter",
        entity_category=EntityCategory.CONFIG,
        name="Reset filter",
        icon="mdi:air-filter",
    )

    async def async_press(self) -> None:
        """Press the button."""
        await self._unit.reset_filter()
        await self.coordinator.async_refresh()
