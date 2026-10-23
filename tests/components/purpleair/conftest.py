"""Define fixtures for PurpleAir tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from aiopurpleair.endpoints.sensors import NearbySensorResult
from aiopurpleair.models.sensors import GetSensorsResponse
import pytest

from homeassistant.components.purpleair.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

TEST_API_KEY = "abcde12345"
TEST_SENSOR_INDEX1 = 123456
TEST_SENSOR_INDEX2 = 567890


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
    """Define a config entry fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="abcde",
        unique_id=TEST_API_KEY,
        data={
            CONF_API_KEY: TEST_API_KEY,
        },
        options={
            "sensor_indices": [TEST_SENSOR_INDEX1],
        },
    )


@pytest.fixture(name="mock_aiopurpleair")
def mock_aiopurpleair_fixture() -> Generator[AsyncMock]:
    """Define a fixture to patch aiopurpleair."""
    get_sensors_response = GetSensorsResponse.model_validate_json(
        load_fixture("get_sensors_response.json", "purpleair")
    )

    with (
        patch(
            "homeassistant.components.purpleair.config_flow.API", autospec=True
        ) as mock_client,
        patch("homeassistant.components.purpleair.coordinator.API", new=mock_client),
    ):
        client = mock_client.return_value
        client.get_map_url.return_value = "http://example.com"
        client.sensors = Mock()

        client.sensors.async_get_sensors = AsyncMock()
        client.sensors.async_get_sensors.return_value = get_sensors_response

        client.sensors.async_get_nearby_sensors = AsyncMock()
        client.sensors.async_get_nearby_sensors.return_value = [
            NearbySensorResult(sensor=sensor, distance=1.0)
            for sensor in get_sensors_response.data.values()
        ]
        yield client


@pytest.fixture(name="setup_config_entry")
async def setup_config_entry_fixture(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_aiopurpleair: AsyncMock
) -> None:
    """Define a fixture to set up purpleair."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
