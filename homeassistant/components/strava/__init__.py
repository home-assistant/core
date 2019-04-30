from datetime import datetime, timedelta
import logging
import voluptuous as vol
from homeassistant.components.http import HomeAssistantView
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'

AUTH_CALLBACK_NAME = 'api:strava'
AUTH_CALLBACK_PATH = '/api/strava'

CONFIGURATOR_DESCRIPTION = 'To link your Strava account, ' \
                           'click the link, login, and authorize:'
CONFIGURATOR_LINK_NAME = 'Link Strava account'
CONFIGURATOR_SUBMIT_CAPTION = 'I authorized successfully'

DEFAULT_NAME = 'Strava'

DOMAIN = 'strava'

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    data = StravaData(hass, config.get(DOMAIN))

    if not data.is_authorized:
        await data.get_token()

    hass.data[DOMAIN] = data

    return True

class StravaData:

    def __init__(self, hass, config):
        from stravalib.client import Client

        self.client = Client()
        self._configurator = None
        self._token = None
        self._hass = hass
        self._config = config

        self._hass.http.register_view(StravaAuthCallbackView(self))

        self._client_id = config.get(CONF_CLIENT_ID)
        self._client_secret = config.get(CONF_CLIENT_SECRET)

        self.athletes = {}
        self.gears = {}
        self.clubs = {}

    @property
    def is_authorized(self):
        return self._token is not None

    @property
    def is_token_valid(self):
        if not self.is_authorized:
            _LOGGER.info("Not authorized")
            return False

        expires_at = datetime.fromtimestamp(self._token['expires_at'])
        if expires_at > datetime.now() + 300:
            return True

        _LOGGER.info("Token expired: %s", repr(self._token))
        return False

    async def get_token(self):
        if not self.is_authorized:
            store = self._hass.helpers.storage.Store(STORAGE_VERSION,
                                                     STORAGE_KEY)
            self._token = await store.async_load()

            if self._token:
                self.client.access_token = self._token['access_token']
            else:
                _LOGGER.info("Requesting token")
                await self.request_token()
                return

        expires_at = datetime.fromtimestamp(self._token['expires_at'])
        if expires_at < datetime.now():
            await self.refresh_token()

    async def authorize(self, code, hass):
        """ Request initial authorization. """
        self._token = await hass.async_add_executor_job(
            self.client.exchange_code_for_token,
            self._client_id,
            self._client_secret,
            code
        )

        store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        await store.async_save(self._token)

        if self.is_authorized:
            await hass.async_add_executor_job(
                hass.components.configurator.request_done,
                self._configurator
            )
            del self._configurator

        await async_setup(hass, self._config)

    async def request_token(self):
        """Request Strava access token."""

        callback_url = '{}{}'.format(self._hass.config.api.base_url,
                                     AUTH_CALLBACK_PATH)
        authorize_url = self.client.authorization_url(
            client_id=self._config.get(CONF_CLIENT_ID),
            redirect_uri=callback_url)

        self._configurator = \
            self._hass.components.configurator.async_request_config(
                DEFAULT_NAME, lambda _: None,
                link_name=CONFIGURATOR_LINK_NAME,
                link_url=authorize_url,
                description=CONFIGURATOR_DESCRIPTION,
                submit_caption=CONFIGURATOR_SUBMIT_CAPTION)

    async def refresh_token(self):
        """Renew Strava access token."""

        self._token = await self._hass.async_add_executor_job(
            self.client.refresh_access_token,
            self._client_id,
            self._client_secret,
            self._token['refresh_token'])

        store = self._hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        await store.async_save(self._token)

    def get_athlete(self, id):
        if id not in self.athletes:
            self.athletes[id] = StravaAthleteData(self, id)

        return self.athletes[id]

    def get_gear(self, id):
        if id not in self.gears:
            self.gears[id] = StravaGearData(self, id)

        return self.gears[id]

    def get_club(self, id):
        if id not in self.clubs:
            self.clubs[id] = StravaClubData(self, id)

        return self.clubs[id]


class StravaAthleteData:

    def __init__(self, data, id=None):
        self.id = id
        self.data = data

        self.details = None
        self.stats = None
        self.last_activity = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self, hass):
        await self.data.get_token()
        activities = await hass.async_add_executor_job(
            self.data.client.get_activities, None, None, 1)

        self.last_activity = next(activities)

        self.details = await hass.async_add_executor_job(
            self.data.client.get_athlete, self.id)
        self.stats = await hass.async_add_executor_job(
            self.data.client.get_athlete_stats, self.id)

class StravaClubData:

    def __init__(self, data, id):
        self.id = id
        self.data = data

        self.club = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self, hass):
        await self.data.get_token()
        self.club = await hass.async_add_executor_job(
            self.data.client.get_club, self.id)

class StravaGearData:

    def __init__(self, data, id):
        self.id = id
        self.data = data

        self.gear = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self, hass):
        await self.data.get_token()
        self.gear = await hass.async_add_executor_job(
            self.data.client.get_gear, self.id)

class StravaAuthCallbackView(HomeAssistantView):
    """Strava Authorization Callback View."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME

    def __init__(self, data):
        self._data = data

    async def get(self, request):
        hass = request.app['hass']
        code = request.query['code']

        await self._data.authorize(code, hass)
