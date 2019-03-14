"""Support for The Movie Database API."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_API_KEY, ATTR_ID)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['tmdbsimple==2.2.0']

DOMAIN = 'tmdb'

_LOGGER = logging.getLogger(__name__)

CONF_MOVIE_LISTS = 'movie_lists'
CONF_TELEVISION_LISTS = 'television_lists'

ATTR_MEDIA = 'media'
ATTR_RELEASE_DATE = 'release_date'
ATTR_OVERVIEW = 'overview'
ATTR_POSTER_PATH = 'poster_path'
ATTR_TITLE = 'title'

LIST_TYPES = ['upcoming', 'now_playing', 'popular', 'top_rated']

SCAN_INTERVAL = timedelta(seconds=300)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_MOVIE_LISTS):
        vol.All(cv.ensure_list, [vol.In(LIST_TYPES)]),
    vol.Optional(CONF_TELEVISION_LISTS):
        vol.All(cv.ensure_list, [vol.In(LIST_TYPES)]),
})


def normalize_result(result):
    """Normailzes a TMDB result."""
    return {
        ATTR_ID: result.get(ATTR_ID),
        ATTR_RELEASE_DATE: result.get(ATTR_RELEASE_DATE),
        ATTR_OVERVIEW: result.get(ATTR_OVERVIEW),
        ATTR_POSTER_PATH: result.get(ATTR_POSTER_PATH),
        ATTR_TITLE: result.get(ATTR_TITLE)
    }


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up The Movie Database sensor platform."""
    import tmdbsimple as tmdb
    tmdb.API_KEY = config[CONF_API_KEY]
    sensors = []

    # get all movie sensors
    movie_lists = config.get(CONF_MOVIE_LISTS, [])
    tmdb_movie = tmdb.Movies()
    sensors += [TmdbSensor(list_type, tmdb_movie, 'movie')
                for list_type in movie_lists]

    # get all television sensors
    television_lists = config.get(CONF_TELEVISION_LISTS, [])
    tmdb_television = tmdb.TV()
    sensors += [TmdbSensor(list_type, tmdb_television, 'tv')
                for list_type in television_lists]

    add_entities(sensors, True)


class TmdbSensor(Entity):
    """Representation of a Movie Database sensor."""

    def __init__(self, list_type: str, tmdb, query_type):
        """Initialize the Reddit sensor."""
        self._list_type = list_type
        self._tmdb = tmdb
        self._query_type = query_type
        self._data = []

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._list_type, self._query_type)

    @property
    def state(self):
        """Return the state of the sensor."""
        return len(self._data)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_MEDIA: self._data
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return 'mdi:movie'

    def update(self):
        """Update data from The Movie Database API."""
        self._data = []

        if hasattr(self._tmdb, self._list_type):
            method_to_call = getattr(self._tmdb, self._list_type)

            try:
                results = method_to_call()
                self._data = [normalize_result(result)
                              for result in results['results']]

            except ConnectionError as err:
                _LOGGER.error("TMDB Sensor error %s", err)
