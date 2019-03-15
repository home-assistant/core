"""The tests for The Movie Database platform."""
import unittest
from unittest.mock import patch

from homeassistant.components.tmdb.sensor import LIST_TYPES, DOMAIN
from homeassistant.setup import setup_component

from tests.common import (get_test_home_assistant,
                          MockDependency)

import logging
_LOGGER = logging.getLogger(__name__)

MOVIE_CONFIG = {
    'sensor': {
        'platform': DOMAIN,
        'api_key': 'test',
        'movie_lists': LIST_TYPES,
    }
}

TV_CONFIG = {
    'sensor': {
        'platform': DOMAIN,
        'api_key': 'test',
        'television_lists': LIST_TYPES,
    }
}

MOCK_RESULTS = {
    'results': [{}, {}]
}

MOCK_RESULTS_LENGTH = len(MOCK_RESULTS['results'])


class MockTmdbSimple():
    """Mock class for tmdbsimple library."""

    def __init__(self):
        """Add mock data for API return."""
        self._data = MOCK_RESULTS

    def upcoming(self):
        """Return list upcoming movies."""
        return self._data

    def now_playing(self):
        """Return list of now playing movies."""
        return self._data

    def popular(self):
        """Return list popular movies."""
        return self._data

    def top_rated(self):
        """Return list of top rated movies."""
        return self._data


class TestTmdbSetup(unittest.TestCase):
    """Test the Dark Sky platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.entities = []

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @MockDependency('tmdbsimple')
    @patch('tmdbsimple.Movies', new=MockTmdbSimple)
    def test_setup_with_movie_config(self, mock_tmdbsimple):
        """Test the platform setup with movie configuration."""
        setup_component(self.hass, 'sensor', MOVIE_CONFIG)

        state = self.hass.states.get('sensor.tmdb_upcoming_movie')
        assert int(state.state) == MOCK_RESULTS_LENGTH

        state = self.hass.states.get('sensor.tmdb_now_playing_movie')
        assert int(state.state) == MOCK_RESULTS_LENGTH

        state = self.hass.states.get('sensor.tmdb_popular_movie')
        assert int(state.state) == MOCK_RESULTS_LENGTH

        state = self.hass.states.get('sensor.tmdb_top_rated_movie')
        assert int(state.state) == MOCK_RESULTS_LENGTH

    @MockDependency('tmdbsimple')
    @patch('tmdbsimple.TV', new=MockTmdbSimple)
    def test_setup_with_tv_config(self, mock_tmdbsimple):
        """Test the platform setup with tv configuration."""
        setup_component(self.hass, 'sensor', TV_CONFIG)

        state = self.hass.states.get('sensor.tmdb_upcoming_tv')
        assert int(state.state) == MOCK_RESULTS_LENGTH

        state = self.hass.states.get('sensor.tmdb_now_playing_tv')
        assert int(state.state) == MOCK_RESULTS_LENGTH

        state = self.hass.states.get('sensor.tmdb_popular_tv')
        assert int(state.state) == MOCK_RESULTS_LENGTH

        state = self.hass.states.get('sensor.tmdb_top_rated_tv')
        assert int(state.state) == MOCK_RESULTS_LENGTH