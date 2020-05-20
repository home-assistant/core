"""Support for Supla switch."""
import logging
from pprint import pformat

from homeassistant.components.supla import SuplaChannel
from homeassistant.components.switch import SwitchEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Supla switches."""
    if discovery_info is None:
        return

    _LOGGER.debug("Discovery: %s", pformat(discovery_info))

    add_entities([SuplaSwitch(device) for device in discovery_info])


class SuplaSwitch(SuplaChannel, SwitchEntity):
    """Representation of a Supla Switch."""

    def turn_on(self, **kwargs):
        """Turn on the switch."""
        self.action("TURN_ON")

    def turn_off(self, **kwargs):
        """Turn off the switch."""
        self.action("TURN_OFF")

    @property
    def is_on(self):
        """Return true if switch is on."""
        state = self.channel_data.get("state")
        if state:
            return state["on"]
        return False
