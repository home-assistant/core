"""
This component provides basic support for Abode Home Security system.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/abode/
"""
import logging

import voluptuous as vol
from requests.exceptions import HTTPError, ConnectTimeout
from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_NAME

REQUIREMENTS = ['abodepy==0.7.1']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by goabode.com"

DOMAIN = 'abode'
DEFAULT_NAME = 'Abode'
DATA_ABODE = 'data_abode'
DEFAULT_ENTITY_NAMESPACE = 'abode'

NOTIFICATION_ID = 'abode_notification'
NOTIFICATION_TITLE = 'Abode Security Setup'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up Abode component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    try:
        data = AbodeData(username, password)
        hass.data[DATA_ABODE] = data

        for component in ['binary_sensor', 'alarm_control_panel']:
            discovery.load_platform(hass, component, DOMAIN, {}, config)

    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Abode: %s", str(ex))
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    return True


class AbodeData:
    """Shared Abode data."""

    def __init__(self, username, password):
        """Initialize Abode oject."""
        import abodepy

        self.abode = abodepy.Abode(username, password)
        self.devices = self.abode.get_devices()

        _LOGGER.debug("Abode Security set up with %s devices",
                      len(self.devices))
