"""Test init for Snoo."""

from unittest.mock import AsyncMock, MagicMock

from python_snoo.exceptions import SnooAuthException, SnooDeviceError

from homeassistant.components.snoo.coordinator import SnooBabyCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import async_init_integration


async def test_async_setup_entry(hass: HomeAssistant, bypass_api: AsyncMock) -> None:
    """Test a successful setup entry."""
    entry = await async_init_integration(hass)
    # 2 device sensors + 3 baby sensors = 5 total
    assert len(hass.states.async_all("sensor")) == 5
    # 2 device binary sensors + 4 baby binary sensors = 6 total
    assert len(hass.states.async_all("binary_sensor")) == 6
    assert entry.state == ConfigEntryState.LOADED

    # Verify services are registered
    assert hass.services.has_service("snoo", "log_diaper_change")


async def test_baby_coordinator_update_data(hass: HomeAssistant) -> None:
    """Test baby coordinator data update."""
    mock_entry = MagicMock()
    mock_snoo_unique_id = "test-snoo-123"
    mock_baby = MagicMock()
    mock_baby_data = MagicMock()
    mock_baby_data.babyName = "Test Baby"

    coordinator = SnooBabyCoordinator(
        hass, mock_entry, mock_snoo_unique_id, mock_baby, mock_baby_data
    )

    # Mock updated baby status data
    mock_updated_status = MagicMock()
    mock_baby.get_status = AsyncMock(return_value=mock_updated_status)

    # Test data update
    await coordinator._async_update_data()

    # Verify the baby status was fetched
    mock_baby.get_status.assert_called_once()


async def test_cannot_auth(hass: HomeAssistant, bypass_api: AsyncMock) -> None:
    """Test that we are put into retry when we fail to auth."""
    bypass_api.authorize.side_effect = SnooAuthException
    entry = await async_init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_failed_devices(hass: HomeAssistant, bypass_api: AsyncMock) -> None:
    """Test that we are put into retry when we fail to get devices."""
    bypass_api.get_devices.side_effect = SnooDeviceError
    entry = await async_init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
