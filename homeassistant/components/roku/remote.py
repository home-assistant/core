"""Support for the Roku remote."""
from typing import Callable, List

from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    ReadTimeout as RequestsReadTimeout,
)
from roku import RokuException

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from .const import DATA_CLIENT, DEFAULT_MANUFACTURER, DOMAIN


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List, bool], None],
) -> bool:
    """Load Roku remote based on a config entry."""
    roku = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    async_add_entities([RokuRemote(roku)], True)


class RokuRemote(RemoteEntity):
    """Device that sends commands to an Roku."""

    def __init__(self, roku):
        """Initialize the Roku device."""
        self.roku = roku
        self._available = False
        self._device_info = {}

    def update(self):
        """Retrieve latest state."""
        if not self.enabled:
            return

        try:
            self._device_info = self.roku.device_info
            self._available = True
        except (RequestsConnectionError, RequestsReadTimeout, RokuException):
            self._available = False

    @property
    def name(self):
        """Return the name of the device."""
        if self._device_info.user_device_name:
            return self._device_info.user_device_name
        return f"Roku {self._device_info.serial_num}"

    @property
    def available(self):
        """Return if able to retrieve information from device or not."""
        return self._available

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._device_info.serial_num

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": DEFAULT_MANUFACTURER,
            "model": self._device_info.model_num,
            "sw_version": self._device_info.software_version,
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
