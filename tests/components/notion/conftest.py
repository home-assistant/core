"""Define fixtures for Notion tests."""
from collections.abc import Generator
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.notion import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry, load_fixture

TEST_USERNAME = "user@host.com"
TEST_PASSWORD = "password123"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.notion.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="client")
def client_fixture(data_bridge, data_sensor, data_task):
    """Define a fixture for an aionotion client."""
    return Mock(
        bridge=Mock(async_all=AsyncMock(return_value=data_bridge)),
        sensor=Mock(async_all=AsyncMock(return_value=data_sensor)),
        task=Mock(async_all=AsyncMock(return_value=data_task)),
    )


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=TEST_USERNAME, data=config)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture():
    """Define a config entry data fixture."""
    return {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }


@pytest.fixture(name="data_bridge", scope="package")
def data_bridge_fixture():
    """Define bridge data."""
    return json.loads(load_fixture("bridge_data.json", "notion"))


@pytest.fixture(name="data_sensor", scope="package")
def data_sensor_fixture():
    """Define sensor data."""
    return json.loads(load_fixture("sensor_data.json", "notion"))


@pytest.fixture(name="data_task", scope="package")
def data_task_fixture():
    """Define task data."""
    return json.loads(load_fixture("task_data.json", "notion"))


@pytest.fixture(name="get_client")
def get_client_fixture(client):
    """Define a fixture to mock the async_get_client method."""
    return AsyncMock(return_value=client)


@pytest.fixture(name="mock_aionotion")
async def mock_aionotion_fixture(client):
    """Define a fixture to patch aionotion."""
    with patch(
        "homeassistant.components.notion.async_get_client",
        AsyncMock(return_value=client),
    ), patch(
        "homeassistant.components.notion.config_flow.async_get_client",
        AsyncMock(return_value=client),
    ):
        yield


@pytest.fixture(name="setup_config_entry")
async def setup_config_entry_fixture(hass, config_entry, mock_aionotion):
    """Define a fixture to set up notion."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
