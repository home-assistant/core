"""Common fixtures for the Tile BLE tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.tile_ble.const import CONF_AUTH_KEY, DOMAIN

from . import AUTH_KEY, OTHER_AUTH_KEY, TILE_ADDRESS


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


def _mock_tile(uuid: str, name: str, auth_key: str | None) -> MagicMock:
    tile = MagicMock()
    tile.uuid = uuid
    tile.name = name
    tile._tile_data = {"result": {"auth_key": auth_key}}
    return tile


@pytest.fixture
def mock_pytile() -> Generator[AsyncMock]:
    """Mock logging in to the Tile cloud."""
    client = AsyncMock()
    client.async_get_tiles.return_value = {
        "19264d2dffdbca32": _mock_tile("19264d2dffdbca32", "Wallet", AUTH_KEY),
        "5176d2dffdbca32a": _mock_tile("5176d2dffdbca32a", "Keys", OTHER_AUTH_KEY),
        "phone": _mock_tile("phone", "Phone", None),
    }
    with patch(
        "homeassistant.components.tile_ble.config_flow.async_login",
        return_value=client,
    ) as mock_login:
        yield mock_login


@pytest.fixture
def mock_tile_ble_device() -> Generator[MagicMock]:
    """Mock talking to a Tile over Bluetooth."""
    with (
        patch(
            "homeassistant.components.tile_ble.config_flow.TileBleDevice",
            autospec=True,
        ) as mock_device,
        patch(
            "homeassistant.components.tile_ble.button.TileBleDevice", new=mock_device
        ),
    ):
        yield mock_device
