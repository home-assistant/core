"""
This component provides basic support for Lupusec Home Security system.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/lupusec
"""

from datetime import timedelta
import logging
import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD,
                                 CONF_NAME, CONF_IP_ADDRESS,
                                 CONF_SCAN_INTERVAL)
from homeassistant.helpers.entity import Entity
_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['lupupy==0.0.4']

DOMAIN = 'lupusec'
DEFAULT_SCAN_INTERVAL = timedelta(seconds=5)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)

LUPUS_PLATFORMS = [
    'alarm_control_panel', 'binary_sensor', 'switch'
]


class LupusecSystem:
    """Lupusec System class."""

    def __init__(self, username, password, ip_address, name, get_devices=True):
        """Initialize the system."""
        import lupupy
        self.lupusec = lupupy.Lupusec(username, password, ip_address)
        self.name = name
        self.devices = []


def setup(hass, config):
    """Set up Lupusec component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    ip_address = conf.get(CONF_IP_ADDRESS)
    name = conf.get(CONF_NAME)
    try:
        hass.data[DOMAIN] = LupusecSystem(username, password, ip_address, name)
    except BaseException:
        _LOGGER.error("Unable to setup Lupusec Panel.")

    for platform in LUPUS_PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    return True


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

    def _update_callback(self, device):
        """Update the device state."""
        self.schedule_update_ha_state()
