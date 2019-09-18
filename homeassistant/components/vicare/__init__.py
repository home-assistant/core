"""The ViCare integration."""
import logging

import voluptuous as vol
from PyViCare.PyViCareDevice import Device

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_NAME
from homeassistant.helpers import discovery

_LOGGER = logging.getLogger(__name__)

VICARE_PLATFORMS = ["climate", "water_heater"]

DOMAIN = "vicare"
VICARE_API = "api"
VICARE_NAME = "name"

CONF_CIRCUIT = "circuit"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_CIRCUIT): int,
                vol.Optional(CONF_NAME, default="ViCare"): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Create the ViCare component."""
    conf = config[DOMAIN]
    params = {"token_file": "/tmp/vicare_token.save"}
    if conf.get(CONF_CIRCUIT) is not None:
        params["circuit"] = conf[CONF_CIRCUIT]

    try:
        vicare_api = Device(conf[CONF_USERNAME], conf[CONF_PASSWORD], **params)
    except AttributeError:
        _LOGGER.error(
            "Failed to create PyViCare API client. Please check your credentials."
        )
        return False

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VICARE_API] = vicare_api
    hass.data[DOMAIN][VICARE_NAME] = conf[CONF_NAME]

    for platform in VICARE_PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    return True
