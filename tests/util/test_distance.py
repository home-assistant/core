"""Test homeasssitant distance utility functions."""

import unittest
import homeassistant.util.distance as distance_util


class TestDistanceUtil(unittest.TestCase):
    """Test the distance utility functions."""

    def test_kilometers_to_miles(self):
        """Test conversion from kilometers to miles."""
        self.assertEqual(distance_util.kilometers_to_miles(0), 0)
        self.assertEqual(distance_util.kilometers_to_miles(1), 0.621371)
        self.assertEqual(distance_util.kilometers_to_miles(0.5), 0.3106855)
        self.assertEqual(distance_util.kilometers_to_miles(-1), -0.621371)

        exceptionThrown = False
        try:
            distance_util.kilometers_to_miles('a')
        except TypeError:
            exceptionThrown = True

        self.assertTrue(exceptionThrown)

    def test_miles_to_kilometer(self):
        """Test conversion from miles to kilometers."""
        self.assertEqual(distance_util.miles_to_kilometers(0), 0)
        self.assertEqual(distance_util.miles_to_kilometers(1), 1.60934)
        self.assertEqual(distance_util.miles_to_kilometers(0.5), 0.80467)
        self.assertEqual(distance_util.miles_to_kilometers(-1), -1.60934)

        exceptionThrown = False
        try:
            distance_util.miles_to_kilometers('a')
        except TypeError:
            exceptionThrown = True

        self.assertTrue(exceptionThrown)

    def test_kilometers_to_meters(self):
        """Test conversion from kilometers to meters."""
        self.assertEqual(distance_util.kilometers_to_meters(0), 0)
        self.assertEqual(distance_util.kilometers_to_meters(1), 1000)
        self.assertEqual(distance_util.kilometers_to_meters(0.5), 500)
        self.assertEqual(distance_util.kilometers_to_meters(-1), -1000)

        exceptionThrown = False
        try:
            distance_util.kilometers_to_meters('a')
        except TypeError:
            exceptionThrown = True

        self.assertTrue(exceptionThrown)

    def test_meters_to_kilometers(self):
        """Test conversion from meters to kilometers."""
        self.assertEqual(distance_util.meters_to_kilometers(0), 0)
        self.assertEqual(distance_util.meters_to_kilometers(1), 0.001)
        self.assertEqual(distance_util.meters_to_kilometers(500), 0.5)
        self.assertEqual(distance_util.meters_to_kilometers(-1), -0.001)

        exceptionThrown = False
        try:
            distance_util.meters_to_kilometers('a')
        except TypeError:
            exceptionThrown = True

        self.assertTrue(exceptionThrown)

    def test_meters_to_feet(self):
        """Test conversion from meters to feet."""
        self.assertEqual(distance_util.meters_to_feet(0), 0)
        self.assertEqual(distance_util.meters_to_feet(1), 3.28084)
        self.assertEqual(distance_util.meters_to_feet(500), 1640.42)
        self.assertEqual(distance_util.meters_to_feet(-1), -3.28084)

        exceptionThrown = False
        try:
            distance_util.meters_to_feet('a')
        except TypeError:
            exceptionThrown = True

        self.assertTrue(exceptionThrown)

    def test_feet_to_meters(self):
        """Test conversion from feet to meters."""
        self.assertEqual(distance_util.feet_to_meters(0), 0)
        self.assertEqual(distance_util.feet_to_meters(1), 0.3048)
        self.assertEqual(distance_util.feet_to_meters(500), 152.4)
        self.assertEqual(distance_util.feet_to_meters(-1), -0.3048)

        exceptionThrown = False
        try:
            distance_util.feet_to_meters('a')
        except TypeError:
            exceptionThrown = True

        self.assertTrue(exceptionThrown)

    def test_feet_to_miles(self):
        """Test conversion from feet to miles."""
        self.assertEqual(distance_util.feet_to_miles(0), 0)
        self.assertEqual(distance_util.feet_to_miles(1), 0.000189394)
        self.assertEqual(distance_util.feet_to_miles(500), 0.094697)
        self.assertEqual(distance_util.feet_to_miles(-1), -0.000189394)

        exceptionThrown = False
        try:
            distance_util.feet_to_miles('a')
        except TypeError:
            exceptionThrown = True

        self.assertTrue(exceptionThrown)

    def test_miles_to_feet(self):
        """Test conversion from miles to feet."""
        self.assertEqual(distance_util.miles_to_ft(0), 0)
        self.assertEqual(distance_util.miles_to_ft(1), 5280)
        self.assertEqual(distance_util.miles_to_ft(.5), 2640)
        self.assertEqual(distance_util.miles_to_ft(-1), -5280)

        exceptionThrown = False
        try:
            distance_util.miles_to_ft('a')
        except TypeError:
            exceptionThrown = True

        self.assertTrue(exceptionThrown)

    def test_convert_same_unit(self):
        """Test conversion from any unit to same unit."""
        self.assertEqual(5, distance_util.convert(5, 'km', 'km'))
        self.assertEqual(2, distance_util.convert(2, 'm', 'm'))
        self.assertEqual(10, distance_util.convert(10, 'mi', 'mi'))
        self.assertEqual(9, distance_util.convert(9, 'ft', 'ft'))

    def test_convert_invalid_unit(self):
        """Test exception is thrown for invalid units."""
        exceptionThrown = False
        try:
            distance_util.convert(5, 'bob', 'km')
        except ValueError:
            exceptionThrown = True

        self.assertTrue(exceptionThrown)

        exceptionThrown = False
        try:
            distance_util.convert(5, 'km', 'jim')
        except ValueError:
            exceptionThrown = True

        self.assertTrue(exceptionThrown)

    def test_convert_from_miles(self):
        """Test conversion from miles to other units."""
        miles = 5
        self.assertEqual(distance_util.convert(miles, 'mi', 'km'), 8.0467)
        self.assertEqual(distance_util.convert(miles, 'mi', 'm'), 8046.7)
        self.assertEqual(distance_util.convert(miles, 'mi', 'ft'), 26400)

    def test_convert_from_feet(self):
        """Test conversion from feet to other units."""
        feet = 5000
        self.assertEqual(distance_util.convert(feet, 'ft', 'km'), 1.524)
        self.assertEqual(distance_util.convert(feet, 'ft', 'm'), 1524)
        self.assertEqual(distance_util.convert(feet, 'ft', 'mi'), 0.9469700000000001)

    def test_convert_from_kilometers(self):
        """Test conversion from kilometers to other units."""
        km = 5
        self.assertEqual(distance_util.convert(km, 'km', 'ft'), 16404.2)
        self.assertEqual(distance_util.convert(km, 'km', 'm'), 5000)
        self.assertEqual(distance_util.convert(km, 'km', 'mi'), 3.106855)

    def test_convert_from_meters(self):
        """Test conversion from meters to other units."""
        m = 5000
        self.assertEqual(distance_util.convert(m, 'm', 'ft'), 16404.2)
        self.assertEqual(distance_util.convert(m, 'm', 'km'), 5)
        self.assertEqual(distance_util.convert(m, 'm', 'mi'), 3.106855)
