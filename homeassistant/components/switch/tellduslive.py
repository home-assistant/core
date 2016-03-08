"""
Support for Tellstick switches using Tellstick Net.

This platform uses the Telldus Live online service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tellduslive/

"""
import logging

from homeassistant.components import tellduslive
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Tellstick switches."""
    if discovery_info is None:
        return
    add_devices(TelldusLiveSwitch(switch) for switch in discovery_info)


class TelldusLiveSwitch(ToggleEntity):
    """Representation of a Tellstick switch."""

    def __init__(self, switch_id):
        """Initialize the switch."""
        self._id = switch_id
        self.update()
        _LOGGER.debug("created switch %s", self)

    def update(self):
        """Get the latest date and update the state."""
        tellduslive.NETWORK.update_switches()
        self._switch = tellduslive.NETWORK.get_switch(self._id)

    @property
    def should_poll(self):
        """Polling is needed."""
        return True

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return True

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self._switch["name"]

    @property
    def available(self):
        """Return the state of the switch."""
        return not self._switch.get("offline", False)

    @property
    def is_on(self):
        """Return true if switch is on."""
        from tellive.live import const
        return self._switch["state"] == const.TELLSTICK_TURNON

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        tellduslive.NETWORK.turn_switch_on(self._id)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        tellduslive.NETWORK.turn_switch_off(self._id)
