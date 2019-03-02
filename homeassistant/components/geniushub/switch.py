"""
homeassistant.components.switch.genius
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Implements Genius switches.
"""

import logging
from homeassistant.components.geniushub import GENIUS_HUB
from homeassistant.components.switch import SwitchDevice

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'geniushub'


async def async_setup_platform(hass, config,
                               async_add_entities, discovery_info=None):
    """ Find and return Genius switches """
    switches = []
    genius_hub = hass.data[GENIUS_HUB]
    await genius_hub.getjson('/zones')

    # Get the zones that are switches
    switch_list = genius_hub.getSwitchList()

    for zone in switch_list:
        switches.append(GeniusSwitch(genius_hub, zone))

    async_add_entities(switches)


class GeniusSwitch(SwitchDevice):
    """ Provides a Genius switch. """

    def __init__(self, genius_hub, zone):
        GeniusSwitch._genius_hub = genius_hub
        self._name = zone['name']
        self._device_id = zone['iID']
        mode = zone['mode']
        if mode == 'off':
            self._state = False
        else:
            self._state = True

    @property
    def name(self):
        """ Returns the name of the Genius switch. """
        return self._name

    @property
    def is_on(self):
        """ True if Genius switch is on. """
        return self._state

    async def async_update(self):
        """Get the latest data."""
        zone = GeniusSwitch._genius_hub.getZone(self._device_id)
        if zone:
            mode = GeniusSwitch._genius_hub.GET_MODE(zone)
            if mode == 'off':
                self._state = False
            else:
                self._state = True

    async def async_turn_on(self, **kwargs):
        """ Turn the Genius switch on. """
        duration = 24 * 60 * 60 - (5 * 60)  # 23:55
        await GeniusSwitch._genius_hub.putjson(
            self._device_id, {
                "fBoostSP": 1,
                "iBoostTimeRemaining": duration,
                "iMode": 16})

    async def async_turn_off(self, **kwargs):
        """ Turn the Genius switch off. """
        await GeniusSwitch._genius_hub.putjson(
            self._device_id, {"iMode": 1})
