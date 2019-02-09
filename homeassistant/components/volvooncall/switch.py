"""
Support for Volvo heater.

This platform uses the Volvo online service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.volvooncall/
"""
import logging

from homeassistant.components.volvooncall import VolvoEntity, DATA_KEY
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up a Volvo switch."""
    if discovery_info is None:
        return
    async_add_entities([VolvoSwitch(hass.data[DATA_KEY], *discovery_info)])


class VolvoSwitch(VolvoEntity, ToggleEntity):
    """Representation of a Volvo switch."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.instrument.state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.instrument.turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.instrument.turn_off()
