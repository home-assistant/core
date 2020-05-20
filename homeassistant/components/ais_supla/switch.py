"""Support for Supla switch"""
from datetime import timedelta
import logging

from homeassistant.components.ais_supla import SuplaChannel
from homeassistant.components.switch import SwitchEntity

from .const import CONF_CHANNELS, CONF_SERVER, DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up an SUPLA switch based on existing config."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    server = hass.data[DOMAIN][CONF_SERVER][config_entry.entry_id]
    channels = hass.data[DOMAIN][CONF_CHANNELS]["switch"]
    scan_interval_in_sec = 60
    if "scan_interval" in config_entry.data:
        scan_interval_in_sec = config_entry.data["scan_interval"]
    async_add_entities(
        [SuplaSwitch(device, server, scan_interval_in_sec) for device in channels]
    )


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
