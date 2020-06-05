"""The tests for the NSW Fuel Station sensor platform."""
import unittest

from homeassistant.components import sensor
from homeassistant.setup import setup_component

from tests.async_mock import patch
from tests.common import assert_setup_component, get_test_home_assistant

VALID_CONFIG = {
    "platform": "nsw_fuel_station",
    "station_id": 350,
    "fuel_types": ["E10", "P95"],
}


class MockPrice:
    """Mock Price implementation."""

    def __init__(self, price, fuel_type, last_updated, price_unit, station_code):
        """Initialize a mock price instance."""
        self.price = price
        self.fuel_type = fuel_type
        self.last_updated = last_updated
        self.price_unit = price_unit
        self.station_code = station_code


class MockStation:
    """Mock Station implementation."""

    def __init__(self, name, code):
        """Initialize a mock Station instance."""
        self.name = name
        self.code = code


class MockGetReferenceDataResponse:
    """Mock GetReferenceDataResponse implementation."""

    def __init__(self, stations):
        """Initialize a mock GetReferenceDataResponse instance."""
        self.stations = stations


class FuelCheckClientMock:
    """Mock FuelCheckClient implementation."""

    def get_fuel_prices_for_station(self, station):
        """Return a fake fuel prices response."""
        return [
            MockPrice(
                price=150.0,
                fuel_type="P95",
                last_updated=None,
                price_unit=None,
                station_code=350,
            ),
            MockPrice(
                price=140.0,
                fuel_type="E10",
                last_updated=None,
                price_unit=None,
                station_code=350,
            ),
        ]

    def get_reference_data(self):
        """Return a fake reference data response."""
        return MockGetReferenceDataResponse(
            stations=[MockStation(code=350, name="My Fake Station")]
        )


class TestNSWFuelStation(unittest.TestCase):
    """Test the NSW Fuel Station sensor platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch(
        "homeassistant.components.nsw_fuel_station.sensor.FuelCheckClient",
        new=FuelCheckClientMock,
    )
    def test_setup(self):
        """Test the setup with custom settings."""
        with assert_setup_component(1, sensor.DOMAIN):
            assert setup_component(self.hass, sensor.DOMAIN, {"sensor": VALID_CONFIG})
            self.hass.block_till_done()

        fake_entities = ["my_fake_station_p95", "my_fake_station_e10"]

        for entity_id in fake_entities:
            state = self.hass.states.get(f"sensor.{entity_id}")
            assert state is not None

    @patch(
        "homeassistant.components.nsw_fuel_station.sensor.FuelCheckClient",
        new=FuelCheckClientMock,
    )
    def test_sensor_values(self):
        """Test retrieval of sensor values."""
        assert setup_component(self.hass, sensor.DOMAIN, {"sensor": VALID_CONFIG})
        self.hass.block_till_done()

        assert "140.0" == self.hass.states.get("sensor.my_fake_station_e10").state
        assert "150.0" == self.hass.states.get("sensor.my_fake_station_p95").state
