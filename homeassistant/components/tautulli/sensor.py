"""A platform which allows you to get information from Tautulli."""
from datetime import timedelta

from pytautulli import PyTautulli
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

CONF_MONITORED_USERS = "monitored_users"

DEFAULT_NAME = "Tautulli"
DEFAULT_PORT = "8181"
DEFAULT_PATH = ""
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

TIME_BETWEEN_UPDATES = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_MONITORED_USERS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
        vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Create the Tautulli sensor."""

    name = config.get(CONF_NAME)
    host = config[CONF_HOST]
    port = config.get(CONF_PORT)
    path = config.get(CONF_PATH)
    api_key = config[CONF_API_KEY]
    monitored_conditions = config.get(CONF_MONITORED_CONDITIONS)
    user = config.get(CONF_MONITORED_USERS)
    use_ssl = config[CONF_SSL]
    verify_ssl = config.get(CONF_VERIFY_SSL)

    session = async_get_clientsession(hass, verify_ssl)
    tautulli = TautulliData(
        PyTautulli(
            api_token=api_key,
            hostname=host,
            session=session,
            verify_ssl=verify_ssl,
            port=port,
            ssl=use_ssl,
            base_api_path=path,
        )
    )

    await tautulli.async_update()
    if not tautulli.activity or not tautulli.home_stats or not tautulli.users:
        raise PlatformNotReady

    sensor = [TautulliSensor(tautulli, name, monitored_conditions, user)]

    async_add_entities(sensor, True)


class TautulliSensor(SensorEntity):
    """Representation of a Tautulli sensor."""

    def __init__(self, tautulli, name, monitored_conditions, users):
        """Initialize the Tautulli sensor."""
        self.tautulli = tautulli
        self.monitored_conditions = monitored_conditions
        self.usernames = users
        self.sessions = {}
        self.home = {}
        self._attributes = {}
        self._name = name
        self._state = None

    async def async_update(self):
        """Get the latest data from the Tautulli API."""
        await self.tautulli.async_update()
        if (
            not self.tautulli.activity
            or not self.tautulli.home_stats
            or not self.tautulli.users
        ):
            return

        self._attributes = {
            "stream_count": self.tautulli.activity.stream_count,
            "stream_count_direct_play": self.tautulli.activity.stream_count_direct_play,
            "stream_count_direct_stream": self.tautulli.activity.stream_count_direct_stream,
            "stream_count_transcode": self.tautulli.activity.stream_count_transcode,
            "total_bandwidth": self.tautulli.activity.total_bandwidth,
            "lan_bandwidth": self.tautulli.activity.lan_bandwidth,
            "wan_bandwidth": self.tautulli.activity.wan_bandwidth,
        }

        for stat in self.tautulli.home_stats:
            if stat.stat_id == "top_movies":
                self._attributes["Top Movie"] = (
                    stat.rows[0].title if stat.rows else None
                )
            elif stat.stat_id == "top_tv":
                self._attributes["Top TV Show"] = (
                    stat.rows[0].title if stat.rows else None
                )
            elif stat.stat_id == "top_users":
                self._attributes["Top User"] = stat.rows[0].user if stat.rows else None

        for user in self.tautulli.users:
            if (
                self.usernames
                and user.username not in self.usernames
                or user.username == "Local"
            ):
                continue
            self._attributes.setdefault(user.username, {})["Activity"] = None

        for session in self.tautulli.activity.sessions:
            if not self._attributes.get(session.username):
                continue

            self._attributes[session.username]["Activity"] = session.state
            if self.monitored_conditions:
                for key in self.monitored_conditions:
                    self._attributes[session.username][key] = getattr(session, key)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.tautulli.activity:
            return 0
        return self.tautulli.activity.stream_count

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:plex"

    @property
    def native_unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return "Watching"

    @property
    def extra_state_attributes(self):
        """Return attributes for the sensor."""
        return self._attributes


class TautulliData:
    """Get the latest data and update the states."""

    def __init__(self, api):
        """Initialize the data object."""
        self.api = api
        self.activity = None
        self.home_stats = None
        self.users = None

    @Throttle(TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from Tautulli."""
        self.activity = await self.api.async_get_activity()
        self.home_stats = await self.api.async_get_home_stats()
        self.users = await self.api.async_get_users()
