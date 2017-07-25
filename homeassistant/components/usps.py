"""
Support for USPS packages and mail.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/usps/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (CONF_NAME, CONF_USERNAME, CONF_PASSWORD)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['myusps==1.1.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'usps'
DATA_USPS = 'data_usps'
SCAN_INTERVAL = timedelta(minutes=30)
COOKIE = 'usps_cookies.pickle'

USPS_TYPE = ['sensor', 'camera']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Use config values to set up a function enabling status retrieval."""

    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    name = conf.get(CONF_NAME)

    import myusps
    _LOGGER.debug("Starting myUSPS session...")
    try:
        cookie = hass.config.path(COOKIE)
        session = myusps.get_session(username, password, cookie_path=cookie)
    except myusps.USPSError:
        _LOGGER.exception('Could not connect to My USPS')
        return False

    hass.data[DATA_USPS] = USPSData(session, name)

    for component in USPS_TYPE:
        _LOGGER.debug("Discovery added for USPS %s", component)
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


class USPSData(object):
    """Stores the data retrieved from USPS.

    For each entity to use, acts as the single point responsible for fetching
    updates from the server.
    """

    def __init__(self, session, name):
        """Initialize the data oject."""
        self._session = session
        self._name = name or DOMAIN
        self._packages = []
        self._mail = []
        self._attr = None
        self._mail_img = []

    @property
    def name(self):
        """Return name for sensors/camera."""
        return self._name

    @property
    def attribution(self):
        """Return attribution for sensors/camera."""
        return self._attr

    @property
    def packages(self):
        """Get latest update if throttle allows. Return status."""
        self.update()
        return self._packages

    @property
    def mail(self):
        """Get latest update if throttle allows. Return status."""
        self.update()
        return self._mail

    @property
    def session(self):
        """Return USPS session object."""
        return self._session

    @Throttle(SCAN_INTERVAL)
    def update(self, **kwargs):
        """Fetch the latest info from USPS."""
        import myusps
        self._packages = myusps.get_packages(self._session)
        self._mail = myusps.get_mail(self._session)
        self._attr = myusps.ATTRIBUTION
        _LOGGER.debug("USPS update performed.")
