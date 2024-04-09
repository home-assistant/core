"""Support for Spa Client switches."""

from typing import Any

from pybalboa import SpaClient, SpaControl
from pybalboa.enums import LowHighRange, UnknownState

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BalboaEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the spa switch entity."""
    spa: SpaClient = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BalboaTempRangeSwitchEntity(spa.temperature_range)])


class BalboaTempRangeSwitchEntity(BalboaEntity, SwitchEntity):
    """Representation of a Temperature Range switch."""

    _attr_icon = "mdi:thermometer-lines"

    def __init__(self, control: SpaControl) -> None:
        """Initialise the switch."""
        super().__init__(control.client, "TempHiLow")
        self._attr_translation_key = "temperature_range"
        self._control = control

    @property
    def is_on(self) -> bool | None:
        """Get whether the temperature range switch is in on state."""
        if self._control.state == UnknownState.UNKNOWN:
            return None
        return self._control.state != LowHighRange.LOW

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the on command."""
        await self._client.set_temperature_range(LowHighRange.HIGH)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the off command."""
        await self._client.set_temperature_range(LowHighRange.LOW)
