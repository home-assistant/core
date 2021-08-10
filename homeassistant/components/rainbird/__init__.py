"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

import logging

from pyrainbird import RainbirdController
import voluptuous as vol

from homeassistant.components import binary_sensor, sensor, switch
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import (
    CONF_FRIENDLY_NAME,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TRIGGER_TIME,
)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

CONF_ZONES = "zones"

PLATFORMS = [switch.DOMAIN, sensor.DOMAIN, binary_sensor.DOMAIN]

_LOGGER = logging.getLogger(__name__)

RAINBIRD_CONTROLLER = "controller"
DATA_RAINBIRD = "rainbird"
DOMAIN = "rainbird"

SENSOR_TYPE_RAINDELAY = "raindelay"
SENSOR_TYPE_RAINSENSOR = "rainsensor"


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_TYPE_RAINSENSOR,
        name="Rainsensor",
        icon="mdi:water",
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_RAINDELAY,
        name="Raindelay",
        icon="mdi:water-off",
    ),
)

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=SENSOR_TYPE_RAINSENSOR,
        name="Rainsensor",
        icon="mdi:water",
    ),
    BinarySensorEntityDescription(
        key=SENSOR_TYPE_RAINDELAY,
        name="Raindelay",
        icon="mdi:water-off",
    ),
)

TRIGGER_TIME_SCHEMA = vol.All(
    cv.time_period, cv.positive_timedelta, lambda td: (td.total_seconds() // 60)
)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_TRIGGER_TIME): TRIGGER_TIME_SCHEMA,
    }
)
CONTROLLER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_TRIGGER_TIME): TRIGGER_TIME_SCHEMA,
        vol.Optional(CONF_ZONES): vol.Schema({cv.positive_int: ZONE_SCHEMA}),
    }
)
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [CONTROLLER_SCHEMA]))},
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the Rain Bird component."""

    hass.data[DATA_RAINBIRD] = []
    success = False
    for controller_config in config[DOMAIN]:
        success = success or _setup_controller(hass, controller_config, config)

    return success


def _setup_controller(hass, controller_config, config):
    """Set up a controller."""
    server = controller_config[CONF_HOST]
    password = controller_config[CONF_PASSWORD]
    controller = RainbirdController(server, password)
    position = len(hass.data[DATA_RAINBIRD])
    try:
        controller.get_serial_number()
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.error("Unable to setup controller: %s", exc)
        return False
    hass.data[DATA_RAINBIRD].append(controller)
    _LOGGER.debug("Rain Bird Controller %d set to: %s", position, server)
    for platform in PLATFORMS:
        discovery.load_platform(
            hass,
            platform,
            DOMAIN,
            {RAINBIRD_CONTROLLER: position, **controller_config},
            config,
        )
    return True
