"""The Schluter DITRA-HEAT integration."""
from datetime import timedelta
import logging

from requests import RequestException, Session
from schluter.api import Api
from schluter.authenticator import AuthenticationState, Authenticator
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DATA_SCHLUTER = "schluter"
PLATFORMS = ["climate"]
DEFAULT_TIMEOUT = 10
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)
SCHLUTER_CONFIG_FILE = ".schluter.conf"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_schluter(hass, config, api, authenticator):
    """Set up the Schluter component."""

    authentication = None
    try:
        authentication = authenticator.authenticate()
    except RequestException as ex:
        _LOGGER.error("Unable to connect to Schluter service: %s", ex)

    state = authentication.state

    if state == AuthenticationState.AUTHENTICATED:
        hass.data[DATA_SCHLUTER] = SchluterPlatformData(authentication.session_id, api)

        for component in PLATFORMS:
            discovery.load_platform(hass, component, DOMAIN, {}, config)

        return True
    if state == AuthenticationState.BAD_PASSWORD:
        _LOGGER.error("Invalid password provided")
        return False
    if state == AuthenticationState.BAD_EMAIL:
        _LOGGER.error("Invalid email provided")
        return False

    return False


async def async_setup(hass, config):
    """Set up the Schluter component."""
    _LOGGER.debug("Starting setup of schluter")
    conf = config[DOMAIN]
    api_http_session = None
    try:
        api_http_session = Session()
    except RequestException as ex:
        _LOGGER.warning("Creating HTTP session failed with: %s", ex)

    api = Api(timeout=conf.get(CONF_TIMEOUT), http_session=api_http_session)

    authenticator = Authenticator(
        api,
        conf.get(CONF_USERNAME),
        conf.get(CONF_PASSWORD),
        session_id_cache_file=hass.config.path(SCHLUTER_CONFIG_FILE),
    )

    return await async_setup_schluter(hass, config, api, authenticator)


class SchluterPlatformData:
    """Data object for passing necessary objects to platform."""

    def __init__(self, session_id, api):
        """Initialize platform data object."""
        self.session_id = session_id
        self.api = api
