"""Test the Wolf SmartSet Service coordinator."""

from datetime import timedelta
from unittest.mock import MagicMock

from httpx import RequestError
import pytest
from wolf_comm.models import Device
from wolf_comm.token_auth import InvalidAuth
from wolf_comm.wolf_client import FetchFailed, ParameterReadError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_system_share_id_forwarded_to_state_list(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that system_share_id is passed to fetch_system_state_list for shared systems."""
    mock_wolflink.fetch_system_list.return_value = [
        Device(1234, 5678, "test-device", system_share_id=9999),
    ]

    await setup_integration(hass, mock_config_entry)

    mock_wolflink.fetch_system_state_list.assert_called_with(1234, 5678, 9999)


async def test_update_skipped_when_device_offline(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the update is failed when fetch_system_state_list returns False.

    This also flags parameters for re-fetch on the next successful update.
    """
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_wolflink.fetch_parameters.reset_mock()
    mock_wolflink.fetch_system_state_list.return_value = False

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
    await hass.async_block_till_done()

    # Restore the device and trigger another refresh — parameters must be
    # re-fetched because the previous cycle flagged it.
    mock_wolflink.fetch_system_state_list.return_value = True
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=240))
    await hass.async_block_till_done()

    assert mock_wolflink.fetch_parameters.call_count == 1


@pytest.mark.parametrize(
    "side_effect",
    [
        RequestError("boom"),
        FetchFailed("boom"),
        InvalidAuth,
    ],
)
async def test_update_failure_modes(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test recoverable update errors propagate as UpdateFailed."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_wolflink.fetch_value.side_effect = side_effect
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
    await hass.async_block_till_done()

    coordinator = next(iter(mock_config_entry.runtime_data.values()))
    assert coordinator.last_update_success is False


async def test_parameter_read_error_triggers_refetch(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test ParameterReadError flags parameters for re-fetch on next cycle."""
    await setup_integration(hass, mock_config_entry)

    mock_wolflink.fetch_parameters.reset_mock()
    mock_wolflink.fetch_value.side_effect = ParameterReadError("stale")
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
    await hass.async_block_till_done()

    coordinator = next(iter(mock_config_entry.runtime_data.values()))
    assert coordinator.last_update_success is False

    mock_wolflink.fetch_value.side_effect = None
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=240))
    await hass.async_block_till_done()

    assert mock_wolflink.fetch_parameters.call_count == 1
    assert coordinator.last_update_success is True
