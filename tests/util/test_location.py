"""Test Home Assistant location util methods."""
# pylint: disable=too-many-public-methods
import unittest

import homeassistant.util.location as location_util

# Paris
COORDINATES_PARIS = (48.864716, 2.349014)
# New York
COORDINATES_NEW_YORK = (40.730610, -73.935242)

# Results for the assertion (vincenty algorithm):
#      Distance [km]   Distance [miles]
# [0]  5846.39         3632.78
# [1]  5851            3635
#
# [0]: http://boulter.com/gps/distance/
# [1]: https://www.wolframalpha.com/input/?i=from+paris+to+new+york
DISTANCE_KM = 5846.39
DISTANCE_MILES = 3632.78


class TestLocationUtil(unittest.TestCase):
    """Test util location methods."""

    def test_get_distance(self):
        """Test getting the distance."""
        meters = location_util.distance(COORDINATES_PARIS[0],
                                        COORDINATES_PARIS[1],
                                        COORDINATES_NEW_YORK[0],
                                        COORDINATES_NEW_YORK[1])
        self.assertAlmostEqual(meters / 1000, DISTANCE_KM, places=2)

    def test_get_kilometers(self):
        """Test getting the distance between given coordinates in km."""
        kilometers = location_util.vincenty(COORDINATES_PARIS,
                                            COORDINATES_NEW_YORK)
        self.assertEqual(round(kilometers, 2), DISTANCE_KM)

    def test_get_miles(self):
        """Test getting the distance between given coordinates in miles."""
        miles = location_util.vincenty(COORDINATES_PARIS,
                                       COORDINATES_NEW_YORK,
                                       miles=True)
        self.assertEqual(round(miles, 2), DISTANCE_MILES)
