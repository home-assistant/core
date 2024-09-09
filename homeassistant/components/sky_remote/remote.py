"""Home Assistant integration to control a sky box using the remote platform."""

from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RemoteControl

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sky remote platform."""
    host = config.data[CONF_HOST]
    port = config.data[CONF_PORT]
    _LOGGER.debug("Setting up Host: %s, Port: %s", host, port)
    async_add_entities([SkyRemote(host, port, config.entry_id)], True)


class SkyRemote(RemoteEntity):
    """Representation of a Sky Remote."""

    def __init__(self, host, port, unique_id) -> None:
        """Initialize the Sky Remote."""
        self._remote = RemoteControl(host, port)
        self._is_on = True
        self._attr_unique_id = unique_id
        self._attr_name = host

    def turn_on(self, activity: str | None = None, **kwargs: Any) -> None:
        """Send the power on command."""
        self.send_command(["sky"])

    def turn_off(self, activity: str | None = None, **kwargs: Any) -> None:
        """Send the power command."""
        self.send_command(["power"])

    def send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a list of commands to the device."""
        try:
            self._remote.send_keys(command)
            _LOGGER.debug("Successfully sent command %s", command)
        except ValueError as err:
            _LOGGER.error("Invalid command: %s. Error: %s", command, err)
