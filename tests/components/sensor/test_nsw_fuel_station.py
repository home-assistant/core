"""The tests for the NSW Fuel Station sensor platform."""
import unittest
from unittest.mock import patch

from homeassistant.components import sensor
from homeassistant.setup import setup_component
from tests.common import (
    get_test_home_assistant, assert_setup_component, MockDependency)

VALID_CONFIG = {
    'platform': 'nsw_fuel_station',
    'station_name': 'My Fake Station',
    'station_id': 350,
    'fuel_types': ['E10', 'P95'],
}


class MockPrice():
    """Mock Price implementation."""

    def __init__(self, price, fuel_type, last_updated,
                 price_unit, station_code):
        """Initialize a mock price instance."""
        self.price = price
        self.fuel_type = fuel_type
        self.last_updated = last_updated
        self.price_unit = price_unit
        self.station_code = station_code


class FuelCheckClientMock():
    """Mock FuelCheckClient implementation."""

    def get_fuel_prices_for_station(self, station):
        """Return a fake fuel prices response."""
        return [
            MockPrice(
                price=150.0,
                fuel_type='P95',
                last_updated=None,
                price_unit=None,
                station_code=350
            ),
            MockPrice(
                price=140.0,
                fuel_type='E10',
                last_updated=None,
                price_unit=None,
                station_code=350
            )
        ]


class TestNSWFuelStation(unittest.TestCase):
    """Test the NSW Fuel Station sensor platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @MockDependency('nsw_fuel')
    @patch('nsw_fuel.FuelCheckClient', new=FuelCheckClientMock)
    def test_setup(self, mock_nsw_fuel):
        """Test the setup with custom settings."""
        with assert_setup_component(1, sensor.DOMAIN):
            self.assertTrue(setup_component(self.hass, sensor.DOMAIN, {
                'sensor': VALID_CONFIG}))

        fake_entities = [
            'nsw_fuel_station_my_fake_station_p95',
            'nsw_fuel_station_my_fake_station_e10'
        ]

        for entity_id in fake_entities:
            state = self.hass.states.get('sensor.{}'.format(entity_id))
            self.assertIsNotNone(state)

    @MockDependency('nsw_fuel')
    @patch('nsw_fuel.FuelCheckClient', new=FuelCheckClientMock)
    def test_sensor_values(self, mock_nsw_fuel):
        """Test retrieval of sensor values."""
        self.assertTrue(setup_component(
            self.hass, sensor.DOMAIN, {'sensor': VALID_CONFIG}))

        self.assertEqual('140.0', self.hass.states.get(
            'sensor.nsw_fuel_station_my_fake_station_e10').state)
        self.assertEqual('150.0', self.hass.states.get(
            'sensor.nsw_fuel_station_my_fake_station_p95').state)
