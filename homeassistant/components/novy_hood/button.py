"""Button platform for the Novy Hood."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .commands import NovyHoodPower
from .entity import NovyHoodEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Novy Hood button platform."""
    async_add_entities([NovyHoodPowerButton(config_entry)])


class NovyHoodPowerButton(NovyHoodEntity, ButtonEntity):
    """Novy hood remote power button (function unknown; exposed for experimentation)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Power"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_power"

    async def async_press(self) -> None:
        """Send the power-button RF command."""
        await self._async_send(NovyHoodPower())
