"""Button platform for CoolMasterNet integration."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DATA_INFO, DOMAIN
from .entity import CoolmasterEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the CoolMasterNet button platform."""
    info = hass.data[DOMAIN][config_entry.entry_id][DATA_INFO]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        CoolmasterResetFilter(coordinator, unit_id, info)
        for unit_id in coordinator.data
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
