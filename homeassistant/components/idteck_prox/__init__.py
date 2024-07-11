"""Component for interfacing RFK101 proximity card readers."""

from __future__ import annotations

import logging

from rfk101py.rfk101py import rfk101py
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "idteck_prox"

EVENT_IDTECK_PROX_KEYCARD = "idteck_prox_keycard"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Required(CONF_PORT): cv.port,
                        vol.Required(CONF_NAME): cv.string,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the IDTECK proximity card component."""
    conf = config[DOMAIN]
    for unit in conf:
        host = unit[CONF_HOST]
        port = unit[CONF_PORT]
        name = unit[CONF_NAME]

        try:
            reader = IdteckReader(hass, host, port, name)
            reader.connect()
            hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, reader.stop)
        except OSError as error:
            _LOGGER.error("Error creating %s. %s", name, error)
            return False

    return True


class IdteckReader:
    """Representation of an IDTECK proximity card reader."""

    def __init__(self, hass, host, port, name):
        """Initialize the reader."""
        self.hass = hass
        self._host = host
        self._port = port
        self._name = name
        self._connection = None

    def connect(self):
        """Connect to the reader."""

        self._connection = rfk101py(self._host, self._port, self._callback)

    def _callback(self, card):
        """Send a keycard event message into Home Assistant whenever a card is read."""
        self.hass.bus.fire(
            EVENT_IDTECK_PROX_KEYCARD, {"card": card, "name": self._name}
        )

    def stop(self, _: Event) -> None:
        """Close resources."""
        if self._connection:
            self._connection.close()
            self._connection = None
