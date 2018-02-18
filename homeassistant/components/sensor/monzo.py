"""Monzo Sensor.

Used to create a sensor in Home Assistant that will return
the current balance of a specified monzo account.
"""
import logging
import json
import time
import urllib.parse
import random

from homeassistant.helpers.entity import Entity
from homeassistant.core import callback
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (
    CONF_NAME)
from requests import post

REQUIREMENTS = ['monzo==0.5.3']

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:credit-card'


DEFAULT_CACHE_PATH = '.monzo-token-cache'
AUTH_CALLBACK_PATH = '/api/monzo'
AUTH_CALLBACK_NAME = 'api:monzo'
DEFAULT_NAME = 'Monzo Balance'
DOMAIN = 'monzo'
CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_CACHE_PATH = 'cache_path'
CONF_CURRENT_ACCOUNT = 'current_account'

CONFIGURATOR_LINK_NAME = 'Link Monzo account'
CONFIGURATOR_SUBMIT_CAPTION = 'I authorized successfully'
CONFIGURATOR_DESCRIPTION = 'To link your Monzo account, ' \
                           'click the link, login, and authorize:'


def is_token_expired(token_info):
    """Return true if the token has expired."""
    now = int(time.time())
    return token_info['expires_at'] - now < 60


def request_configuration(hass, config, add_devices, request_url):
    """Request Monzo authorization."""
    configurator = hass.components.configurator
    hass.data[DOMAIN] = configurator.request_config(
        DEFAULT_NAME, lambda _: None,
        link_name=CONFIGURATOR_LINK_NAME,
        link_url=request_url,
        description=CONFIGURATOR_DESCRIPTION,
        submit_caption=CONFIGURATOR_SUBMIT_CAPTION)


def setup_platform(hass, config, add_devices, device_discovery=None):
    """Setup the monzo platform."""
    client_id = config.get(CONF_CLIENT_ID)
    client_secret = config.get(CONF_CLIENT_SECRET)
    callback_url = '{}{}'.format(hass.config.api.base_url, AUTH_CALLBACK_PATH)
    cache = config.get(CONF_CACHE_PATH, hass.config.path(DEFAULT_CACHE_PATH))
    current_account = config.get(CONF_CURRENT_ACCOUNT, False)
    oauth = AuthClient(client_id,
                       client_secret,
                       callback_url,
                       cache_path=cache)

    token_info = oauth.get_cached_token()
    if not token_info:
        hass.http.register_view(MonzoAuthCallbackView(
            config, add_devices, oauth))
        request_configuration(hass,
                              config,
                              add_devices,
                              oauth.get_authorize_url())
        return
    if hass.data.get(DOMAIN):
        configurator = hass.components.configurator
        configurator.request_done(hass.data.get(DOMAIN))
        del hass.data[DOMAIN]
    sensor = MonzoSensor(oauth,
                         current_account,
                         config.get(CONF_NAME, DEFAULT_NAME))
    add_devices([sensor])


