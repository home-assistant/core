"""Support for Rain Bird Irrigation system LNK WiFi Module."""
import logging

import voluptuous as vol

from homeassistant.components import binary_sensor, sensor
from homeassistant.components.rainbird.switch import (
    ATTR_DURATION,
    SERVICE_SCHEMA_IRRIGATION,
    SERVICE_START_IRRIGATION,
    RainBirdSwitch,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

RAINBIRD_CONTROLLER = "rainbird_controller"
DATA_RAINBIRD = "rainbird"
DOMAIN = "rainbird"

SENSOR_TYPE_RAINDELAY = "raindelay"
SENSOR_TYPE_RAINSENSOR = "rainsensor"
# sensor_type [ description, unit, icon ]
SENSOR_TYPES = {
    SENSOR_TYPE_RAINSENSOR: ["Rainsensor", None, "mdi:water"],
    SENSOR_TYPE_RAINDELAY: ["Raindelay", None, "mdi:water-off"],
}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the Rain Bird component."""

    conf = config[DOMAIN]
    server = conf.get(CONF_HOST)
    password = conf.get(CONF_PASSWORD)

    from pyrainbird import RainbirdController

    controller = RainbirdController(server, password)
    hass.data[DATA_RAINBIRD] = controller

    _LOGGER.debug("Rain Bird Controller set to: %s", server)

    for platform in [switch.DOMAIN, sensor.DOMAIN, binary_sensor.DOMAIN]:
        discovery.load_platform(
            hass,
            platform,
            DOMAIN,
            discovered={RAINBIRD_CONTROLLER: controller},
            hass_config=config,
        )

    return True
