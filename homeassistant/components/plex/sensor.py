"""Support for Plex media server monitoring."""
from datetime import timedelta
import logging

import plexapi.exceptions
import requests.exceptions

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import DOMAIN as PLEX_DOMAIN, SERVERS

DEFAULT_NAME = "Plex"
_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Plex sensor."""
    if discovery_info is None:
        return

    plexserver = list(hass.data[PLEX_DOMAIN][SERVERS].values())[0]
    add_entities([PlexSensor(plexserver)], True)


class PlexSensor(Entity):
    """Representation of a Plex now playing sensor."""

    def __init__(self, plex_server):
        """Initialize the sensor."""
        self._name = DEFAULT_NAME
        self._state = None
        self._now_playing = []
        self._server = plex_server
        self._unique_id = f"sensor-{plex_server.machine_identifier}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the id of this plex client."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return "Watching"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {content[0]: content[1] for content in self._now_playing}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update method for Plex sensor."""
        try:
            sessions = self._server.sessions()
        except plexapi.exceptions.BadRequest:
            _LOGGER.error(
                "Error listing current Plex sessions on %s", self._server.friendly_name
            )
            return
        except requests.exceptions.RequestException as ex:
            _LOGGER.warning(
                "Temporary error connecting to %s (%s)", self._server.friendly_name, ex
            )
            return

        now_playing = []
        for sess in sessions:
            user = sess.usernames[0]
            device = sess.players[0].title
            now_playing_user = f"{user} - {device}"
            now_playing_title = ""

            if sess.TYPE == "episode":
                # example:
                # "Supernatural (2005) - S01 · E13 - Route 666"
                season_title = sess.grandparentTitle
                if sess.show().year is not None:
                    season_title += " ({0})".format(sess.show().year)
                season_episode = "S{0}".format(sess.parentIndex)
                if sess.index is not None:
                    season_episode += f" · E{sess.index}"
                episode_title = sess.title
                now_playing_title = "{0} - {1} - {2}".format(
                    season_title, season_episode, episode_title
                )
            elif sess.TYPE == "track":
                # example:
                # "Billy Talent - Afraid of Heights - Afraid of Heights"
                track_artist = sess.grandparentTitle
                track_album = sess.parentTitle
                track_title = sess.title
                now_playing_title = "{0} - {1} - {2}".format(
                    track_artist, track_album, track_title
                )
            else:
                # example:
                # "picture_of_last_summer_camp (2015)"
                # "The Incredible Hulk (2008)"
                now_playing_title = sess.title
                if sess.year is not None:
                    now_playing_title += f" ({sess.year})"

            now_playing.append((now_playing_user, now_playing_title))
        self._state = len(sessions)
        self._now_playing = now_playing
