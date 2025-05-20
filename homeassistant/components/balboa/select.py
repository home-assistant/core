"""Support for Spa Client selects."""

from pybalboa import SpaControl
from pybalboa.enums import LowHighRange

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BalboaConfigEntry
from .entity import BalboaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BalboaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the spa select entity."""
    spa = entry.runtime_data
    async_add_entities([BalboaTempRangeSelectEntity(spa.temperature_range)])


class BalboaTempRangeSelectEntity(BalboaEntity, SelectEntity):
    """Representation of a Temperature Range select."""

    _attr_translation_key = "temperature_range"
    _attr_options = [
        LowHighRange.LOW.name.lower(),
        LowHighRange.HIGH.name.lower(),
    ]

    def __init__(self, control: SpaControl) -> None:
        """Initialise the select."""
        super().__init__(control.client, "TempHiLow")
        self._control = control

    @property
    def current_option(self) -> str | None:
        """Return current select option."""
        if self._control.state == LowHighRange.HIGH:
            return LowHighRange.HIGH.name.lower()
        return LowHighRange.LOW.name.lower()

    async def async_select_option(self, option: str) -> None:
        """Select temperature range high/low mode."""
        if option == LowHighRange.HIGH.name.lower():
            await self._client.set_temperature_range(LowHighRange.HIGH)
        else:
            await self._client.set_temperature_range(LowHighRange.LOW)
