"""Define fixtures for PurpleAir tests."""

from unittest.mock import AsyncMock, Mock, patch

from aiopurpleair.endpoints.sensors import NearbySensorResult
from aiopurpleair.models.sensors import GetSensorsResponse
import pytest

from homeassistant.components.purpleair import DOMAIN

from tests.common import MockConfigEntry, load_fixture

TEST_API_KEY = "abcde12345"
TEST_SENSOR_INDEX1 = 123456
TEST_SENSOR_INDEX2 = 567890


@pytest.fixture(name="api")
def api_fixture(get_sensors_response):
    """Define a fixture to return a mocked aiopurple API object."""
    return Mock(
        async_check_api_key=AsyncMock(),
        get_map_url=Mock(return_value="http://example.com"),
        sensors=Mock(
            async_get_nearby_sensors=AsyncMock(
                return_value=[
                    NearbySensorResult(sensor=sensor, distance=1.0)
                    for sensor in get_sensors_response.data.values()
                ]
            ),
            async_get_sensors=AsyncMock(return_value=get_sensors_response),
        ),
    )


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config_entry_data, config_entry_options):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="abcde",
        unique_id=TEST_API_KEY,
        data=config_entry_data,
        options=config_entry_options,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config_entry_data")
def config_entry_data_fixture():
    """Define a config entry data fixture."""
    return {
        "api_key": TEST_API_KEY,
    }


@pytest.fixture(name="config_entry_options")
def config_entry_options_fixture():
    """Define a config entry options fixture."""
    return {
        "sensor_indices": [TEST_SENSOR_INDEX1],
    }


@pytest.fixture(name="get_sensors_response", scope="package")
def get_sensors_response_fixture():
    """Define a fixture to mock an aiopurpleair GetSensorsResponse object."""
    return GetSensorsResponse.parse_raw(
        load_fixture("get_sensors_response.json", "purpleair")
    )


@pytest.fixture(name="mock_aiopurpleair")
async def mock_aiopurpleair_fixture(api):
    """Define a fixture to patch aiopurpleair."""
    with (
        patch("homeassistant.components.purpleair.config_flow.API", return_value=api),
        patch("homeassistant.components.purpleair.coordinator.API", return_value=api),
    ):
        yield api


@pytest.fixture(name="setup_config_entry")
async def setup_config_entry_fixture(hass, config_entry, mock_aiopurpleair):
    """Define a fixture to set up purpleair."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
