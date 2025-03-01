"""Support for Velbus select."""

from velbusaio.channels import SelectedProgram

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VelbusConfigEntry
from .entity import VelbusEntity, api_call

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Velbus select based on config_entry."""
    await entry.runtime_data.scan_task
    async_add_entities(
        VelbusSelect(channel)
        for channel in entry.runtime_data.controller.get_all_select()
    )


class VelbusSelect(VelbusEntity, SelectEntity):
    """Representation of a select option for velbus."""

    _channel: SelectedProgram
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        channel: SelectedProgram,
    ) -> None:
        """Initialize a select Velbus entity."""
        super().__init__(channel)
        self._attr_options = self._channel.get_options()
        self._attr_unique_id = f"{self._attr_unique_id}-program_select"

    @api_call
    async def async_select_option(self, option: str) -> None:
        """Update the program on the module."""
        await self._channel.set_selected_program(option)

    @property
    def current_option(self) -> str:
        """Return the selected option."""
        return self._channel.get_selected_program()
