"""Define test fixtures for OpenUV."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.openuv import CONF_FROM_WINDOW, CONF_TO_WINDOW, DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)

from tests.common import MockConfigEntry, load_fixture

TEST_API_KEY = "abcde12345"
TEST_ELEVATION = 0
TEST_LATITUDE = 51.528308
TEST_LONGITUDE = -0.3817765


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.openuv.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="client")
def client_fixture(data_protection_window, data_uv_index):
    """Define a mock Client object."""
    return Mock(
        uv_index=AsyncMock(return_value=data_uv_index),
        uv_protection_window=AsyncMock(return_value=data_protection_window),
    )


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{config[CONF_LATITUDE]}, {config[CONF_LONGITUDE]}",
        data=config,
        options={CONF_FROM_WINDOW: 3.5, CONF_TO_WINDOW: 3.5},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture():
    """Define a config entry data fixture."""
    return {
        CONF_API_KEY: TEST_API_KEY,
        CONF_ELEVATION: TEST_ELEVATION,
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
    }


@pytest.fixture(name="data_protection_window", scope="package")
def data_protection_window_fixture():
    """Define a fixture to return UV protection window data."""
    return json.loads(load_fixture("protection_window_data.json", "openuv"))


@pytest.fixture(name="data_uv_index", scope="package")
def data_uv_index_fixture():
    """Define a fixture to return UV index data."""
    return json.loads(load_fixture("uv_index_data.json", "openuv"))


@pytest.fixture(name="mock_pyopenuv")
async def mock_pyopenuv_fixture(client):
    """Define a fixture to patch pyopenuv."""
    with (
        patch(
            "homeassistant.components.openuv.config_flow.Client", return_value=client
        ),
        patch("homeassistant.components.openuv.Client", return_value=client),
    ):
        yield


@pytest.fixture(name="setup_config_entry")
async def setup_config_entry_fixture(hass, config_entry, mock_pyopenuv):
    """Define a fixture to set up openuv."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
