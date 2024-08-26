"""Home Assistant integration to control a sky box using the remote platform."""

from collections.abc import Iterable
import logging
from typing import Any

from skyboxremote import RemoteControl

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_LEGACY_CONTROL_PORT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sky remote platform."""
    host = config.data[CONF_HOST]
    port = 49160 if not config.data[CONF_LEGACY_CONTROL_PORT] else 5900
    name = config.data[CONF_NAME]
    _LOGGER.debug("Setting up Host: %s, Port: %s", host, port)
    async_add_entities([SkyRemote(host, port, name, config.entry_id)], True)


class SkyRemote(RemoteEntity):
    """Representation of a Sky Remote."""

    def __init__(self, host, port, name, unique_id) -> None:
        """Initialize the Sky Remote."""
        self._remote = RemoteControl(host, port)
        self._is_on = True
        self._name = name
        self._attr_unique_id = unique_id

    @property
    def name(self) -> str:
        """Return the display name of the sky box remote."""
        return self._name

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
