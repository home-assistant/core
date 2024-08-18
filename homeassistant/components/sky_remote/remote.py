"""Home Assistant integration to control a sky box using the remote platform."""

from collections.abc import Iterable
import logging
from typing import Any

from skyboxremote import RemoteControl
import voluptuous as vol

from homeassistant.components.remote import (
    PLATFORM_SCHEMA as REMOTE_PLATFORM_SCHEMA,
    RemoteEntity,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DOMAIN = "sky_remote"

_LOGGER = logging.getLogger(__name__)


DEFAULT_PORT = 49160

PLATFORM_SCHEMA = REMOTE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Sky remote platform."""
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    name = config[CONF_NAME]
    _LOGGER.debug("Setting up Host: %s, Port: %s", host, port)
    add_entities([SkyRemote(host, port, name)])


class SkyRemote(RemoteEntity):
    """Representation of a Sky Remote."""

    def __init__(self, host, port, name) -> None:
        """Initialize the Sky Remote."""
        self._remote = RemoteControl(host, port)
        self._is_on = True
        self._name = name

    @property
    def name(self) -> str:
        """Return the display name of the sky box remote."""
        return self._name

    def turn_on(self, activity: str | None = None, **kwargs: Any) -> None:
        """Send the power on command."""
        self.send_command(["sky"])

    def turn_off(self, activity: str | None = None, **kwargs: Any) -> None:
        """Send the power on command."""
        self.send_command(["power"])

    def send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a list of commands to the device."""
        try:
            self._remote.send_keys(command)
            _LOGGER.debug("Successfully sent command %s", command)
        except ValueError as err:
            _LOGGER.error("Invalid command: %s. Error: %s", command, err)
