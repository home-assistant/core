"""Define test fixtures for Tile."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from pytile.api import API
from pytile.tile import Tile

from homeassistant.components.tile.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import TEST_PASSWORD, TEST_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def tile() -> AsyncMock:
    """Define a Tile object."""
    mock = AsyncMock(spec=Tile)
    mock.uuid = "19264d2dffdbca32"
    mock.name = "Wallet"
    mock.dead = False
    mock.latitude = 1
    mock.longitude = 1
    mock.altitude = 0
    mock.lost = False
    mock.last_timestamp = datetime(2020, 8, 12, 17, 55, 26)
    mock.lost_timestamp = datetime(1969, 12, 31, 19, 0, 0)
    mock.ring_state = "STOPPED"
    mock.voip_state = "OFFLINE"
    mock.hardware_version = "02.09"
    mock.firmware_version = "01.12.14.0"
    mock.as_dict.return_value = {
        "accuracy": 13.496111,
        "altitude": 0,
        "archetype": "WALLET",
        "dead": False,
        "firmware_version": "01.12.14.0",
        "hardware_version": "02.09",
        "kind": "TILE",
        "last_timestamp": datetime(2020, 8, 12, 17, 55, 26),
        "latitude": 0,
        "longitude": 0,
        "lost": False,
        "lost_timestamp": datetime(1969, 12, 31, 19, 0, 0),
        "name": "Wallet",
        "ring_state": "STOPPED",
        "uuid": "19264d2dffdbca32",
        "visible": True,
        "voip_state": "OFFLINE",
    }
    return mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Define a config entry fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USERNAME,
        data={CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
    )


@pytest.fixture
def mock_pytile(tile: AsyncMock) -> Generator[None]:
    """Define a fixture to patch pytile."""
    client = AsyncMock(spec=API)
    client.async_get_tiles = AsyncMock(return_value={"19264d2dffdbca32": tile})
    with (
        patch(
            "homeassistant.components.tile.config_flow.async_login", return_value=client
        ),
        patch("homeassistant.components.tile.async_login", return_value=client),
    ):
        yield


@pytest.fixture
def mock_setup_entry():
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.tile.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
