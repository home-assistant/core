"""Support for Lupusec Home Security system."""
import logging

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD,
                                 CONF_NAME, CONF_IP_ADDRESS)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['lupupy==0.0.17']

DOMAIN = 'lupusec'

NOTIFICATION_ID = 'lupusec_notification'
NOTIFICATION_TITLE = 'Lupusec Security Setup'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

LUPUSEC_PLATFORMS = [
    'alarm_control_panel', 'binary_sensor', 'switch'
]


def setup(hass, config):
    """Set up Lupusec component."""
    from lupupy.exceptions import LupusecException

    conf = config[DOMAIN]
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    ip_address = conf[CONF_IP_ADDRESS]
    name = conf.get(CONF_NAME)

    try:
        hass.data[DOMAIN] = LupusecSystem(username, password, ip_address, name)
    except LupusecException as ex:
        _LOGGER.error(ex)

        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    for platform in LUPUSEC_PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    return True


class LupusecSystem:
    """Lupusec System class."""

    def __init__(self, username, password, ip_address, name):
        """Initialize the system."""
        import lupupy
        self.lupusec = lupupy.Lupusec(username, password, ip_address)
        self.name = name


class LupusecDevice(Entity):
    """Representation of a Lupusec device."""

    def __init__(self, data, device):
        """Initialize a sensor for Lupusec device."""
        self._data = data
        self._device = device

    def update(self):
        """Update automation state."""
        self._device.refresh()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._device.name
