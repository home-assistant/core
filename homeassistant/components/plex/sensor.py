"""Support for Plex media server monitoring."""
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_SERVER_IDENTIFIER,
    DISPATCHERS,
    DOMAIN as PLEX_DOMAIN,
    NAME_FORMAT,
    PLEX_UPDATE_SENSOR_SIGNAL,
    SERVERS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Plex sensor from a config entry."""
    server_id = config_entry.data[CONF_SERVER_IDENTIFIER]
    plexserver = hass.data[PLEX_DOMAIN][SERVERS][server_id]
    sensor = PlexSensor(plexserver)
    async_add_entities([sensor])


class PlexSensor(Entity):
    """Representation of a Plex now playing sensor."""

    def __init__(self, plex_server):
        """Initialize the sensor."""
        self.sessions = []
        self._state = None
        self._now_playing = []
        self._server = plex_server
        self._name = NAME_FORMAT.format(plex_server.friendly_name)
        self._unique_id = f"sensor-{plex_server.machine_identifier}"

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        server_id = self._server.machine_identifier
        unsub = async_dispatcher_connect(
            self.hass,
            PLEX_UPDATE_SENSOR_SIGNAL.format(server_id),
            self.async_refresh_sensor,
        )
        self.hass.data[PLEX_DOMAIN][DISPATCHERS][server_id].append(unsub)

    @callback
    def async_refresh_sensor(self, sessions):
        """Set instance object and trigger an entity state update."""
        self.sessions = sessions
        self.async_schedule_update_ha_state(True)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the id of this plex client."""
        return self._unique_id

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return "Watching"

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:plex"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {content[0]: content[1] for content in self._now_playing}

    def update(self):
        """Update method for Plex sensor."""
        _LOGGER.debug("Refreshing sensor [%s]", self.unique_id)
        now_playing = []
        for sess in self.sessions:
            if sess.TYPE == "photo":
                _LOGGER.debug("Photo session detected, skipping: %s", sess)
                continue
            user = sess.usernames[0]
            device = sess.players[0].title
            now_playing_user = f"{user} - {device}"
            now_playing_title = ""

            if sess.TYPE in ["clip", "episode"]:
                # example:
                # "Supernatural (2005) - s01e13 - Route 666"
                season_title = sess.grandparentTitle
                if sess.show().year is not None:
                    season_title += f" ({sess.show().year!s})"
                season_episode = sess.seasonEpisode
                episode_title = sess.title
                now_playing_title = (
                    f"{season_title} - {season_episode} - {episode_title}"
                )
            elif sess.TYPE == "track":
                # example:
                # "Billy Talent - Afraid of Heights - Afraid of Heights"
                track_artist = sess.grandparentTitle
                track_album = sess.parentTitle
                track_title = sess.title
                now_playing_title = f"{track_artist} - {track_album} - {track_title}"
            else:
                # example:
                # "picture_of_last_summer_camp (2015)"
                # "The Incredible Hulk (2008)"
                now_playing_title = sess.title
                if sess.year is not None:
                    now_playing_title += f" ({sess.year})"

            now_playing.append((now_playing_user, now_playing_title))
        self._state = len(self.sessions)
        self._now_playing = now_playing

    @property
    def device_info(self):
        """Return a device description for device registry."""
        if self.unique_id is None:
            return None

        return {
            "identifiers": {(PLEX_DOMAIN, self._server.machine_identifier)},
            "manufacturer": "Plex",
            "model": "Plex Media Server",
            "name": "Activity Sensor",
            "sw_version": self._server.version,
        }
