"""The Schluter DITRA-HEAT integration."""
import logging

from requests import RequestException, Session
from schluter.api import Api
from schluter.authenticator import AuthenticationState, Authenticator
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DATA_SCHLUTER_SESSION = "schluter_session"
DATA_SCHLUTER_API = "schluter_api"
SCHLUTER_CONFIG_FILE = ".schluter.conf"
API_TIMEOUT = 10

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(DOMAIN): vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Schluter component."""
    _LOGGER.debug("Starting setup of schluter")

    conf = config[DOMAIN]
    api_http_session = Session()
    api = Api(timeout=API_TIMEOUT, http_session=api_http_session)

    authenticator = Authenticator(
        api,
        conf.get(CONF_USERNAME),
        conf.get(CONF_PASSWORD),
        session_id_cache_file=hass.config.path(SCHLUTER_CONFIG_FILE),
    )

    authentication = None
    try:
        authentication = authenticator.authenticate()
    except RequestException as ex:
        _LOGGER.error("Unable to connect to Schluter service: %s", ex)
        return False

    state = authentication.state

    if state == AuthenticationState.AUTHENTICATED:
        hass.data[DOMAIN] = {
            DATA_SCHLUTER_API: api,
            DATA_SCHLUTER_SESSION: authentication.session_id,
        }
        discovery.load_platform(hass, Platform.CLIMATE, DOMAIN, {}, config)
        return True
    if state == AuthenticationState.BAD_PASSWORD:
        _LOGGER.error("Invalid password provided")
        return False
    if state == AuthenticationState.BAD_EMAIL:
        _LOGGER.error("Invalid email provided")
        return False

    _LOGGER.error("Unknown set up error: %s", state)
    return False
