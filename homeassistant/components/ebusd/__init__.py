"""Support for Ebusd daemon for communication with eBUS heating systems."""

import logging
from typing import Any

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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EBUSD_DATA, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "ebusd"
DEFAULT_PORT = 8888
CONF_CIRCUIT = "circuit"
CACHE_TTL = 900
SERVICE_EBUSD_WRITE = "ebusd_write"


def verify_ebusd_config(config: ConfigType) -> ConfigType:
    """Verify eBusd config."""
    circuit: str = config[CONF_CIRCUIT]
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
    conf: ConfigType = config[DOMAIN]
    name: str = conf[CONF_NAME]
    circuit: str = conf[CONF_CIRCUIT]
    monitored_conditions: list[str] = conf[CONF_MONITORED_CONDITIONS]
    server_address: tuple[str, int] = (conf[CONF_HOST], conf[CONF_PORT])

    try:
        ebusdpy.init(server_address)
    except TimeoutError, OSError:
        return False
    hass.data[EBUSD_DATA] = EbusdData(server_address, circuit)
    sensor_config = {
        CONF_MONITORED_CONDITIONS: monitored_conditions,
        "client_name": name,
        "sensor_types": SENSOR_TYPES[circuit],
    }
    load_platform(hass, Platform.SENSOR, DOMAIN, sensor_config, config)

    hass.services.register(DOMAIN, SERVICE_EBUSD_WRITE, hass.data[EBUSD_DATA].write)

    _LOGGER.debug("Ebusd integration setup completed")
    return True


class EbusdData:
    """Get the latest data from Ebusd."""

    def __init__(self, address: tuple[str, int], circuit: str) -> None:
        """Initialize the data object."""
        self._circuit = circuit
        self._address = address
        self.value: dict[str, Any] = {}

    def update(self, name: str, stype: int) -> None:
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
            if (
                command_result is not None
                and "done" not in command_result
                and "empty" not in command_result
            ):
                _LOGGER.warning("Write command failed: %s", name)
        except RuntimeError as err:
            _LOGGER.error(err)
