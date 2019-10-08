"""Support for Supla cover - curtains, rollershutters etc."""
import logging
from pprint import pformat

from homeassistant.components.switch import SwitchDevice
from homeassistant.components.supla import SuplaChannel

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_devices):
    async_add_devices([SuplaSwitch(device) for device in config_entry.data])


def setup_platform(hass, config, add_entities, discovery_info=None):
    _LOGGER.warning("Loading SUPLA via platform config is deprecated")
    """Set up the Supla switches."""
    if discovery_info is None:
        return

    _LOGGER.debug("Discovery: %s", pformat(discovery_info))

    add_entities([SuplaSwitch(device) for device in discovery_info])


class SuplaSwitch(SuplaChannel, SwitchDevice):
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
