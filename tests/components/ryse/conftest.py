"""Fixtures for the RYSE integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.ryse.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Device",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={},
    )


@pytest.fixture
def mock_device() -> MagicMock:
    """Return a mocked RyseBLEDevice."""
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.update_callback = None
    device.client = None
    device.is_valid_position.return_value = True
    device.get_real_position.side_effect = lambda x: 100 - x
    device.is_closed.side_effect = lambda x: x == 100
    device.pair = AsyncMock(return_value=True)
    device.send_open = AsyncMock()
    device.send_close = AsyncMock()
    device.send_set_position = AsyncMock()
    device.send_get_position = AsyncMock()
    return device


@pytest.fixture(autouse=True)
def mock_ryse_ble_device(mock_device: MagicMock) -> Generator[MagicMock]:
    """Patch RyseBLEDevice so tests never touch real BLE hardware."""
    with patch(
        "homeassistant.components.ryse.RyseBLEDevice",
        return_value=mock_device,
    ):
        yield mock_device


@pytest.fixture
def mock_ble_device_from_address() -> Generator[MagicMock]:
    """Patch the bluetooth lookup so the device is always discoverable."""
    with patch(
        "homeassistant.components.ryse.async_ble_device_from_address",
        return_value=MagicMock(),
    ) as mock_from_address:
        yield mock_from_address


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_ble_device_from_address: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the RYSE integration and return its config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
