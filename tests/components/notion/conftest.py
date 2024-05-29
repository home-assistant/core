"""Define fixtures for Notion tests."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, Mock, patch

from aionotion.bridge.models import Bridge
from aionotion.listener.models import Listener
from aionotion.sensor.models import Sensor
from aionotion.user.models import UserPreferences
import pytest

from homeassistant.components.notion import CONF_REFRESH_TOKEN, CONF_USER_UUID, DOMAIN
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

TEST_USERNAME = "user@host.com"
TEST_PASSWORD = "password123"
TEST_REFRESH_TOKEN = "abcde12345"
TEST_USER_UUID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.notion.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="client")
def client_fixture(data_bridge, data_listener, data_sensor, data_user_preferences):
    """Define a fixture for an aionotion client."""
    return Mock(
        bridge=Mock(
            async_all=AsyncMock(
                return_value=[
                    Bridge.from_dict(bridge) for bridge in data_bridge["base_stations"]
                ]
            )
        ),
        listener=Mock(
            async_all=AsyncMock(
                return_value=[
                    Listener.from_dict(listener)
                    for listener in data_listener["listeners"]
                ]
            )
        ),
        refresh_token=TEST_REFRESH_TOKEN,
        sensor=Mock(
            async_all=AsyncMock(
                return_value=[
                    Sensor.from_dict(sensor) for sensor in data_sensor["sensors"]
                ]
            )
        ),
        user=Mock(
            async_preferences=AsyncMock(
                return_value=UserPreferences.from_dict(
                    data_user_preferences["user_preferences"]
                )
            )
        ),
        user_uuid=TEST_USER_UUID,
    )


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass: HomeAssistant, config):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=TEST_USERNAME, data=config)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture():
    """Define a config entry data fixture."""
    return {
        CONF_USERNAME: TEST_USERNAME,
        CONF_USER_UUID: TEST_USER_UUID,
        CONF_REFRESH_TOKEN: TEST_REFRESH_TOKEN,
    }


@pytest.fixture(name="data_bridge", scope="package")
def data_bridge_fixture():
    """Define bridge data."""
    return json.loads(load_fixture("bridge_data.json", "notion"))


@pytest.fixture(name="data_listener", scope="package")
def data_listener_fixture():
    """Define listener data."""
    return json.loads(load_fixture("listener_data.json", "notion"))


@pytest.fixture(name="data_sensor", scope="package")
def data_sensor_fixture():
    """Define sensor data."""
    return json.loads(load_fixture("sensor_data.json", "notion"))


@pytest.fixture(name="data_user_preferences", scope="package")
def data_user_preferences_fixture():
    """Define user preferences data."""
    return json.loads(load_fixture("user_preferences_data.json", "notion"))


@pytest.fixture(name="get_client")
def get_client_fixture(client):
    """Define a fixture to mock the client retrieval methods."""
    return AsyncMock(return_value=client)


@pytest.fixture(name="mock_aionotion")
async def mock_aionotion_fixture(client):
    """Define a fixture to patch aionotion."""
    with (
        patch(
            "homeassistant.components.notion.async_get_client_with_credentials",
            AsyncMock(return_value=client),
        ),
        patch(
            "homeassistant.components.notion.async_get_client_with_refresh_token",
            AsyncMock(return_value=client),
        ),
        patch(
            "homeassistant.components.notion.config_flow.async_get_client_with_credentials",
            AsyncMock(return_value=client),
        ),
    ):
        yield


@pytest.fixture(name="setup_config_entry")
async def setup_config_entry_fixture(hass: HomeAssistant, config_entry, mock_aionotion):
    """Define a fixture to set up notion."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
