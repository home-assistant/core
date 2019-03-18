from datetime import datetime
import logging
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['stravalib>=0.10.2']

_LOGGER = logging.getLogger(__name__)

CONF_CACHE_PATH = 'cache_path'
CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'

AUTH_CALLBACK_NAME = 'api:strava'
AUTH_CALLBACK_PATH = '/api/strava'

CONFIGURATOR_DESCRIPTION = 'To link your Strava account, ' \
                           'click the link, login, and authorize:'
CONFIGURATOR_LINK_NAME = 'Link Strava account'
CONFIGURATOR_SUBMIT_CAPTION = 'I authorized successfully'

DEFAULT_CACHE_PATH = '.strava-token-cache'
DEFAULT_NAME = 'Strava'

DEPENDENCIES = ['http']

DOMAIN = 'strava'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_CACHE_PATH): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


class TokenExpired(Exception):
    pass


class StravaData:

    def __init__(self, hass, config):
        from stravalib.client import Client

        self.client = Client()
        self.configurator = None
        self._token = None
        self._hass = hass
        self._config = config

        self._hass.http.register_view(StravaAuthCallbackView(self))

        # Some settings
        self._path = config.get(CONF_CACHE_PATH,
                                hass.config.path(DEFAULT_CACHE_PATH))
        self._client_id = config.get(CONF_CLIENT_ID)
        self._client_secret = config.get(CONF_CLIENT_SECRET)

        try:
            self._read_token_cache()

            expires_at = datetime.fromtimestamp(self._token['expires_at'])
            if expires_at < datetime.now():
                _LOGGER.info("Strava token expired. Renewing token.")

                self.renew_token()
            else:
                self.client.access_token = self._token['access_token']

        except:
            _LOGGER.info("No Strava token found. Starting authorization.")

            self.request_token()

    @property
    def is_authorized(self):
        return self._token is not None

    def _read_token_cache(self):
        """ Read token infos from cache file. """

        import json

        with open(self._path) as f:
            self._token = json.load(f)

    def _update_token_cache(self):
        """ Save token infos to cache file. """

        import json

        with open(self._path, 'w') as f:
            json.dump(self._token, f)

    def authorize(self, code, hass):
        self._token = self.client.exchange_code_for_token(
            client_id=self._client_id,
            client_secret=self._client_secret,
            code=code)

        self._update_token_cache()

        hass.async_add_job(setup, hass, self._config)

    def request_token(self):
        """Request Strava access token."""

        callback_url = '{}{}'.format(self._hass.config.api.base_url,
                                     AUTH_CALLBACK_PATH)
        authorize_url = self.client.authorization_url(
            client_id=self._config.get(CONF_CLIENT_ID),
            redirect_uri=callback_url)

        self.configurator = self._hass.components.configurator.request_config(
            DEFAULT_NAME, lambda _: None,
            link_name=CONFIGURATOR_LINK_NAME,
            link_url=authorize_url,
            description=CONFIGURATOR_DESCRIPTION,
            submit_caption=CONFIGURATOR_SUBMIT_CAPTION)

    def renew_token(self):
        """Renew Strava access token."""

        expires_at = datetime.fromtimestamp(self._token['expires_at'])
        if expires_at > datetime.now() + 300:
            _LOGGER.info("Token still valid for 5 minutes. Postponing renewal")
            return

        self._token = self.client.refresh_access_token(
            client_id=self._client_id,
            client_secret=self._client_secret,
            refresh_token=self._token['refresh_token'])

        self._update_token_cache()


class StravaAuthCallbackView(HomeAssistantView):
    """Strava Authorization Callback View."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME

    def __init__(self, data):
        self._data = data

    @callback
    def get(self, request):
        hass = request.app['hass']
        code = request.query['code']

        self._data.authorize(code, hass)

def setup(hass, config):
    if hass.data.get(DOMAIN) is None:
        hass.data[DOMAIN] = StravaData(hass, config.get(DOMAIN))

    data = hass.data.get(DOMAIN)
    if data.is_authorized and data.configurator:
        hass.components.configurator.request_done(data.configurator)

    return True
