"""Support for the Roku remote."""
import requests.exceptions
from roku import Roku

from homeassistant.components.remote import RemoteDevice
from homeassistant.const import CONF_IP_ADDRESS
from .const import (
    DEFAULT_MANUFACTURER,
    DOMAIN as ROKU_DOMAIN,
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Roku remote platform."""
    if not discovery_info:
        return

    ip_address = discovery_info[CONF_IP_ADDRESS]
    async_add_entities([RokuRemote(ip_address)], True)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Load Roku remote based on a config entry."""
    ip_address = config_entry[CONF_IP_ADDRESS]
    async_add_entities([RokuRemote(ip_address)], True)


class RokuRemote(RemoteDevice):
    """Device that sends commands to an Roku."""

    def __init__(self, host):
        """Initialize the Roku device."""

        self.roku = Roku(host)
        self._device_info = {}

    def update(self):
        """Retrieve latest state."""
        try:
            self._device_info = self.roku.device_info
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
            pass

    @property
    def name(self):
        """Return the name of the device."""
        if self._device_info.user_device_name:
            return self._device_info.user_device_name
        return f"Roku {self._device_info.serial_num}"

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._device_info.serial_num

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": self.name,
            "identifiers": {(ROKU_DOMAIN, self.unique_id)},
            "manufacturer": DEFAULT_MANUFACTURER,
            "model": self._device_info.model_num,
            "sw_version": self._device_info.software_version,
            "via_device": (ROKU_DOMAIN, self.unique_id),
        }

    @property
    def is_on(self):
        """Return true if device is on."""
        return True

    @property
    def should_poll(self):
        """No polling needed for Roku."""
        return False

    def send_command(self, command, **kwargs):
        """Send a command to one device."""
        for single_command in command:
            if not hasattr(self.roku, single_command):
                continue

            getattr(self.roku, single_command)()
