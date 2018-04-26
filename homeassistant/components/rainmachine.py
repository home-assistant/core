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
    CONF_EMAIL, CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_SSL)
from homeassistant.util import Throttle

REQUIREMENTS = ['regenmaschine==0.4.1']

_LOGGER = logging.getLogger(__name__)

DATA_RAINMACHINE = 'data_rainmachine'
DOMAIN = 'rainmachine'

NOTIFICATION_ID = 'rainmachine_notification'
NOTIFICATION_TITLE = 'RainMachine Component Setup'

CONF_ATTRIBUTION = 'Data provided by Green Electronics LLC'

DEFAULT_PORT = 8080
DEFAULT_SSL = True

MIN_SCAN_TIME_LOCAL = timedelta(seconds=1)
MIN_SCAN_TIME_REMOTE = timedelta(seconds=1)
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
    ip_address = conf.get(CONF_IP_ADDRESS)
    email_address = conf.get(CONF_EMAIL)
    password = conf[CONF_PASSWORD]

    try:
        if ip_address:
            port = conf[CONF_PORT]
            ssl = conf[CONF_SSL]
            auth = Authenticator.create_local(
                ip_address, password, port=port, https=ssl)
            _LOGGER.debug('Configuring local API: %s', ip_address)
        elif email_address:
            auth = Authenticator.create_remote(email_address, password)
            _LOGGER.debug('Configuring remote API')

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


def aware_throttle(api_type):
    """Create an API type-aware throttler."""
    _decorator = None
    if api_type == 'local':

        @Throttle(MIN_SCAN_TIME_LOCAL, MIN_SCAN_TIME_FORCED)
        def decorator(function):
            """Create a local API throttler."""
            return function

        _decorator = decorator
    else:

        @Throttle(MIN_SCAN_TIME_REMOTE, MIN_SCAN_TIME_FORCED)
        def decorator(function):
            """Create a remote API throttler."""
            return function

        _decorator = decorator

    return _decorator
