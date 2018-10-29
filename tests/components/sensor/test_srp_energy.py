"""The tests for the Srp Energy Platform."""
import re
import unittest
from unittest.mock import MagicMock, patch
from datetime import timedelta

import requests_mock

import srpenergy

from homeassistant.components.sensor import srp_energy
from homeassistant.setup import setup_component

from tests.common import (load_fixture, get_test_home_assistant,
                          MockDependency)

VALID_CONFIG_MINIMAL = {
    'sensor': {
        'platform': 'srp',
        'username': 'foo',
        'password': 'bar',
        'id': 1234
    }
}

def load_createMock(accountid, username, password):  # pylint: disable=invalid-name
    """Mock srpusage usage."""
    return ''

def load_usageMock(startdate, enddate):  # pylint: disable=invalid-name
    """Mock srpusage usage."""

    usage = [
        ('9/19/2018', '12:00 AM', '2018-09-19T00:00:00-7:00', '1.2', '0.17'),
        ('9/19/2018', '1:00 AM', '2018-09-19T01:00:00-7:00', '2.1', '0.30'),
        ('9/19/2018', '2:00 AM', '2018-09-19T02:00:00-7:00', '1.5', '0.23'),
        ('9/19/2018', '9:00 PM', '2018-09-19T21:00:00-7:00', '1.2', '0.19'),
        ('9/19/2018', '10:00 PM', '2018-09-19T22:00:00-7:00', '1.1', '0.18'),
        ('9/19/2018', '11:00 PM', '2018-09-19T23:00:00-7:00', '0.4', '0.09')
        ]
    return usage

class TestSrpEnergySetup(unittest.TestCase):
    """Test the Srp Energy platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.username = 'foo'
        self.password = self.hass.config.username = 'abba'
        self.id = self.hass.config.id = '123'
        self.entities = []

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @MockDependency('srpenergy')
    @patch('srpenergy.load_forecast', new=load_usageMock)
    def test_setup_with_config(self, mock_forecastio):
        """Test the platform setup with configuration."""
        setup_component(self.hass, 'sensor', VALID_CONFIG_MINIMAL)

        state = self.hass.states.get('sensor.dark_sky_summary')
        assert state is not None