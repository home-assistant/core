"""Tests for the Hidromotic coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.hidromotic.const import DOMAIN
from homeassistant.components.hidromotic.coordinator import HidromoticCoordinator
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.168.1.100",
        data={"host": "192.168.1.100"},
        title="Test Device",
    )


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock HidromoticClient."""
    client = MagicMock()
    client.connect = AsyncMock(return_value=True)
    client.disconnect = AsyncMock()
    client.refresh = AsyncMock()
    client.set_zone_state = AsyncMock()
    client.register_callback = MagicMock(return_value=lambda: None)
    client.data = {"test": "data"}
    client.get_zones = MagicMock(return_value={0: {"id": 0}})
    client.get_tanks = MagicMock(return_value={0: {"id": 0}})
    client.get_pump = MagicMock(return_value={"estado": 0})
    return client


async def test_coordinator_setup_success(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful coordinator setup."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HidromoticCoordinator(hass, mock_client, mock_config_entry)

    with patch("homeassistant.components.hidromotic.coordinator.asyncio.sleep"):
        result = await coordinator.async_setup()

    assert result is True
    mock_client.connect.assert_called_once()
    mock_client.register_callback.assert_called_once()


async def test_coordinator_setup_failure(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator setup failure when connection fails."""
    mock_config_entry.add_to_hass(hass)
    mock_client.connect = AsyncMock(return_value=False)
    coordinator = HidromoticCoordinator(hass, mock_client, mock_config_entry)

    result = await coordinator.async_setup()

    assert result is False


async def test_coordinator_shutdown(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator shutdown."""
    mock_config_entry.add_to_hass(hass)
    unregister = MagicMock()
    mock_client.register_callback = MagicMock(return_value=unregister)
    coordinator = HidromoticCoordinator(hass, mock_client, mock_config_entry)

    with patch("homeassistant.components.hidromotic.coordinator.asyncio.sleep"):
        await coordinator.async_setup()

    await coordinator.async_shutdown()

    unregister.assert_called_once()
    mock_client.disconnect.assert_called_once()


async def test_coordinator_set_zone_state(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting zone state through coordinator."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HidromoticCoordinator(hass, mock_client, mock_config_entry)

    await coordinator.async_set_zone_state(0, True)

    mock_client.set_zone_state.assert_called_once_with(0, True)


async def test_coordinator_refresh_data(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test refreshing data through coordinator."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HidromoticCoordinator(hass, mock_client, mock_config_entry)

    await coordinator.async_refresh_data()

    mock_client.refresh.assert_called_once()


async def test_coordinator_get_zones(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test getting zones through coordinator."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HidromoticCoordinator(hass, mock_client, mock_config_entry)

    zones = coordinator.get_zones()

    mock_client.get_zones.assert_called_once()
    assert 0 in zones


async def test_coordinator_get_tanks(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test getting tanks through coordinator."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HidromoticCoordinator(hass, mock_client, mock_config_entry)

    tanks = coordinator.get_tanks()

    mock_client.get_tanks.assert_called_once()
    assert 0 in tanks


async def test_coordinator_get_pump(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test getting pump status through coordinator."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HidromoticCoordinator(hass, mock_client, mock_config_entry)

    pump = coordinator.get_pump()

    mock_client.get_pump.assert_called_once()
    assert pump["estado"] == 0


async def test_coordinator_data_update_callback(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that coordinator updates data when callback is called."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HidromoticCoordinator(hass, mock_client, mock_config_entry)

    # Capture the callback
    callback = None

    def capture_callback(cb):
        nonlocal callback
        callback = cb
        return lambda: None

    mock_client.register_callback = MagicMock(side_effect=capture_callback)

    with patch("homeassistant.components.hidromotic.coordinator.asyncio.sleep"):
        await coordinator.async_setup()

    # Simulate data update
    new_data = {"updated": True}
    callback(new_data)

    assert coordinator.data == new_data
