"""Remote control support for Apple TV."""

import logging

from homeassistant.components.remote import RemoteEntity
from homeassistant.const import CONF_NAME

from . import AppleTVEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Load Apple TV remote based on a config entry."""
    name = config_entry.data[CONF_NAME]
    manager = hass.data[DOMAIN][config_entry.unique_id]
    async_add_entities([AppleTVRemote(name, config_entry.unique_id, manager)])


class AppleTVRemote(AppleTVEntity, RemoteEntity):
    """Device that sends commands to an Apple TV."""

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.atv is not None

    @property
    def should_poll(self):
        """No polling needed for Apple TV."""
        return False

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self.manager.connect()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self.manager.disconnect()

    async def async_send_command(self, command, **kwargs):
        """Send a command to one device."""
        if not self.is_on:
            _LOGGER.error("Unable to send commands, not connected to %s", self._name)
            return

        for single_command in command:
            if not hasattr(self.atv.remote_control, single_command):
                continue

            await getattr(self.atv.remote_control, single_command)()
