"""Tests for the National Grid US integration init."""

from unittest.mock import AsyncMock, patch

from py_nationalgrid.exceptions import CannotConnectError, InvalidAuthError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import make_api_mock

from tests.common import MockConfigEntry

PATCH_CLIENT = (
    "homeassistant.components.national_grid_us.coordinator.NationalGridClient"
)


async def test_setup_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_national_grid_api: AsyncMock,
) -> None:
    """Test successful setup and unload of a config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup with auth error."""
    api = make_api_mock()
    api.get_billing_account = AsyncMock(side_effect=InvalidAuthError("Bad creds"))

    with patch(PATCH_CLIENT, return_value=api):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_connect_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup with connection error results in retry."""
    api = make_api_mock()
    api.get_billing_account = AsyncMock(side_effect=CannotConnectError("Timeout"))

    with patch(PATCH_CLIENT, return_value=api):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_all_accounts_fail(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that UpdateFailed is raised when all accounts fail."""
    api = make_api_mock()
    api.get_billing_account = AsyncMock(
        side_effect=CannotConnectError("Connection failed")
    )

    with patch(PATCH_CLIENT, return_value=api):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_sensor_missing_usage_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors handle missing usage and cost data gracefully."""
    api = make_api_mock()
    api.get_energy_usages = AsyncMock(return_value=[])
    api.get_energy_usage_costs = AsyncMock(return_value=[])

    with patch(PATCH_CLIENT, return_value=api):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("sensor.electric_meter_last_billing_usage")
    assert state is not None
    assert state.state == "unknown"

    state = hass.states.get("sensor.electric_meter_last_billing_cost")
    assert state is not None
    assert state.state == "unknown"
