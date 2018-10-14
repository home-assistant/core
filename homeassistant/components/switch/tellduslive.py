"""
Support for Tellstick switches using Tellstick Net.

This platform uses the Telldus Live online service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tellduslive/

"""
import logging

from homeassistant.components.tellduslive import TelldusLiveEntity
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Tellstick switches."""
    if discovery_info is None:
        return
    add_entities(TelldusLiveSwitch(hass, switch) for switch in discovery_info)


class TelldusLiveSwitch(TelldusLiveEntity, ToggleEntity):
    """Representation of a Tellstick switch."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.device.is_on

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.device.turn_on()
        self.changed()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self.device.turn_off()
        self.changed()
