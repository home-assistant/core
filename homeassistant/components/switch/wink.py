"""
Support for Wink switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.wink/
"""
import asyncio
import logging

from homeassistant.components.wink import DOMAIN, WinkDevice
from homeassistant.helpers.entity import ToggleEntity

DEPENDENCIES = ['wink']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Wink platform."""
    import pywink

    for switch in pywink.get_switches():
        _id = switch.object_id() + switch.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_entities([WinkToggleDevice(switch, hass)])
    for switch in pywink.get_powerstrips():
        _id = switch.object_id() + switch.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_entities([WinkToggleDevice(switch, hass)])
    for sprinkler in pywink.get_sprinklers():
        _id = sprinkler.object_id() + sprinkler.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_entities([WinkToggleDevice(sprinkler, hass)])
    for switch in pywink.get_binary_switch_groups():
        _id = switch.object_id() + switch.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_entities([WinkToggleDevice(switch, hass)])


class WinkToggleDevice(WinkDevice, ToggleEntity):
    """Representation of a Wink toggle device."""

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN]['entities']['switch'].append(self)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.wink.state()

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.wink.set_state(True)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.wink.set_state(False)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = super(WinkToggleDevice, self).device_state_attributes
        try:
            event = self.wink.last_event()
            if event is not None:
                attributes["last_event"] = event
        except AttributeError:
            pass
        return attributes
