"""Support for QVR Pro NVR software by QNAP."""

import logging

from pyqvrpro import Client
from pyqvrpro.client import AuthenticationError, InsufficientPermissionsError
from requests.exceptions import ConnectionError as RequestsConnectionError
import voluptuous as vol

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

from .const import (
    CONF_EXCLUDE_CHANNELS,
    DOMAIN,
    SERVICE_START_RECORD,
    SERVICE_STOP_RECORD,
)

SERVICE_CHANNEL_GUID = "guid"

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_PORT): cv.port,
                vol.Optional(CONF_EXCLUDE_CHANNELS, default=[]): vol.All(
                    cv.ensure_list_csv, [cv.positive_int]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_CHANNEL_RECORD_SCHEMA = vol.Schema(
    {vol.Required(SERVICE_CHANNEL_GUID): cv.string}
)


def setup(hass, config):
    """Set up the QVR Pro component."""
    conf = config[DOMAIN]
    user = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    host = conf[CONF_HOST]
    port = conf.get(CONF_PORT)
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

    load_platform(hass, CAMERA_DOMAIN, DOMAIN, {}, config)

    # Register services
    def handle_start_record(call):
        guid = call.data[SERVICE_CHANNEL_GUID]
        qvrpro.start_recording(guid)

    def handle_stop_record(call):
        guid = call.data[SERVICE_CHANNEL_GUID]
        qvrpro.stop_recording(guid)

    hass.services.register(
        DOMAIN,
        SERVICE_START_RECORD,
        handle_start_record,
        schema=SERVICE_CHANNEL_RECORD_SCHEMA,
    )
    hass.services.register(
        DOMAIN,
        SERVICE_STOP_RECORD,
        handle_stop_record,
        schema=SERVICE_CHANNEL_RECORD_SCHEMA,
    )

    return True
