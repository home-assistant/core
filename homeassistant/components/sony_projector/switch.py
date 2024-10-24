"""Support for Sony projectors via SDCP network control."""

from __future__ import annotations

import logging
from typing import Any

import pysdcp
import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Sony Projector"

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
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
    sensors = [SonyProjector(sdcp_connection, name)]
    add_entities(sensors, update_before_add=False)



class SonyProjector(SwitchEntity):
    """Represents a Sony Projector as a switch."""

    def __init__(self, sdcp_connection, name):
        super().__init__()
        """Init of the Sony projector."""

        # await ???
        #self._sdcp = await sdcp_connection
        self._sdcp = sdcp_connection

        self._name = name
        self._state = STATE_OFF
        self._available = False
        self._attributes = {}

    @property
    def name(self):
        """Return name of the projector."""
        return self._name

    async def async_update(self) -> None:
        """Get the latest state from the projector."""
        try:
            if not self._available:
                self._sdcp.get_power()     # neuer Versuch, falls fehler direkt nach exeption
                self._state = STATE_ON
                self._available = True

        except ConnectionError:
            # Handle the case when the projector is off or not reachable
            self._available = False
            self._state = STATE_OFF
            _LOGGER.warning("Projector '%s' is not reachable or is turned off", self._name)

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
