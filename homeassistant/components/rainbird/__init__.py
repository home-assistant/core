"""Support for Rain Bird Irrigation system LNK WiFi Module."""
import logging

import voluptuous as vol

from homeassistant.components import binary_sensor, sensor, switch
from homeassistant.const import (
    CONF_FRIENDLY_NAME,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TRIGGER_TIME,
)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

RAINBIRD_CONTROLLER = "controller"
DATA_RAINBIRD = "rainbird"
DOMAIN = "rainbird"

SENSOR_TYPE_RAINDELAY = "raindelay"
SENSOR_TYPE_RAINSENSOR = "rainsensor"
# sensor_type [ description, unit, icon ]
SENSOR_TYPES = {
    SENSOR_TYPE_RAINSENSOR: ["Rainsensor", None, "mdi:water"],
    SENSOR_TYPE_RAINDELAY: ["Raindelay", None, "mdi:water-off"],
}

ZONE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_TRIGGER_TIME): cv.positive_int,
        vol.Optional(CONF_SCAN_INTERVAL): cv.positive_int,
    }
)
CONTROLLER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TRIGGER_TIME): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL): cv.string,
        vol.Optional("zones"): vol.Schema({cv.positive_int: ZONE_SCHEMA}),
    }
)
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.Any(cv.ensure_list(CONTROLLER_SCHEMA), CONTROLLER_SCHEMA))},
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the Rain Bird component."""

    hass.data[DATA_RAINBIRD] = list()
    if isinstance(config[DOMAIN], list):
        for controller_config in config[DOMAIN]:
            _setup_controller(controller_config, hass)
    else:
        _setup_controller(config[DOMAIN], hass)

    return True


def _setup_controller(config, hass):
    from pyrainbird import RainbirdController

    server = config[CONF_HOST]
    password = config[CONF_PASSWORD]
    controller = RainbirdController(server, password)
    position = len(hass.data[DATA_RAINBIRD])
    hass.data[DATA_RAINBIRD].append(controller)
    _LOGGER.debug("Rain Bird Controller %d set to: %s", position, server)
    for platform in [switch.DOMAIN, sensor.DOMAIN, binary_sensor.DOMAIN]:
        discovery.load_platform(
            hass,
            platform,
            DOMAIN,
            discovered={**{RAINBIRD_CONTROLLER: position}, **config},
            hass_config=config,
        )
