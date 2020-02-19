"""Support for QVR Pro NVR software by QNAP."""

import logging

from pyqvrpro import Client
from pyqvrpro.client import AuthenticationError, InsufficientPermissionsError
import voluptuous as vol

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

from .const import (
    CONF_EXCLUDE_CHANNELS,
    DOMAIN,
    SERVICE_START_RECORD,
    SERVICE_STOP_RECORD,
)

CHANNEL_GUID = "guid"

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_EXCLUDE_CHANNELS, default=[]): vol.All(
                    cv.ensure_list_csv, [cv.positive_int]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA_CHANNEL_RECORD = vol.Schema({vol.Required(CHANNEL_GUID): cv.string})


def setup(hass, config):
    """Set up the QVR Pro component."""
    conf = config[DOMAIN]
    user = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    host = conf[CONF_HOST]
    excluded_channels = conf[CONF_EXCLUDE_CHANNELS]

    try:
        qvrpro = Client(user, password, host)

        channel_resp = qvrpro.get_channel_list()

    except InsufficientPermissionsError:
        _LOGGER.error("User must have Surveillance Management permission")
        return False
    except AuthenticationError:
        _LOGGER.error("Authentication failed")
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
        guid = call.data.get(CHANNEL_GUID)
        qvrpro.start_recording(guid)

    def handle_stop_record(call):
        guid = call.data.get(CHANNEL_GUID)
        qvrpro.stop_recording(guid)

    hass.services.register(
        DOMAIN,
        SERVICE_START_RECORD,
        handle_start_record,
        schema=SERVICE_SCHEMA_CHANNEL_RECORD,
    )
    hass.services.register(
        DOMAIN,
        SERVICE_STOP_RECORD,
        handle_stop_record,
        schema=SERVICE_SCHEMA_CHANNEL_RECORD,
    )

    return True
