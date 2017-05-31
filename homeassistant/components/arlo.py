"""
This component provides basic support for Netgear Arlo IP cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/arlo/
"""
import logging
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.loader as loader

from requests.exceptions import HTTPError, ConnectTimeout

REQUIREMENTS = ['pyarlo==0.0.4']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = 'Data provided by arlo.netgear.com'

DOMAIN = 'arlo'

DEFAULT_BRAND = 'Netgear Arlo'

NOTIFICATION_ID = 'arlo_notification'
NOTIFICATION_TITLE = 'Arlo Camera Setup'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up an Arlo component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    persistent_notification = loader.get_component('persistent_notification')
    try:
        from pyarlo import PyArlo

        arlo = PyArlo(username, password, preload=False)
        if not arlo.is_connected:
            return False
        hass.data['arlo'] = arlo
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Netgar Arlo: %s", str(ex))
        persistent_notification.create(
            hass, 'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False
    return True
