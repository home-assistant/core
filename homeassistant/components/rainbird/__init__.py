"""Support for Rain Bird Irrigation system LNK WiFi Module."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DATA_RAINBIRD = "rainbird"
DOMAIN = "rainbird"
# sensor_type [ description, unit, icon ]
SENSOR_TYPES = {
    "rainsensor": ["Rainsensor", None, "mdi:water"],
    "raindelay": ["Raindelay", None, "mdi:water-off"],
}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_HOST): cv.string, vol.Required(CONF_PASSWORD): cv.string}
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

    _LOGGER.debug("Rain Bird Controller set to: %s", server)

    initial_status = controller.command("ModelAndVersion")
    if initial_status and initial_status["type"] != "ModelAndVersionResponse":
        _LOGGER.error("Error getting state. Possible configuration issues")
        return False

    hass.data[DATA_RAINBIRD] = controller
    return True
