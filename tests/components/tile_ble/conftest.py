"""Common fixtures for the Tile BLE tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.tile_ble.const import DOMAIN

from . import TILE_ADDRESS

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.tile_ble.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Tile BLE config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Tile",
        unique_id=TILE_ADDRESS,
        data={},
    )
