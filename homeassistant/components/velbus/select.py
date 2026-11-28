"""Support for Velbus select."""

from typing import override

from velbusaio.properties import SelectedProgram

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VelbusConfigEntry
from .entity import VelbusEntity, api_call
from .entity_discovery import async_setup_platform_discovery, discover_select_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Velbus select based on config_entry."""
    await async_setup_platform_discovery(
        hass, entry, async_add_entities, discover_select_entities, Platform.SELECT
    )


class VelbusSelect(VelbusEntity, SelectEntity):
    """Representation of a select option for velbus."""

    _channel: SelectedProgram
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "select_program"

    def __init__(
        self,
        channel: SelectedProgram,
    ) -> None:
        """Initialize a select Velbus entity."""
        super().__init__(channel)
        del self._attr_name
        self._attr_options = self._channel.get_options()

    @api_call
    @override
    async def async_select_option(self, option: str) -> None:
        """Update the program on the module."""
        await self._channel.set_selected_program(option)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected option."""
        return self._channel.get_selected_program()
