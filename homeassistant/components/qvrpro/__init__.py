"""Support for QVR Pro NVR software by QNAP."""

import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

from .const import CONF_EXCLUDE_CHANNELS, DOMAIN

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


def setup(hass, config):
    """Set up the QVR Pro component."""
    from pyqvrpro import Client
    from pyqvrpro.client import AuthenticationError

    user = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    host = config[DOMAIN][CONF_HOST]
    excluded_channels = config[DOMAIN][CONF_EXCLUDE_CHANNELS]

    try:
        qvrpro = Client(user, password, host)
    except AuthenticationError:
        _LOGGER.error("QVR Pro authentication failed.  Please check your credentials.")
        return False

    channel_resp = qvrpro.get_channel_list()

    if "message" in channel_resp.keys():
        if channel_resp["message"] == "Insufficient permission.":
            _LOGGER.error("QVR Pro user must have Surveillance Management permission.")
            return False

    channels = []

    for channel in channel_resp["channels"]:
        if channel["channel_index"] + 1 in excluded_channels:
            continue

        channels.append(QVRChannel(**channel))

    hass.data[DOMAIN] = {"channels": channels, "client": qvrpro}

    load_platform(hass, "camera", DOMAIN, {}, config)

    # Register services
    def handle_start_record(call):
        guid = call.data.get("guid")
        qvrpro.start_recording(guid)

    def handle_stop_record(call):
        guid = call.data.get("guid")
        qvrpro.stop_recording(guid)

    hass.services.register(DOMAIN, "start_record", handle_start_record)
    hass.services.register(DOMAIN, "stop_record", handle_stop_record)

    return True


class QVRChannel:
    """Representation of a QVR channel."""

    def __init__(self, name, model, brand, channel_index, guid):
        """Initialize QVRChannel."""
        self.name = "QVR {}".format(name)
        self.model = model
        self.brand = brand
        self.index = channel_index
        self.guid = guid
