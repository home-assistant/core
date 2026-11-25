"""Common fixtures for the Tile BLE tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from tile_ble import TileCloudTile

from homeassistant.components.tile_ble.const import CONF_AUTH_KEY, DOMAIN

from . import AUTH_KEY, KEYS_TILE_ID, OTHER_AUTH_KEY, TILE_ADDRESS, WALLET_TILE_ID


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.tile_ble.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Tile BLE config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Tile",
        unique_id=TILE_ADDRESS,
        data={CONF_AUTH_KEY: AUTH_KEY},
    )


@pytest.fixture
def mock_get_tiles() -> Generator[AsyncMock]:
    """Mock getting the Tiles of the account from the Tile cloud."""
    with patch(
        "homeassistant.components.tile_ble.config_flow.async_get_tiles",
        return_value=[
            TileCloudTile(WALLET_TILE_ID, "Wallet", AUTH_KEY),
            TileCloudTile(KEYS_TILE_ID, "Keys", OTHER_AUTH_KEY),
            TileCloudTile("phone", "Phone", None),
        ],
    ) as mock_get_tiles:
        yield mock_get_tiles


@pytest.fixture
def mock_tile_ble_device() -> Generator[MagicMock]:
    """Mock talking to a Tile over Bluetooth."""
    with (
        patch(
            "homeassistant.components.tile_ble.config_flow.TileBleDevice",
            autospec=True,
        ) as mock_device,
        patch("homeassistant.components.tile_ble.button.TileBleDevice", mock_device),
    ):
        yield mock_device


@pytest.fixture
def mock_read_tile_id() -> Generator[AsyncMock]:
    """Mock reading the Tile ID of a Tile over Bluetooth."""
    with patch(
        "homeassistant.components.tile_ble.config_flow.async_read_tile_id",
        return_value=KEYS_TILE_ID,
    ) as mock_read:
        yield mock_read
