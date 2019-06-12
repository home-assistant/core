"""The tests for the Season sensor platform."""
# pylint: disable=protected-access
import unittest
from datetime import datetime

from homeassistant.setup import setup_component
import homeassistant.components.season.sensor as season

from tests.common import get_test_home_assistant


HEMISPHERE_NORTHERN = {
    'homeassistant': {
        'latitude': '48.864716',
        'longitude': '2.349014',
    },
    'sensor': {
        'platform': 'season',
        'type': 'astronomical',
    }
}

HEMISPHERE_SOUTHERN = {
    'homeassistant': {
        'latitude': '-33.918861',
        'longitude': '18.423300',
    },
    'sensor': {
        'platform': 'season',
        'type': 'astronomical',
    }
}

HEMISPHERE_EQUATOR = {
    'homeassistant': {
        'latitude': '0',
        'longitude': '-51.065100',
    },
    'sensor': {
        'platform': 'season',
        'type': 'astronomical',
    }
}

HEMISPHERE_EMPTY = {
    'homeassistant': {
    },
    'sensor': {
        'platform': 'season',
        'type': 'meteorological',
    }
}


# pylint: disable=invalid-name
class TestSeason(unittest.TestCase):
    """Test the season platform."""

    DEVICE = None
    CONFIG_ASTRONOMICAL = {'type': 'astronomical'}
    CONFIG_METEOROLOGICAL = {'type': 'meteorological'}

    def add_entities(self, devices):
        """Mock add devices."""
        for device in devices:
            self.DEVICE = device

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_season_should_be_summer_northern_astronomical(self):
        """Test that season should be summer."""
        # A known day in summer
        summer_day = datetime(2017, 9, 3, 0, 0)
        current_season = season.get_season(summer_day, season.NORTHERN,
                                           season.TYPE_ASTRONOMICAL)
        assert season.STATE_SUMMER == \
            current_season

    def test_season_should_be_summer_northern_meteorological(self):
        """Test that season should be summer."""
        # A known day in summer
        summer_day = datetime(2017, 8, 13, 0, 0)
        current_season = season.get_season(summer_day, season.NORTHERN,
                                           season.TYPE_METEOROLOGICAL)
        assert season.STATE_SUMMER == \
            current_season

    def test_season_should_be_autumn_northern_astronomical(self):
        """Test that season should be autumn."""
        # A known day in autumn
        autumn_day = datetime(2017, 9, 23, 0, 0)
        current_season = season.get_season(autumn_day, season.NORTHERN,
                                           season.TYPE_ASTRONOMICAL)
        assert season.STATE_AUTUMN == \
            current_season

    def test_season_should_be_autumn_northern_meteorological(self):
        """Test that season should be autumn."""
        # A known day in autumn
        autumn_day = datetime(2017, 9, 3, 0, 0)
        current_season = season.get_season(autumn_day, season.NORTHERN,
                                           season.TYPE_METEOROLOGICAL)
        assert season.STATE_AUTUMN == \
            current_season

    def test_season_should_be_winter_northern_astronomical(self):
        """Test that season should be winter."""
        # A known day in winter
        winter_day = datetime(2017, 12, 25, 0, 0)
        current_season = season.get_season(winter_day, season.NORTHERN,
                                           season.TYPE_ASTRONOMICAL)
        assert season.STATE_WINTER == \
            current_season

    def test_season_should_be_winter_northern_meteorological(self):
        """Test that season should be winter."""
        # A known day in winter
        winter_day = datetime(2017, 12, 3, 0, 0)
        current_season = season.get_season(winter_day, season.NORTHERN,
                                           season.TYPE_METEOROLOGICAL)
        assert season.STATE_WINTER == \
            current_season

    def test_season_should_be_spring_northern_astronomical(self):
        """Test that season should be spring."""
        # A known day in spring
        spring_day = datetime(2017, 4, 1, 0, 0)
        current_season = season.get_season(spring_day, season.NORTHERN,
                                           season.TYPE_ASTRONOMICAL)
        assert season.STATE_SPRING == \
            current_season

    def test_season_should_be_spring_northern_meteorological(self):
        """Test that season should be spring."""
        # A known day in spring
        spring_day = datetime(2017, 3, 3, 0, 0)
        current_season = season.get_season(spring_day, season.NORTHERN,
                                           season.TYPE_METEOROLOGICAL)
        assert season.STATE_SPRING == \
            current_season

    def test_season_should_be_winter_southern_astronomical(self):
        """Test that season should be winter."""
        # A known day in winter
        winter_day = datetime(2017, 9, 3, 0, 0)
        current_season = season.get_season(winter_day, season.SOUTHERN,
                                           season.TYPE_ASTRONOMICAL)
        assert season.STATE_WINTER == \
            current_season

    def test_season_should_be_winter_southern_meteorological(self):
        """Test that season should be winter."""
        # A known day in winter
        winter_day = datetime(2017, 8, 13, 0, 0)
        current_season = season.get_season(winter_day, season.SOUTHERN,
                                           season.TYPE_METEOROLOGICAL)
        assert season.STATE_WINTER == \
            current_season

    def test_season_should_be_spring_southern_astronomical(self):
        """Test that season should be spring."""
        # A known day in spring
        spring_day = datetime(2017, 9, 23, 0, 0)
        current_season = season.get_season(spring_day, season.SOUTHERN,
                                           season.TYPE_ASTRONOMICAL)
        assert season.STATE_SPRING == \
            current_season

    def test_season_should_be_spring_southern_meteorological(self):
        """Test that season should be spring."""
        # A known day in spring
        spring_day = datetime(2017, 9, 3, 0, 0)
        current_season = season.get_season(spring_day, season.SOUTHERN,
                                           season.TYPE_METEOROLOGICAL)
        assert season.STATE_SPRING == \
            current_season

    def test_season_should_be_summer_southern_astronomical(self):
        """Test that season should be summer."""
        # A known day in summer
        summer_day = datetime(2017, 12, 25, 0, 0)
        current_season = season.get_season(summer_day, season.SOUTHERN,
                                           season.TYPE_ASTRONOMICAL)
        assert season.STATE_SUMMER == \
            current_season

    def test_season_should_be_summer_southern_meteorological(self):
        """Test that season should be summer."""
        # A known day in summer
        summer_day = datetime(2017, 12, 3, 0, 0)
        current_season = season.get_season(summer_day, season.SOUTHERN,
                                           season.TYPE_METEOROLOGICAL)
        assert season.STATE_SUMMER == \
            current_season

    def test_season_should_be_autumn_southern_astronomical(self):
        """Test that season should be spring."""
        # A known day in spring
        autumn_day = datetime(2017, 4, 1, 0, 0)
        current_season = season.get_season(autumn_day, season.SOUTHERN,
                                           season.TYPE_ASTRONOMICAL)
        assert season.STATE_AUTUMN == \
            current_season

    def test_season_should_be_autumn_southern_meteorological(self):
        """Test that season should be autumn."""
        # A known day in autumn
        autumn_day = datetime(2017, 3, 3, 0, 0)
        current_season = season.get_season(autumn_day, season.SOUTHERN,
                                           season.TYPE_METEOROLOGICAL)
        assert season.STATE_AUTUMN == \
            current_season

    def test_on_equator_results_in_none(self):
        """Test that season should be unknown."""
        # A known day in summer if astronomical and northern
        summer_day = datetime(2017, 9, 3, 0, 0)
        current_season = season.get_season(summer_day,
                                           season.EQUATOR,
                                           season.TYPE_ASTRONOMICAL)
        assert current_season is None

    def test_setup_hemisphere_northern(self):
        """Test platform setup of northern hemisphere."""
        self.hass.config.latitude = HEMISPHERE_NORTHERN[
            'homeassistant']['latitude']
        assert setup_component(self.hass, 'sensor', HEMISPHERE_NORTHERN)
        assert self.hass.config.as_dict()['latitude'] == \
            HEMISPHERE_NORTHERN['homeassistant']['latitude']
        state = self.hass.states.get('sensor.season')
        assert state.attributes.get('friendly_name') == 'Season'

    def test_setup_hemisphere_southern(self):
        """Test platform setup of southern hemisphere."""
        self.hass.config.latitude = HEMISPHERE_SOUTHERN[
            'homeassistant']['latitude']
        assert setup_component(self.hass, 'sensor', HEMISPHERE_SOUTHERN)
        assert self.hass.config.as_dict()['latitude'] == \
            HEMISPHERE_SOUTHERN['homeassistant']['latitude']
        state = self.hass.states.get('sensor.season')
        assert state.attributes.get('friendly_name') == 'Season'

    def test_setup_hemisphere_equator(self):
        """Test platform setup of equator."""
        self.hass.config.latitude = HEMISPHERE_EQUATOR[
            'homeassistant']['latitude']
        assert setup_component(self.hass, 'sensor', HEMISPHERE_EQUATOR)
        assert self.hass.config.as_dict()['latitude'] == \
            HEMISPHERE_EQUATOR['homeassistant']['latitude']
        state = self.hass.states.get('sensor.season')
        assert state.attributes.get('friendly_name') == 'Season'

    def test_setup_hemisphere_empty(self):
        """Test platform setup of missing latlong."""
        self.hass.config.latitude = None
        assert setup_component(self.hass, 'sensor', HEMISPHERE_EMPTY)
        assert self.hass.config.as_dict()['latitude']is None
