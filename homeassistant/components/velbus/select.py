"""Support for Velbus select."""

from velbusaio.channels import SelectedProgram

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import VelbusEntity, api_call


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Velbus select based on config_entry."""
    await hass.data[DOMAIN][entry.entry_id]["tsk"]
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    async_add_entities(VelbusSelect(channel) for channel in cntrl.get_all("select"))


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
