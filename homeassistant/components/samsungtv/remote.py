"""Support for Samsung TV remotes."""
from typing import Iterable

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    DEFAULT_DELAY_SECS,
    RemoteDevice,
)
from homeassistant.const import CONF_ID, CONF_NAME

from .const import DOMAIN, KEY_REMOTE

COMMAND_RETRY_COUNT = 2


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the remote."""
    async_add_entities([SamsungTVRemote(discovery_info)])


class SamsungTVRemote(RemoteDevice):
    """Representation of a Samsung TV remote."""

    def __init__(self, config_entry):
        """Initialize the remote."""
        self._name = config_entry.data.get(CONF_NAME)
        self._uuid = config_entry.data.get(CONF_ID)
        self._entry_id = config_entry.entry_id

    @property
    def _remote(self):
        return self.hass.data[DOMAIN][self._entry_id][KEY_REMOTE]

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    # TODO, need different than media player?
    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._uuid

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return True."""
        return True

    def send_command(self, command: Iterable[str], **kwargs) -> None:
        """Send commands to a device."""
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        for single_command in command:
            self._remote.send_command(single_command, delay)
