"""The tests for the Season sensor platform."""
# pylint: disable=protected-access
import unittest
from datetime import datetime

import homeassistant.components.sensor.season as season

from tests.common import get_test_home_assistant


# pylint: disable=invalid-name
class TestSeason(unittest.TestCase):
    """Test the season platform."""

    DEVICE = None
    CONFIG_ASTRONOMICAL = {'type': 'astronomical'}
    CONFIG_METEOROLOGICAL = {'type': 'meteorological'}

    def add_devices(self, devices):
        """Mock add devices."""
        for device in devices:
            self.DEVICE = device

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_season_should_be_summer_northern_astonomical(self):
        """Test that season should be summer."""
        # A known day in summer
        summer_day = datetime(2017, 9, 3, 0, 0)
        current_season = season.get_season(summer_day, season.NORTHERN,
                                           season.TYPE_ASTRONOMICAL)
        self.assertEqual(season.STATE_SUMMER,
                         current_season)

    def test_season_should_be_summer_northern_meteorological(self):
        """Test that season should be summer."""
        # A known day in summer
        summer_day = datetime(2017, 8, 13, 0, 0)
        current_season = season.get_season(summer_day, season.NORTHERN,
                                           season.TYPE_METEOROLOGICAL)
        self.assertEqual(season.STATE_SUMMER,
                         current_season)

    def test_season_should_be_autumn_northern_astonomical(self):
        """Test that season should be autumn."""
        # A known day in autumn
        autumn_day = datetime(2017, 9, 23, 0, 0)
        current_season = season.get_season(autumn_day, season.NORTHERN,
                                           season.TYPE_ASTRONOMICAL)
        self.assertEqual(season.STATE_AUTUMN,
                         current_season)

    def test_season_should_be_autumn_northern_meteorological(self):
        """Test that season should be autumn."""
        # A known day in autumn
        autumn_day = datetime(2017, 9, 3, 0, 0)
        current_season = season.get_season(autumn_day, season.NORTHERN,
                                           season.TYPE_METEOROLOGICAL)
        self.assertEqual(season.STATE_AUTUMN,
                         current_season)

    def test_season_should_be_winter_northern_astonomical(self):
        """Test that season should be winter."""
        # A known day in winter
        winter_day = datetime(2017, 12, 25, 0, 0)
        current_season = season.get_season(winter_day, season.NORTHERN,
                                           season.TYPE_ASTRONOMICAL)
        self.assertEqual(season.STATE_WINTER,
                         current_season)

    def test_season_should_be_winter_northern_meteorological(self):
        """Test that season should be winter."""
        # A known day in winter
        winter_day = datetime(2017, 12, 3, 0, 0)
        current_season = season.get_season(winter_day, season.NORTHERN,
                                           season.TYPE_METEOROLOGICAL)
        self.assertEqual(season.STATE_WINTER,
                         current_season)

    def test_season_should_be_spring_northern_astonomical(self):
        """Test that season should be spring."""
        # A known day in spring
        spring_day = datetime(2017, 4, 1, 0, 0)
        current_season = season.get_season(spring_day, season.NORTHERN,
                                           season.TYPE_ASTRONOMICAL)
        self.assertEqual(season.STATE_SPRING,
                         current_season)

    def test_season_should_be_spring_northern_meteorological(self):
        """Test that season should be spring."""
        # A known day in spring
        spring_day = datetime(2017, 3, 3, 0, 0)
        current_season = season.get_season(spring_day, season.NORTHERN,
                                           season.TYPE_METEOROLOGICAL)
        self.assertEqual(season.STATE_SPRING,
                         current_season)

    def test_season_should_be_winter_southern_astonomical(self):
        """Test that season should be winter."""
        # A known day in winter
        winter_day = datetime(2017, 9, 3, 0, 0)
        current_season = season.get_season(winter_day, season.SOUTHERN,
                                           season.TYPE_ASTRONOMICAL)
        self.assertEqual(season.STATE_WINTER,
                         current_season)

    def test_season_should_be_winter_southern_meteorological(self):
        """Test that season should be winter."""
        # A known day in winter
        winter_day = datetime(2017, 8, 13, 0, 0)
        current_season = season.get_season(winter_day, season.SOUTHERN,
                                           season.TYPE_METEOROLOGICAL)
        self.assertEqual(season.STATE_WINTER,
                         current_season)

    def test_season_should_be_spring_southern_astonomical(self):
        """Test that season should be spring."""
        # A known day in spring
        spring_day = datetime(2017, 9, 23, 0, 0)
        current_season = season.get_season(spring_day, season.SOUTHERN,
                                           season.TYPE_ASTRONOMICAL)
        self.assertEqual(season.STATE_SPRING,
                         current_season)

    def test_season_should_be_spring_southern_meteorological(self):
        """Test that season should be spring."""
        # A known day in spring
        spring_day = datetime(2017, 9, 3, 0, 0)
        current_season = season.get_season(spring_day, season.SOUTHERN,
                                           season.TYPE_METEOROLOGICAL)
        self.assertEqual(season.STATE_SPRING,
                         current_season)

    def test_season_should_be_summer_southern_astonomical(self):
        """Test that season should be summer."""
        # A known day in summer
        summer_day = datetime(2017, 12, 25, 0, 0)
        current_season = season.get_season(summer_day, season.SOUTHERN,
                                           season.TYPE_ASTRONOMICAL)
        self.assertEqual(season.STATE_SUMMER,
                         current_season)

    def test_season_should_be_summer_southern_meteorological(self):
        """Test that season should be summer."""
        # A known day in summer
        summer_day = datetime(2017, 12, 3, 0, 0)
        current_season = season.get_season(summer_day, season.SOUTHERN,
                                           season.TYPE_METEOROLOGICAL)
        self.assertEqual(season.STATE_SUMMER,
                         current_season)

    def test_season_should_be_autumn_southern_astonomical(self):
        """Test that season should be spring."""
        # A known day in spring
        autumn_day = datetime(2017, 4, 1, 0, 0)
        current_season = season.get_season(autumn_day, season.SOUTHERN,
                                           season.TYPE_ASTRONOMICAL)
        self.assertEqual(season.STATE_AUTUMN,
                         current_season)

    def test_season_should_be_autumn_southern_meteorological(self):
        """Test that season should be autumn."""
        # A known day in autumn
        autumn_day = datetime(2017, 3, 3, 0, 0)
        current_season = season.get_season(autumn_day, season.SOUTHERN,
                                           season.TYPE_METEOROLOGICAL)
        self.assertEqual(season.STATE_AUTUMN,
                         current_season)

    def test_on_equator_results_in_none(self):
        """Test that season should be unknown."""
        # A known day in summer if astronomical and northern
        summer_day = datetime(2017, 9, 3, 0, 0)
        current_season = season.get_season(summer_day,
                                           season.EQUATOR,
                                           season.TYPE_ASTRONOMICAL)
        self.assertEqual(None, current_season)
