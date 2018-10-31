"""
Support for USPS packages and mail.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/usps/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD)
from homeassistant.helpers import (config_validation as cv, discovery)
from homeassistant.util import Throttle
from homeassistant.util.dt import now

REQUIREMENTS = ['myusps==1.3.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'usps'
DATA_USPS = 'data_usps'
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)
COOKIE = 'usps_cookies.pickle'
CACHE = 'usps_cache'
CONF_DRIVER = 'driver'

USPS_TYPE = ['sensor', 'camera']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DOMAIN): cv.string,
        vol.Optional(CONF_DRIVER): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Use config values to set up a function enabling status retrieval."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    name = conf.get(CONF_NAME)
    driver = conf.get(CONF_DRIVER)

    import myusps
    try:
        cookie = hass.config.path(COOKIE)
        cache = hass.config.path(CACHE)
        session = myusps.get_session(username, password,
                                     cookie_path=cookie, cache_path=cache,
                                     driver=driver)
    except myusps.USPSError:
        _LOGGER.exception('Could not connect to My USPS')
        return False

    hass.data[DATA_USPS] = USPSData(session, name)

    for component in USPS_TYPE:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


class USPSData:
    """Stores the data retrieved from USPS.

    For each entity to use, acts as the single point responsible for fetching
    updates from the server.
    """

    def __init__(self, session, name):
        """Initialize the data object."""
        self.session = session
        self.name = name
        self.packages = []
        self.mail = []
        self.attribution = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, **kwargs):
        """Fetch the latest info from USPS."""
        import myusps
        self.packages = myusps.get_packages(self.session)
        self.mail = myusps.get_mail(self.session, now().date())
        self.attribution = myusps.ATTRIBUTION
        _LOGGER.debug("Mail, request date: %s, list: %s",
                      now().date(), self.mail)
        _LOGGER.debug("Package list: %s", self.packages)
