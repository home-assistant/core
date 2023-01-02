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

from datetime import datetime, timedelta

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DATA_SCHLUTER_SESSION = "schluter_session"
DATA_SCHLUTER_API = "schluter_api"
DATA_SCHLUTER_USER = "schluter_user"
DATA_SCHLUTER_PASS = "schluter_pass"
DATA_SCHLUTER_EXPIRES = "schluter_expires"
#DATA_SCHLUTER_SESSIONFILE = "schluter_file"
#SCHLUTER_CONFIG_FILE = ".schluter.conf"
API_TIMEOUT = 10

#
# Period for session renewal in hours
#
SCHLUTER_UPDATE_HOURS=1

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

def schluter_auth_update(hass_domain: dict[str,any]) -> bool:
    ''' 
    schluter_auth_update() updates session_id and expires inside the hass.data[DOMAIN].
    returns None on error and session id on success

    Note: we are reimplementing the code from Schluter's library Authenticator, because
    that code dumps error message upon token expiration and this pollutes the logs. '''

    api = hass_domain[DATA_SCHLUTER_API];
    session = hass_domain[DATA_SCHLUTER_SESSION];
    expires = hass_domain[DATA_SCHLUTER_EXPIRES];

    if expires > datetime.utcnow():
        return session;

    _LOGGER.debug("schluter: reacquiring new session ID.");

    try:
        ## 
        ## As of 2022, one http session to Schluter cloud can last for months.
        ## Thus we could reuse it between the session id updates,
        ## but it seems to be safer to reestablish it periodically. 
        ##
        ## HACK: This is probably not a good idea because _http_session is not exposed by the API.
        api._http_session.close();

        response = api.get_session(hass_domain[DATA_SCHLUTER_USER],hass_domain[DATA_SCHLUTER_PASS]);
        data = response.json()
    except RequestException as ex:
        _LOGGER.error("Unable to connect to Schluter service: %s", ex);
        return None;
        
    if data["ErrorCode"] == 2:
        _LOGGER.error("Unable to auth to Schluter service: bad password");
        return None;
    elif data["ErrorCode"] == 1:
        _LOGGER.error("Unable to auth to Schluter service: bad email");
        return None;

    session_id = data["SessionId"];

    hass_domain[DATA_SCHLUTER_EXPIRES] = datetime.utcnow() + timedelta(hours=SCHLUTER_UPDATE_HOURS);
    hass_domain[DATA_SCHLUTER_SESSION] = session_id;

    return session_id;


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Schluter component."""
    _LOGGER.debug("Starting setup of schluter")

    conf = config[DOMAIN]
        
    user = conf.get(CONF_USERNAME);
    password = conf.get(CONF_PASSWORD);

    api_http_session = Session()
    api = Api(timeout=API_TIMEOUT, http_session=api_http_session)
    
    hass_domain = {
            DATA_SCHLUTER_API: api,
            DATA_SCHLUTER_USER: user,
            DATA_SCHLUTER_PASS: password,
            DATA_SCHLUTER_SESSION: None,
            DATA_SCHLUTER_EXPIRES: datetime.utcnow() - timedelta(hours=1),
    }

    sid = schluter_auth_update(hass_domain);

    if (sid is None):
        return False
    else:
        hass.data[DOMAIN] = hass_domain;
        discovery.load_platform(hass, Platform.CLIMATE, DOMAIN, {}, config)
        return True
