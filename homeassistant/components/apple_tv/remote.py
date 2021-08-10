"""Remote control support for Apple TV."""

import asyncio
import logging

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
)
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

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self.manager.connect()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self.manager.disconnect()

    async def async_send_command(self, command, **kwargs):
        """Send a command to one device."""
        num_repeats = kwargs[ATTR_NUM_REPEATS]
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)

        if not self.is_on:
            _LOGGER.error("Unable to send commands, not connected to %s", self.name)
            return

        for _ in range(num_repeats):
            for single_command in command:
                attr_value = getattr(self.atv.remote_control, single_command, None)
                if not attr_value:
                    raise ValueError("Command not found. Exiting sequence")

                _LOGGER.info("Sending command %s", single_command)
                await attr_value()
                await asyncio.sleep(delay)
