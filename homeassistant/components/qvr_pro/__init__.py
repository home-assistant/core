"""Support for QVR Pro NVR software by QNAP."""

import logging

import probatio
from pyqvrpro import Client
from pyqvrpro.client import AuthenticationError, InsufficientPermissionsError
from requests.exceptions import ConnectionError as RequestsConnectionError

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.typing import ConfigType

from .const import CONF_EXCLUDE_CHANNELS, DOMAIN
from .services import setup_services

DEFAULT_PORT = 8080

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Required(CONF_HOST): cv.string,
                probatio.Required(CONF_USERNAME): cv.string,
                probatio.Required(probatio.Secret(CONF_PASSWORD)): cv.string,
                probatio.Optional(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
                probatio.Optional(CONF_EXCLUDE_CHANNELS, default=[]): probatio.All(
                    cv.ensure_list_csv, [cv.positive_int]
                ),
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the QVR Pro component."""
    setup_services(hass)
    conf = config[DOMAIN]
    user = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    host = conf[CONF_HOST]
    port = conf[CONF_PORT]
    excluded_channels = conf[CONF_EXCLUDE_CHANNELS]

    try:
        qvrpro = Client(user, password, host, port=port)

        channel_resp = qvrpro.get_channel_list()

    except InsufficientPermissionsError:
        _LOGGER.error("User must have Surveillance Management permission")
        return False
    except AuthenticationError:
        _LOGGER.error("Authentication failed")
        return False
    except RequestsConnectionError:
        _LOGGER.error("Error connecting to QVR server")
        return False

    channels = []

    for channel in channel_resp["channels"]:
        if channel["channel_index"] + 1 in excluded_channels:
            continue

        channels.append(channel)

    hass.data[DOMAIN] = {"channels": channels, "client": qvrpro}

    load_platform(hass, Platform.CAMERA, DOMAIN, {}, config)

    return True
