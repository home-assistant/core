"""Define fixtures for PurpleAir tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aiopurpleair.endpoints.sensors import NearbySensorResult
from aiopurpleair.models.sensors import GetSensorsResponse
import pytest

from homeassistant.components.purpleair.const import (
    CONF_SENSOR_INDEX,
    CONF_SENSOR_LIST,
    CONF_SENSOR_READ_KEY,
    DOMAIN,
    SCHEMA_VERSION,
    TITLE,
)
from homeassistant.const import CONF_API_KEY, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant

from .const import TEST_API_KEY, TEST_SENSOR_INDEX1

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="api")
def api_fixture(get_sensors_response: GetSensorsResponse) -> Mock:
    """Define a fixture to return a mocked aiopurpleair API object."""
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
def config_entry_fixture(
    hass: HomeAssistant,
    config_entry_data: dict[str, Any],
    config_entry_options: dict[str, Any],
) -> MockConfigEntry:
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_API_KEY,
        data=config_entry_data,
        options=config_entry_options,
        version=SCHEMA_VERSION,
        title=TITLE,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config_entry_data")
def config_entry_data_fixture() -> dict[str, Any]:
    """Define a config entry data fixture."""
    return {
        CONF_API_KEY: TEST_API_KEY,
    }


@pytest.fixture(name="config_entry_options")
def config_entry_options_fixture() -> dict[str, Any]:
    """Define a config entry options fixture."""
    return {
        CONF_SENSOR_LIST: [
            {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1, CONF_SENSOR_READ_KEY: None},
        ],
        CONF_SHOW_ON_MAP: False,
    }


@pytest.fixture(name="get_sensors_response", scope="package")
def get_sensors_response_fixture() -> GetSensorsResponse:
    """Define a fixture to mock an aiopurpleair GetSensorsResponse object."""
    return GetSensorsResponse.model_validate_json(
        load_fixture("get_sensors_response.json", "purpleair")
    )


@pytest.fixture(name="mock_aiopurpleair")
def mock_aiopurpleair_fixture(api: Mock) -> Generator[Mock]:
    """Define a fixture to patch aiopurpleair."""
    with (
        patch("homeassistant.components.purpleair.coordinator.API", return_value=api),
    ):
        yield api


@pytest.fixture(name="setup_config_entry")
async def setup_config_entry_fixture(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_aiopurpleair: Mock
) -> None:
    """Define a fixture to set up purpleair."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
