"""Support for Velbus switches."""
import logging

from homeassistant.components.switch import SwitchDevice

from . import VelbusEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Old way."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Velbus switch based on config_entry."""
    cntrl = hass.data[DOMAIN][entry.entry_id]['cntrl']
    modules_data = hass.data[DOMAIN][entry.entry_id]['switch']
    entities = []
    for address, channel in modules_data:
        module = cntrl.get_module(address)
        entities.append(
            VelbusSwitch(module, channel))
    async_add_entities(entities)


class VelbusSwitch(VelbusEntity, SwitchDevice):
    """Representation of a switch."""

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._module.is_on(self._channel)

    def turn_on(self, **kwargs):
        """Instruct the switch to turn on."""
        self._module.turn_on(self._channel)

    def turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
        self._module.turn_off(self._channel)
