"""Support for Ebusd daemon for communication with eBUS heating systems."""
import logging
import socket

import ebusdpy
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PORT,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "ebusd"
DEFAULT_PORT = 8888
CONF_CIRCUIT = "circuit"
CACHE_TTL = 900
SERVICE_EBUSD_WRITE = "ebusd_write"


def verify_ebusd_config(config):
    """Verify eBusd config."""
    circuit = config[CONF_CIRCUIT]
    for condition in config[CONF_MONITORED_CONDITIONS]:
        if condition not in SENSOR_TYPES[circuit]:
            raise vol.Invalid(f"Condition '{condition}' not in '{circuit}'.")
    return config


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            vol.All(
                {
                    vol.Required(CONF_CIRCUIT): cv.string,
                    vol.Required(CONF_HOST): cv.string,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                    vol.Optional(CONF_MONITORED_CONDITIONS, default=[]): cv.ensure_list,
                },
                verify_ebusd_config,
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the eBusd component."""
    _LOGGER.debug("Integration setup started")
    conf = config[DOMAIN]
    name = conf[CONF_NAME]
    circuit = conf[CONF_CIRCUIT]
    monitored_conditions = conf.get(CONF_MONITORED_CONDITIONS)
    server_address = (conf.get(CONF_HOST), conf.get(CONF_PORT))

    try:
        ebusdpy.init(server_address)
        hass.data[DOMAIN] = EbusdData(server_address, circuit)

        sensor_config = {
            CONF_MONITORED_CONDITIONS: monitored_conditions,
            "client_name": name,
            "sensor_types": SENSOR_TYPES[circuit],
        }
        load_platform(hass, Platform.SENSOR, DOMAIN, sensor_config, config)

        hass.services.register(DOMAIN, SERVICE_EBUSD_WRITE, hass.data[DOMAIN].write)

        _LOGGER.debug("Ebusd integration setup completed")
        return True
    except (socket.timeout, OSError):
        return False


class EbusdData:
    """Get the latest data from Ebusd."""

    def __init__(self, address, circuit):
        """Initialize the data object."""
        self._circuit = circuit
        self._address = address
        self.value = {}

    def update(self, name, stype):
        """Call the Ebusd API to update the data."""
        try:
            _LOGGER.debug("Opening socket to ebusd %s", name)
            command_result = ebusdpy.read(
                self._address, self._circuit, name, stype, CACHE_TTL
            )
            if command_result is not None:
                if "ERR:" in command_result:
                    _LOGGER.warning(command_result)
                else:
                    self.value[name] = command_result
        except RuntimeError as err:
            _LOGGER.error(err)
            raise RuntimeError(err) from err

    def write(self, call: ServiceCall) -> None:
        """Call write method on ebusd."""
        name = call.data.get("name")
        value = call.data.get("value")

        try:
            _LOGGER.debug("Opening socket to ebusd %s", name)
            command_result = ebusdpy.write(self._address, self._circuit, name, value)
            if command_result is not None and "done" not in command_result:
                _LOGGER.warning("Write command failed: %s", name)
        except RuntimeError as err:
            _LOGGER.error(err)
