"""Remote control support for Apple TV."""

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from pyatv.const import InputAction

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_HOLD_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_HOLD_SECS,
    RemoteEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AppleTVEntity, AppleTVManager
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
COMMAND_TO_ATTRIBUTE = {
    "wakeup": ("power", "turn_on"),
    "suspend": ("power", "turn_off"),
    "turn_on": ("power", "turn_on"),
    "turn_off": ("power", "turn_off"),
    "volume_up": ("audio", "volume_up"),
    "volume_down": ("audio", "volume_down"),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load Apple TV remote based on a config entry."""
    name: str = config_entry.data[CONF_NAME]
    # apple_tv config entries always have a unique id
    assert config_entry.unique_id is not None
    manager: AppleTVManager = hass.data[DOMAIN][config_entry.unique_id]
    async_add_entities([AppleTVRemote(name, config_entry.unique_id, manager)])


class AppleTVRemote(AppleTVEntity, RemoteEntity):
    """Device that sends commands to an Apple TV."""

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.atv is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.manager.connect()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.manager.disconnect()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to one device."""
        num_repeats = kwargs[ATTR_NUM_REPEATS]
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        hold_secs = kwargs.get(ATTR_HOLD_SECS, DEFAULT_HOLD_SECS)

        if not self.atv:
            _LOGGER.error("Unable to send commands, not connected to %s", self.name)
            return

        for _ in range(num_repeats):
            for single_command in command:
                attr_value: Any = None
                if attributes := COMMAND_TO_ATTRIBUTE.get(single_command):
                    attr_value = self.atv
                    for attr_name in attributes:
                        attr_value = getattr(attr_value, attr_name, None)
                if not attr_value:
                    attr_value = getattr(self.atv.remote_control, single_command, None)
                if not attr_value:
                    raise ValueError("Command not found. Exiting sequence")

                _LOGGER.info("Sending command %s", single_command)

                if hold_secs >= 1:
                    await attr_value(action=InputAction.Hold)
                else:
                    await attr_value()

                await asyncio.sleep(delay)
