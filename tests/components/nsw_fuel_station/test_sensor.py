"""The tests for the NSW Fuel Station sensor platform."""
from unittest.mock import patch

from nsw_fuel import FuelCheckError

from homeassistant.components import sensor
from homeassistant.components.nsw_fuel_station import DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component

VALID_CONFIG = {
    "platform": "nsw_fuel_station",
    "station_id": 350,
    "fuel_types": ["E10", "P95"],
}

VALID_CONFIG_EXPECTED_ENTITY_IDS = ["my_fake_station_p95", "my_fake_station_e10"]


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


class MockGetFuelPricesResponse:
    """Mock GetFuelPricesResponse implementation."""

    def __init__(self, prices, stations):
        """Initialize a mock GetFuelPricesResponse instance."""
        self.prices = prices
        self.stations = stations


MOCK_FUEL_PRICES_RESPONSE = MockGetFuelPricesResponse(
    prices=[
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
    ],
    stations=[MockStation(code=350, name="My Fake Station")],
)


@patch(
    "homeassistant.components.nsw_fuel_station.FuelCheckClient.get_fuel_prices",
    return_value=MOCK_FUEL_PRICES_RESPONSE,
)
async def test_setup(get_fuel_prices, hass):
    """Test the setup with custom settings."""
    with assert_setup_component(1, sensor.DOMAIN):
        assert await async_setup_component(
            hass, sensor.DOMAIN, {"sensor": VALID_CONFIG}
        )
        await hass.async_block_till_done()

    for entity_id in VALID_CONFIG_EXPECTED_ENTITY_IDS:
        state = hass.states.get(f"sensor.{entity_id}")
        assert state is not None


def raise_fuel_check_error():
    """Raise fuel check error for testing error cases."""
    raise FuelCheckError()


@patch(
    "homeassistant.components.nsw_fuel_station.FuelCheckClient.get_fuel_prices",
    side_effect=raise_fuel_check_error,
)
async def test_setup_error(get_fuel_prices, hass):
    """Test the setup with client throwing error."""
    with assert_setup_component(1, sensor.DOMAIN):
        assert await async_setup_component(
            hass, sensor.DOMAIN, {"sensor": VALID_CONFIG}
        )
        await hass.async_block_till_done()

    for entity_id in VALID_CONFIG_EXPECTED_ENTITY_IDS:
        state = hass.states.get(f"sensor.{entity_id}")
        assert state is None


@patch(
    "homeassistant.components.nsw_fuel_station.FuelCheckClient.get_fuel_prices",
    return_value=MOCK_FUEL_PRICES_RESPONSE,
)
async def test_setup_error_no_station(get_fuel_prices, hass):
    """Test the setup with specified station not existing."""
    with assert_setup_component(2, sensor.DOMAIN):
        assert await async_setup_component(
            hass,
            sensor.DOMAIN,
            {
                "sensor": [
                    {
                        "platform": "nsw_fuel_station",
                        "station_id": 350,
                        "fuel_types": ["E10"],
                    },
                    {
                        "platform": "nsw_fuel_station",
                        "station_id": 351,
                        "fuel_types": ["P95"],
                    },
                ]
            },
        )
        await hass.async_block_till_done()

    assert hass.states.get("sensor.my_fake_station_e10") is not None
    assert hass.states.get("sensor.my_fake_station_p95") is None


@patch(
    "homeassistant.components.nsw_fuel_station.FuelCheckClient.get_fuel_prices",
    return_value=MOCK_FUEL_PRICES_RESPONSE,
)
async def test_sensor_values(get_fuel_prices, hass):
    """Test retrieval of sensor values."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, sensor.DOMAIN, {"sensor": VALID_CONFIG})
    await hass.async_block_till_done()

    assert hass.states.get("sensor.my_fake_station_e10").state == "140.0"
    assert hass.states.get("sensor.my_fake_station_p95").state == "150.0"
