"""A platform which allows you to get information from Tautulli."""
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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import TautulliDataUpdateCoordinator

CONF_MONITORED_USERS = "monitored_users"

DEFAULT_NAME = "Tautulli"
DEFAULT_PORT = "8181"
DEFAULT_PATH = ""
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

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
    api_client = PyTautulli(
        api_token=api_key,
        hostname=host,
        session=session,
        verify_ssl=verify_ssl,
        port=port,
        ssl=use_ssl,
        base_api_path=path,
    )

    coordinator = TautulliDataUpdateCoordinator(hass=hass, api_client=api_client)

    entities = [TautulliSensor(coordinator, name, monitored_conditions, user)]

    async_add_entities(entities, True)


class TautulliSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Tautulli sensor."""

    coordinator: TautulliDataUpdateCoordinator

    def __init__(self, coordinator, name, monitored_conditions, users):
        """Initialize the Tautulli sensor."""
        super().__init__(coordinator)
        self.monitored_conditions = monitored_conditions
        self.usernames = users
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.activity:
            return 0
        return self.coordinator.activity.stream_count

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
        if (
            not self.coordinator.activity
            or not self.coordinator.home_stats
            or not self.coordinator.users
        ):
            return None

        _attributes = {
            "stream_count": self.coordinator.activity.stream_count,
            "stream_count_direct_play": self.coordinator.activity.stream_count_direct_play,
            "stream_count_direct_stream": self.coordinator.activity.stream_count_direct_stream,
            "stream_count_transcode": self.coordinator.activity.stream_count_transcode,
            "total_bandwidth": self.coordinator.activity.total_bandwidth,
            "lan_bandwidth": self.coordinator.activity.lan_bandwidth,
            "wan_bandwidth": self.coordinator.activity.wan_bandwidth,
        }

        for stat in self.coordinator.home_stats:
            if stat.stat_id == "top_movies":
                _attributes["Top Movie"] = stat.rows[0].title if stat.rows else None
            elif stat.stat_id == "top_tv":
                _attributes["Top TV Show"] = stat.rows[0].title if stat.rows else None
            elif stat.stat_id == "top_users":
                _attributes["Top User"] = stat.rows[0].user if stat.rows else None

        for user in self.coordinator.users:
            if (
                self.usernames
                and user.username not in self.usernames
                or user.username == "Local"
            ):
                continue
            _attributes.setdefault(user.username, {})["Activity"] = None

        for session in self.coordinator.activity.sessions:
            if not _attributes.get(session.username):
                continue

            _attributes[session.username]["Activity"] = session.state
            if self.monitored_conditions:
                for key in self.monitored_conditions:
                    _attributes[session.username][key] = getattr(session, key)

        return _attributes
