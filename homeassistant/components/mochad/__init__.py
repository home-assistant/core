"""Support for CM15A/CM19A X10 Controller using mochad daemon."""
import logging
import threading

from pymochad import controller, exceptions
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

CONF_COMM_TYPE = "comm_type"

DOMAIN = "mochad"

REQ_LOCK = threading.Lock()

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_HOST, default="localhost"): cv.string,
                vol.Optional(CONF_PORT, default=1099): cv.port,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the mochad component."""
    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)

    try:
        mochad_controller = MochadCtrl(host, port)
    except exceptions.ConfigurationError as err:
        _LOGGER.exception(str(err))
        return False

    def stop_mochad(event):
        """Stop the Mochad service."""
        mochad_controller.disconnect()

    def start_mochad(event):
        """Start the Mochad service."""
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_mochad)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_mochad)
    hass.data[DOMAIN] = mochad_controller

    return True


class MochadCtrl:
    """Mochad controller."""

    def __init__(self, host, port):
        """Initialize a PyMochad controller."""
        super().__init__()
        self._host = host
        self._port = port

        self.ctrl = controller.PyMochad(server=self._host, port=self._port)

    @property
    def host(self):
        """Return the server where mochad is running."""
        return self._host

    @property
    def port(self):
        """Return the port mochad is running on."""
        return self._port

    def disconnect(self):
        """Close the connection to the mochad socket."""
        self.ctrl.socket.close()
