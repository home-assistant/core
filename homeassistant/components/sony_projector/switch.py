"""Support for Sony projectors via SDCP network control."""

from __future__ import annotations

import logging
from typing import Any

import pysdcp
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Sony Projector"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Connect to Sony projector using network."""

    host = config[CONF_HOST]
    name = config[CONF_NAME]
    sdcp_connection = pysdcp.Projector(host)

    # Sanity check the connection
    try:
        sdcp_connection.get_power()
    except ConnectionError:
        _LOGGER.error("Failed to connect to projector '%s'", host)
        return
    _LOGGER.debug("Validated projector '%s' OK", host)
    add_entities([SonyProjector(sdcp_connection, name)], True)


class SonyProjector(SwitchEntity):
    """Represents a Sony Projector as a switch."""

    def __init__(self, sdcp_connection, name):
        """Init of the Sony projector."""
        self._sdcp = sdcp_connection
        self._name = name
        self._state = None
        self._available = False
        self._attributes = {}

    @property
    def available(self):
        """Return if projector is available."""
        return self._available

    @property
    def name(self):
        """Return name of the projector."""
        return self._name

    @property
    def is_on(self):
        """Return if the projector is turned on."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return state attributes."""
        return self._attributes

    def update(self) -> None:
        """Get the latest state from the projector."""
        try:
            self._state = self._sdcp.get_power()
            self._available = True
        except ConnectionRefusedError:
            _LOGGER.error("Projector connection refused")
            self._available = False

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the projector on."""
        _LOGGER.debug("Powering on projector '%s'", self.name)
        if self._sdcp.set_power(True):
            _LOGGER.debug("Powered on successfully")
            self._state = STATE_ON
        else:
            _LOGGER.error("Power on command was not successful")

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the projector off."""
        _LOGGER.debug("Powering off projector '%s'", self.name)
        if self._sdcp.set_power(False):
            _LOGGER.debug("Powered off successfully")
            self._state = STATE_OFF
        else:
            _LOGGER.error("Power off command was not successful")
