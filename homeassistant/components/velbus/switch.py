"""Support for Velbus switches."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity

from . import VelbusEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Velbus switch based on config_entry."""
    await hass.data[DOMAIN][entry.entry_id]["tsk"]
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    entities = []
    for channel in cntrl.get_all("switch"):
        entities.append(VelbusSwitch(channel))
    async_add_entities(entities)


class VelbusSwitch(VelbusEntity, SwitchEntity):
    """Representation of a switch."""

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._channel.is_on()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        await self._channel.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        await self._channel.turn_off()
