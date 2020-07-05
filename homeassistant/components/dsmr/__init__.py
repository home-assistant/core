"""The dsmr component."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_FORCE_UPDATE, CONF_HOST, CONF_PORT, CONF_PREFIX
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

_LOGGER = logging.getLogger(__name__)

CONF_DSMR_VERSION = "dsmr_version"
CONF_RECONNECT_INTERVAL = "reconnect_interval"
CONF_PRECISION = "precision"

DEFAULT_DSMR_VERSION = "2.2"
DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_PRECISION = 3
DEFAULT_FORCE_UPDATE = False
DEFAULT_PREFIX = ""

DOMAIN = "dsmr"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
                vol.Optional(CONF_HOST): cv.string,
                vol.Optional(CONF_DSMR_VERSION, default=DEFAULT_DSMR_VERSION): vol.All(
                    cv.string, vol.In(["5B", "5", "4", "2.2"])
                ),
                vol.Optional(CONF_RECONNECT_INTERVAL, default=30): int,
                vol.Optional(CONF_PRECISION, default=DEFAULT_PRECISION): vol.Coerce(
                    int
                ),
                vol.Optional(
                    CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE
                ): cv.boolean,
                vol.Optional(CONF_PREFIX, default=DEFAULT_PREFIX): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the DSMR platform."""
    config_domain = config[DOMAIN]
    hass.data[DOMAIN] = {
        CONF_PORT: config_domain.get(CONF_PORT),
        CONF_HOST: config_domain.getgit(CONF_HOST),
        CONF_DSMR_VERSION: config_domain.get(CONF_DSMR_VERSION),
        CONF_RECONNECT_INTERVAL: config_domain.get(CONF_RECONNECT_INTERVAL),
        CONF_PRECISION: config_domain.get(CONF_PRECISION),
        CONF_FORCE_UPDATE: config_domain.get(CONF_FORCE_UPDATE),
        CONF_PREFIX: config_domain.get(CONF_PREFIX),
    }

    hass.async_create_task(async_load_platform(hass, "sensor", DOMAIN, {}, config))
    return True
