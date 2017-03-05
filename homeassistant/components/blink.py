"""
Support for Blink Home Camera System.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/blink/
"""
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_USERNAME,
                                 CONF_PASSWORD,
                                 CONF_SCAN_INTERVAL)
from homeassistant.helpers import discovery
_LOGGER = logging.getLogger(__name__)

DOMAIN = 'blink'
REQUIREMENTS = ['blinkpy==0.4.2']

BLINKGLOB = None
DEFAULT_UPDATE_INTERVAL = 90

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL,
                     default=DEFAULT_UPDATE_INTERVAL): cv.positive_int
    })
}, extra=vol.ALLOW_EXTRA)


class BlinkSystem(object):
    """Blink System class."""

    def __init__(self, config_info):
        """Initialize the system."""
        import blinkpy
        self.blink = blinkpy.Blink(username=config_info[DOMAIN][CONF_USERNAME],
                                   password=config_info[DOMAIN][CONF_PASSWORD])
        self._update_interval = config_info[DOMAIN][CONF_SCAN_INTERVAL]
        self.blink.setup_system()

    @property
    def update_interval(self):
        """A method to return update interval from config."""
        return self._update_interval


def setup(hass, config):
    """Setup Blink System."""
    global BLINKGLOB

    if BLINKGLOB is None:
        BLINKGLOB = BlinkSystem(config)

    discovery.load_platform(hass, 'camera', DOMAIN, {}, config)
    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)
    discovery.load_platform(hass, 'switch', DOMAIN, {}, config)
    return True
