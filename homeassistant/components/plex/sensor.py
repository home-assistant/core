"""Support for Plex media server monitoring."""
from datetime import timedelta
import logging
import plexapi.exceptions
import requests.exceptions
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    CONF_SSL,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_SSL, DEFAULT_VERIFY_SSL
from .server import PlexServer

DEFAULT_NAME = "Plex"
_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TOKEN): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Plex sensor."""
    name = config.get(CONF_NAME)
    plex_host = config.get(CONF_HOST)
    plex_port = config.get(CONF_PORT)
    plex_token = config.get(CONF_TOKEN)
    verify_ssl = config.get(CONF_VERIFY_SSL)

    plex_url = "{}://{}:{}".format(
        "https" if config.get(CONF_SSL) else "http", plex_host, plex_port
    )

    try:
        plex_server = PlexServer(
            {CONF_URL: plex_url, CONF_TOKEN: plex_token, CONF_VERIFY_SSL: verify_ssl}
        )
        plex_server.connect()
    except (
        plexapi.exceptions.BadRequest,
        plexapi.exceptions.Unauthorized,
        plexapi.exceptions.NotFound,
    ) as error:
        _LOGGER.error(error)
        return

    add_entities([PlexSensor(name, plex_server)], True)


class PlexSensor(Entity):
    """Representation of a Plex now playing sensor."""

    def __init__(self, name, plex_server):
        """Initialize the sensor."""
        self._name = name
        self._state = None
        self._now_playing = []
        self._server = plex_server

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
