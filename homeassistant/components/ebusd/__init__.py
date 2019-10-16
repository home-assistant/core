"""Support for Ebusd daemon for communication with eBUS heating systems."""
from datetime import timedelta
import logging
import socket

import ebusdpy
import voluptuous as vol


from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PORT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.util import Throttle

from .const import DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "ebusd"
DEFAULT_PORT = 8888
CONF_CIRCUITS = "circuits"
CONF_CIRCUIT = "circuit"
CONF_CACHE_TTL = "cache_ttl"
DEFAULT_CACHE_TTL = 900
SERVICE_EBUSD_WRITE = "ebusd_write"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)


def verify_ebusd_circuit_config(config):
    """Verify eBusd circuit config."""
    circuit = config[CONF_CIRCUIT]
    for condition in config[CONF_MONITORED_CONDITIONS]:
        if condition not in SENSOR_TYPES[circuit]:
            raise vol.Invalid("Condition '" + condition + "' not in '" + circuit + "'.")
    return config


def verify_ebusd_config(config):
    """Verify eBusd config."""
    cache_ttl = config[CONF_CACHE_TTL]
    if cache_ttl < MIN_TIME_BETWEEN_UPDATES.seconds:
        raise vol.Invalid(
            "Cache TTL "
            + str(cache_ttl)
            + " cannot be less than "
            + str(MIN_TIME_BETWEEN_UPDATES.seconds)
            + " seconds."
        )
    for circuit in config[CONF_CIRCUITS]:
        verify_ebusd_circuit_config(circuit)
    return config


CONFIG_CIRCUIT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CIRCUIT): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[]): cv.ensure_list,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            vol.All(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Optional(
                        CONF_CACHE_TTL, default=DEFAULT_CACHE_TTL
                    ): cv.positive_int,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                    vol.Required(CONF_CIRCUITS, default=[]): vol.All(
                        cv.ensure_list, [CONFIG_CIRCUIT_SCHEMA]
                    ),
                },
                verify_ebusd_config,
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the eBusd component."""
    conf = config[DOMAIN]
    cache_ttl = conf[CONF_CACHE_TTL]
    server_address = (conf.get(CONF_HOST), conf.get(CONF_PORT))

    try:
        _LOGGER.debug("Ebusd integration setup started")

        ebusdpy.init(server_address)
        hass.data[DOMAIN] = EbusdData(server_address, cache_ttl)

        for circuit_cfg in conf[CONF_CIRCUITS]:
            sensor_config = {
                "circuit": circuit_cfg["circuit"],
                CONF_MONITORED_CONDITIONS: circuit_cfg["monitored_conditions"],
                "client_name": circuit_cfg["name"],
                "sensor_types": SENSOR_TYPES[circuit_cfg["circuit"]],
            }
            load_platform(hass, "sensor", DOMAIN, sensor_config, config)

        hass.services.register(DOMAIN, SERVICE_EBUSD_WRITE, hass.data[DOMAIN].write)

        _LOGGER.debug("Ebusd integration setup completed")
        return True
    except (socket.timeout, socket.error):
        return False


class EbusdData:
    """Get the latest data from Ebusd."""

    def __init__(self, address, cache_ttl):
        """Initialize the data object."""
        self._address = address
        self._cache_ttl = cache_ttl
        self.value = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, circuit, name, stype):
        """Call the Ebusd API to update the data."""
        try:
            _LOGGER.debug("Opening socket to ebusd %s", name)
            command_result = ebusdpy.read(
                self._address, circuit, name, stype, self._cache_ttl
            )
            if command_result is not None:
                if "ERR:" in command_result:
                    _LOGGER.warning(command_result)
                else:
                    self.value[name] = command_result
        except RuntimeError as err:
            _LOGGER.error(err)
            raise RuntimeError(err)

    def write(self, call):
        """Call write methon on ebusd."""
        circuit = call.data.get("circuit")
        name = call.data.get("name")
        value = call.data.get("value")

        try:
            _LOGGER.debug("Opening socket to ebusd %s", name)
            command_result = ebusdpy.write(self._address, circuit, name, value)
            if command_result is not None:
                if "done" not in command_result:
                    _LOGGER.warning("Write command failed: %s", name)
        except RuntimeError as err:
            _LOGGER.error(err)
