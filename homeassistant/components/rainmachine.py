"""
This component provides support for RainMachine sprinkler controllers.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rainmachine/
"""
import logging
from datetime import timedelta

import voluptuous as vol
from requests.exceptions import ConnectTimeout

from homeassistant.helpers import config_validation as cv
from homeassistant.const import (
    CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_SSL)

REQUIREMENTS = ['regenmaschine==0.4.1']

_LOGGER = logging.getLogger(__name__)

DATA_RAINMACHINE = 'data_rainmachine'
DOMAIN = 'rainmachine'

NOTIFICATION_ID = 'rainmachine_notification'
NOTIFICATION_TITLE = 'RainMachine Component Setup'

DEFAULT_ATTRIBUTION = 'Data provided by Green Electronics LLC'
DEFAULT_PORT = 8080
DEFAULT_SSL = True

MIN_SCAN_TIME = timedelta(seconds=1)
MIN_SCAN_TIME_FORCED = timedelta(milliseconds=100)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
            vol.Required(CONF_IP_ADDRESS): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        })
    },
    extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the RainMachine component."""
    from regenmaschine import Authenticator, Client
    from regenmaschine.exceptions import HTTPError

    conf = config[DOMAIN]
    ip_address = conf[CONF_IP_ADDRESS]
    password = conf[CONF_PASSWORD]
    port = conf[CONF_PORT]
    ssl = conf[CONF_SSL]

    try:
        auth = Authenticator.create_local(
            ip_address, password, port=port, https=ssl)
        client = Client(auth)
        hass.data[DATA_RAINMACHINE] = client
    except (HTTPError, ConnectTimeout, UnboundLocalError) as exc_info:
        _LOGGER.error('An error occurred: %s', str(exc_info))
        hass.components.persistent_notification.create(
            'Error: {0}<br />'
            'You will need to restart hass after fixing.'
            ''.format(exc_info),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False
    return True
