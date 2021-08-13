"""A platform which allows you to get information from Tautulli."""
from __future__ import annotations

from datetime import timedelta
from logging import Logger, getLogger
from typing import Any

from pytautulli import (
    PyTautulli,
    PyTautulliApiActivity,
    PyTautulliApiHomeStats,
    PyTautulliApiUser,
    PyTautulliConnectionException,
    PyTautulliException,
)
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

_LOGGER: Logger = getLogger(__name__)

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
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_MONITORED_USERS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
        vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Create the Tautulli sensor."""

    name = config[CONF_NAME]
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    users = config[CONF_MONITORED_USERS]
    verify_ssl = config[CONF_VERIFY_SSL]

    session = async_get_clientsession(hass, verify_ssl)
    client = PyTautulli(
        api_token=config[CONF_API_KEY],
        hostname=config[CONF_HOST],
        session=session,
        verify_ssl=verify_ssl,
        port=config[CONF_PORT],
        ssl=config[CONF_SSL],
        base_api_path=config[CONF_PATH],
    )
    try:
        await client.async_get_server_info()
    except PyTautulliConnectionException as exception:
        raise PlatformNotReady(exception) from exception
    except PyTautulliException as exception:
        _LOGGER.error(exception)
        return

    async_add_entities(
        [TautulliSensor(TautulliData(client), name, monitored_conditions, users)], True
    )


class TautulliSensor(SensorEntity):
    """Representation of a Tautulli sensor."""

    _attr_icon = "mdi:plex"
    _attr_native_unit_of_measurement = "Watching"

    def __init__(
        self,
        data: TautulliData,
        name: str,
        monitored_conditions: list[str],
        users: list[str],
    ):
        """Initialize the Tautulli sensor."""
        self._attr_name = name
        self.data = data
        self.monitored_conditions = monitored_conditions
        self.usernames = users

    async def async_update(self):
        """Get the latest data from the Tautulli API."""
        try:
            await self.data.async_update()
        except PyTautulliException as exception:
            _LOGGER.error(exception)
            self._attr_available = False
            return

        if not self.data.activity or not self.data.home_stats or not self.data.users:
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_native_value = self.data.activity.stream_count

        _attributes: dict[str, Any] = {
            "stream_count": self.data.activity.stream_count,
            "stream_count_direct_play": self.data.activity.stream_count_direct_play,
            "stream_count_direct_stream": self.data.activity.stream_count_direct_stream,
            "stream_count_transcode": self.data.activity.stream_count_transcode,
            "total_bandwidth": self.data.activity.total_bandwidth,
            "lan_bandwidth": self.data.activity.lan_bandwidth,
            "wan_bandwidth": self.data.activity.wan_bandwidth,
        }

        for stat in self.data.home_stats:
            if stat.stat_id == "top_movies":
                _attributes["Top Movie"] = stat.rows[0].title if stat.rows else None
            elif stat.stat_id == "top_tv":
                _attributes["Top TV Show"] = stat.rows[0].title if stat.rows else None
            elif stat.stat_id == "top_users":
                _attributes["Top User"] = stat.rows[0].user if stat.rows else None

        for user in self.data.users:
            if (
                self.usernames
                and user.username not in self.usernames
                or user.username == "Local"
            ):
                continue
            _attributes.setdefault(user.username, {})["Activity"] = None

        for session in self.data.activity.sessions:
            if not _attributes.get(session.username):
                continue

            _attributes[session.username]["Activity"] = session.state
            for key in self.monitored_conditions:
                _attributes[session.username][key] = session.__getattribute__(key)

        self._attr_extra_state_attributes = _attributes


class TautulliData:
    """Get the latest data and update the states."""

    activity: PyTautulliApiActivity | None = None
    home_stats: list[PyTautulliApiHomeStats] | None = None
    users: list[PyTautulliApiUser] | None = None

    def __init__(self, client: PyTautulli):
        """Initialize the data object."""
        self._client = client

    @Throttle(TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from Tautulli."""
        self.activity = await self._client.async_get_activity()
        self.home_stats = await self._client.async_get_home_stats()
        self.users = await self._client.async_get_users()
