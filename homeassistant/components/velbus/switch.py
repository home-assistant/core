"""Support for Velbus switches."""
import logging

from homeassistant.components.switch import SwitchDevice

from . import DOMAIN as VELBUS_DOMAIN, VelbusEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Velbus Switch platform."""
    if discovery_info is None:
        return
    switches = []
    for switch in discovery_info:
        module = hass.data[VELBUS_DOMAIN].get_module(switch[0])
        channel = switch[1]
        switches.append(VelbusSwitch(module, channel))
    async_add_entities(switches)


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
