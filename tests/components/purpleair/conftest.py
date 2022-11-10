"""Define fixtures for PurpleAir tests."""
from unittest.mock import AsyncMock, patch

from aiopurpleair.models.sensors import GetSensorsResponse
import pytest

from homeassistant.components.purpleair import DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="check_api_key")
def check_api_key_fixture():
    """Define a fixture to mock the method to check an API key's validity."""
    return AsyncMock()


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config_entry_data):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Sensor",
        unique_id="123456",
        data=config_entry_data,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config_entry_data")
def config_entry_data_fixture():
    """Define a config entry data fixture."""
    return {
        "api_key": "abcde12345",
        "latitude": 51.5285582,
        "longitude": -0.2416796,
        "distance": 5,
        "sensor_index": 123456,
    }


@pytest.fixture(name="get_nearby_sensors")
def get_nearby_sensors_fixture(get_sensors_response):
    """Define a mocked API.sensors.async_get_nearby_sensors."""
    return AsyncMock(return_value=list(get_sensors_response.data.values()))


@pytest.fixture(name="get_sensors")
def get_sensors_fixture(get_sensors_response):
    """Define a mocked API.sensors.async_get_sensors."""
    return AsyncMock(return_value=get_sensors_response)


@pytest.fixture(name="get_sensors_response", scope="package")
def get_sensors_response_fixture():
    """Define a fixture to mock an aiopurpleair GetSensorsResponse object."""
    return GetSensorsResponse.parse_raw(
        load_fixture("get_sensors_response.json", "purpleair")
    )


@pytest.fixture(name="setup_purpleair")
async def setup_purpleair_fixture(
    hass, check_api_key, config_entry_data, get_nearby_sensors, get_sensors
):
    """Define a fixture to set up PurpleAir."""
    with patch(
        "homeassistant.components.purpleair.config_flow.API.async_check_api_key",
        check_api_key,
    ), patch(
        "aiopurpleair.endpoints.sensors.SensorsEndpoints.async_get_nearby_sensors",
        get_nearby_sensors,
    ), patch(
        "aiopurpleair.endpoints.sensors.SensorsEndpoints.async_get_sensors",
        get_sensors,
    ), patch(
        "homeassistant.components.purpleair.PLATFORMS", []
    ):
        assert await async_setup_component(hass, DOMAIN, config_entry_data)
        await hass.async_block_till_done()
        yield