class AuthClient():
    """Used to authenticate with Monzo."""

    REQUEST_TOKEN_URL = 'https://auth.getmondo.co.uk'
    ACCESS_TOKEN_URL = 'https://api.monzo.com/oauth2/token'

    def __init__(self,
                 client_id,
                 client_secret,
                 redirect_uri,
                 state=None,
                 cache_path=None):
        """Create an oauth client to talk to monzo."""
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.state = state
        if state is None:
            self.state = self.__generate_nonce(8)
        self.cache_path = cache_path
        self.token_info = None

    def get_authorize_url(self, state=None):
        """Get the URL to use to authorize this app."""
        payload = {'client_id': self.client_id,
                   'response_type': 'code',
                   'redirect_uri': self.redirect_uri}

        if state is None:
            state = self.state
        if state is not None:
            payload['state'] = state

        urlparams = urllib.parse.urlencode(payload)
        return "%s?%s" % (self.REQUEST_TOKEN_URL, urlparams)

    def get_cached_token(self):
        """Get a cached auth token."""
        token_info = None
        if self.cache_path:
            try:
                file = open(self.cache_path)
                token_info_string = file.read()
                file.close()
                token_info = json.loads(token_info_string)

                if is_token_expired(token_info):
                    token_info = self.refresh_access_token(
                        token_info['refresh_token'])

            except IOError:
                pass
        return token_info

    def refresh_access_token(self, refresh_token):
        """Refreshe the access token."""
        payload = {'refresh_token': refresh_token,
                   'grant_type': 'refresh_token',
                   'client_secret': self.client_secret,
                   'client_id': self.client_id}
        response = post(self.ACCESS_TOKEN_URL, data=payload)
        if response.status_code != 200:
            _LOGGER.warning("couldn't refresh token: code:"
                            + str(response.status_code)
                            + " reason:"
                            + response.reason)
            return None
        token_info = response.json()
        token_info = self.__add_custom_values_to_token(token_info)
        if 'refresh_token' not in token_info:
            token_info['refresh_token'] = refresh_token
        self.__save_token_info(token_info)
        return token_info

    def get_access_token(self, state, code):
        """Retrieve the access token from Monzo."""
        _LOGGER.info("Access Token from Monzo recieved. Processing now.")
        if state != self.state:
            _LOGGER.error("The state does not match what we sent.")
            return

        post_url_params = {'grant_type': 'authorization_code',
                           'client_id': self.client_id,
                           'client_secret': self.client_secret,
                           'redirect_uri': self.redirect_uri,
                           'code': code}

        response = post(self.ACCESS_TOKEN_URL, data=post_url_params)

        if response.status_code is not 200:
            raise MonzoOauthError(response.reason)

        token_info = response.json()
        token_info = self.__add_custom_values_to_token(token_info)

        self.__save_token_info(token_info)

        return token_info

    @staticmethod
    def __add_custom_values_to_token(token_info):
        """Store some values that aren't directly provided by the response."""
        token_info['expires_at'] = int(time.time()) + token_info['expires_in']
        return token_info

    def __save_token_info(self, token_info):
        if self.cache_path:
            try:
                file = open(self.cache_path, 'w')
                file.write(json.dumps(token_info))
                file.close()
            except IOError:
                _LOGGER.warning("couldn't write token cache to "
                                + self.cache_path)

    @staticmethod
    def __generate_nonce(length=8):
        """Generate pseudorandom number."""
        return ''.join([str(random.randint(0, 9)) for i in range(length)])


class MonzoAccountError(Exception):
    """Unable to find the given account."""

    pass


class MonzoOauthError(Exception):
    """Error authenticating with Monzo."""

    pass


class MonzoAuthCallbackView(HomeAssistantView):
    """Monzo Authorization Callback View."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME

    def __init__(self, config, add_devices, oauth):
        """Initialize."""
        self.config = config
        self.add_devices = add_devices
        self.oauth = oauth

    @callback
    def get(self, request):
        """Receive authorization token."""
        hass = request.app['hass']

        state = request.query['state']
        code = request.query['code']
        self.oauth.get_access_token(state, code)

        hass.async_add_job(setup_platform, hass, self.config, self.add_devices)


class MonzoSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, oauth, current_account, name):
        """Create a Monzo sensor."""
        self._name = name
        self._oauth = oauth
        self._current_account = current_account
        self._token_info = self._oauth.get_cached_token()
        self._currency = None
        self._client = None
        self._state = None
        self._account_id = None

    def refresh_monzo_instance(self):
        """Refresh the monzo instance."""
        import monzo.monzo
        token_refreshed = False
        need_token = (self._token_info is None or
                      is_token_expired(self._token_info))
        if need_token:
            new_token = \
                self._oauth.refresh_access_token(
                    self._token_info['refresh_token'])
            # skip when refresh failed
            if new_token is None:
                return

            self._token_info = new_token
            token_refreshed = True
        if self._client is None or token_refreshed:
            self._client = \
                monzo.monzo.Monzo(self._token_info.get('access_token'))
            account = None
            if self._current_account:
                accounts = self._client.get_accounts()['accounts']
                account = next(
                    acc for acc in accounts if acc['type'] == 'uk_retail')
            else:
                account = self._client.get_first_account()
            if not account:
                raise MonzoAccountError('Account could not be found')
            self._account_id = account['id']

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._currency

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self.refresh_monzo_instance()

        if is_token_expired(self._token_info):
            _LOGGER.warning("Monzo failed to update, token expired.")
            return

        balance = self._client.get_balance(self._account_id)
        self._state = balance['balance']/100
        currency = balance['currency']
        if currency == 'GBP':
            currency = '£'

        self._currency = currency
