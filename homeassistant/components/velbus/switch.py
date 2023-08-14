"""Support for Velbus switches."""
from typing import Any

from velbusaio.channels import Relay as VelbusRelay

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import VelbusEntity, api_call


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    await hass.data[DOMAIN][entry.entry_id]["tsk"]
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    entities = []
    for channel in cntrl.get_all("switch"):
        entities.append(VelbusSwitch(channel))
    async_add_entities(entities)


class VelbusSwitch(VelbusEntity, SwitchEntity):
    """Representation of a switch."""

    _channel: VelbusRelay

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._channel.is_on()

    @api_call
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        await self._channel.turn_on()

    @api_call
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        await self._channel.turn_off()
