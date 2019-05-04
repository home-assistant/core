"""The Strava component."""

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

CONFIGURATOR_DESCRIPTION = "To link your Strava account, " \
                           "click the link, login, and authorize:"
CONFIGURATOR_LINK_NAME = "Link Strava account"
CONFIGURATOR_SUBMIT_CAPTION = "I authorized successfully"

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
    """Setups Strava platform."""
    data = StravaData(hass, config.get(DOMAIN))

    if not data.is_authorized:
        await data.get_token()

    hass.data[DOMAIN] = data

    return True


class StravaData:
    """A model which stores the Strava data."""

    def __init__(self, hass, config):
        """Initialize strava data model."""
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
        """Check if there is a (possiblly expired) OAuth2 token."""
        return self._token is not None

    @property
    def is_token_valid(self):
        """Check if OAuth2 token is present and not expired."""
        if not self.is_authorized:
            _LOGGER.error("Not authorized")
            return False

        expires_at = datetime.fromtimestamp(self._token['expires_at'])
        if expires_at > datetime.now() + 300:
            return True

        _LOGGER.info("Token expired: %s", repr(self._token))
        return False

    async def get_token(self):
        """Load the OAuth2 token from the store."""
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
        """Request initial authorization."""
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

    def get_athlete(self, sid):
        """Get existing Athlete model or create if not existing."""
        if id not in self.athletes:
            self.athletes[sid] = StravaAthleteData(self, sid)

        return self.athletes[sid]

    def get_gear(self, sid):
        """Get existing Gear model or create if not existing."""
        if id not in self.gears:
            self.gears[sid] = StravaGearData(self, sid)

        return self.gears[sid]

    def get_club(self, sid):
        """Get existing Club model or create if not existing."""
        if id not in self.clubs:
            self.clubs[sid] = StravaClubData(self, sid)

        return self.clubs[sid]


class StravaAthleteData:
    """Strava athlete data model."""

    def __init__(self, data, sid=None):
        """Initialize Strava athlete data model."""
        self.strava_id = sid
        self.data = data

        self.details = None
        self.stats = None
        self.last_activity = None

    async def update_last_actitivity(self, hass):
        """Update last Strava activity."""
        def get_last_activity(client):
            activities = client.get_activities(limit=1)
            last = next(activities)
            detailed = client.get_activity(last.id, True)

            return detailed

        self.last_activity = await hass.async_add_executor_job(
            get_last_activity, self.data.client)

        _LOGGER.debug("Fetched last activity")

    async def update_details(self, hass):
        """Update Strava athlete details."""
        self.details = await hass.async_add_executor_job(
            self.data.client.get_athlete, self.strava_id)

        _LOGGER.debug("Fetched athlete details")

    async def update_stats(self, hass):
        """Update Strava athlete statistics."""
        self.stats = await hass.async_add_executor_job(
            self.data.client.get_athlete_stats, self.strava_id)

        _LOGGER.debug("Fetched athlete statistics")

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self, hass):
        """Updata Strava athlete data model."""
        import asyncio

        # Request or refresh token
        await self.data.get_token()

        await asyncio.gather(
            self.update_last_actitivity(hass),
            self.update_details(hass),
            self.update_stats(hass)
        )


class StravaClubData:
    """Strava club data model."""

    def __init__(self, data, sid):
        """Initialize Strava club data model."""
        self.strava_id = sid
        self.data = data

        self.club = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self, hass):
        """Update Strava club data model."""
        await self.data.get_token()
        self.club = await hass.async_add_executor_job(
            self.data.client.get_club, self.strava_id)


class StravaGearData:
    """Strava gear data model."""

    def __init__(self, data, sid):
        """Initialize Strava gear data model."""
        self.strava_id = sid
        self.data = data

        self.gear = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self, hass):
        """Update Strava gear data model."""
        await self.data.get_token()
        self.gear = await hass.async_add_executor_job(
            self.data.client.get_gear, self.strava_id)


class StravaAuthCallbackView(HomeAssistantView):
    """Strava Authorization Callback View."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME

    def __init__(self, data):
        """Initialize Strava Authorization Callback View."""
        self._data = data

    async def get(self, request):
        """Get Strava Authorization Callback View."""
        hass = request.app['hass']
        code = request.query['code']

        await self._data.authorize(code, hass)
