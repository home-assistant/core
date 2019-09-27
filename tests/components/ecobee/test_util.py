"""Tests for the ecobee.util module."""
import unittest
import voluptuous as vol
from homeassistant.components.ecobee.util import ecobee_date, ecobee_time


class TestUtil(unittest.TestCase):
    """Tests for the ecobee.util functions."""

    def test_ecobee_date_with_valid_input(self):
        """Test that the date function returns the expected result."""
        test_input = "2019-09-27"

        assert ecobee_date(test_input) == test_input

    def test_ecobee_date_with_invalid_input(self):
        """Test that the date function raises the expected exception."""
        test_input = "20190927"

        with self.assertRaises(vol.Invalid):
            ecobee_date(test_input)

    def test_ecobee_time_with_valid_input(self):
        """Test that the time function returns the expected result."""
        test_input = "20:55:15"

        assert ecobee_time(test_input) == test_input

    def test_ecobee_time_with_invalid_input(self):
        """Test that the time function raises the expected exception."""
        test_input = "20:55"

        with self.assertRaises(vol.Invalid):
            ecobee_time(test_input)
