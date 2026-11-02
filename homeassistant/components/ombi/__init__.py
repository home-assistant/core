"""Support for Ombi."""

import logging

import probatio
import pyombi

from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.typing import ConfigType

from .const import CONF_URLBASE, DEFAULT_PORT, DEFAULT_SSL, DEFAULT_URLBASE, DOMAIN
from .services import setup_services

_LOGGER = logging.getLogger(__name__)


def urlbase(value) -> str:
    """Validate and transform urlbase."""
    if value is None:
        raise probatio.Invalid("string value is None")
    value = str(value).strip("/")
    if not value:
        return value
    return f"{value}/"


CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.All(
            probatio.Schema(
                {
                    probatio.Required(CONF_HOST): cv.string,
                    probatio.Required(CONF_USERNAME): cv.string,
                    probatio.Exclusive(
                        probatio.Secret(CONF_API_KEY), "auth"
                    ): cv.string,
                    probatio.Exclusive(
                        probatio.Secret(CONF_PASSWORD), "auth"
                    ): cv.string,
                    probatio.Optional(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
                    probatio.Optional(CONF_URLBASE, default=DEFAULT_URLBASE): urlbase,
                    probatio.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
                }
            ),
            probatio.AtLeastOne(CONF_API_KEY, CONF_PASSWORD),
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Ombi component platform."""
    setup_services(hass)

    ombi = pyombi.Ombi(
        ssl=config[DOMAIN][CONF_SSL],
        host=config[DOMAIN][CONF_HOST],
        port=config[DOMAIN][CONF_PORT],
        urlbase=config[DOMAIN][CONF_URLBASE],
        username=config[DOMAIN][CONF_USERNAME],
        password=config[DOMAIN].get(CONF_PASSWORD),
        api_key=config[DOMAIN].get(CONF_API_KEY),
    )

    try:
        ombi.authenticate()
        ombi.test_connection()
    except pyombi.OmbiError as err:
        _LOGGER.warning("Unable to setup Ombi: %s", err)
        return False

    hass.data[DOMAIN] = {"instance": ombi}

    load_platform(hass, Platform.SENSOR, DOMAIN, {}, config)

    return True
