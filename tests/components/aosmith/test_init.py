"""Tests for the initialization of the A. O. Smith integration."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from py_aosmith import AOSmithInvalidCredentialsException, AOSmithUnknownException
import pytest

from homeassistant.components.aosmith.const import (
    DOMAIN,
    FAST_INTERVAL,
    REGULAR_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_config_entry_setup(init_integration: MockConfigEntry) -> None:
    """Test setup of the config entry."""
    mock_config_entry = init_integration

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the config entry not ready."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_devices",
        side_effect=AOSmithUnknownException("Unknown error"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_auth_failure(
    hass: HomeAssistant, mock_client: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test auth failure during data update."""
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    mock_client.get_devices.side_effect = AOSmithInvalidCredentialsException(
        "Authentication error"
    )
    async_fire_time_changed(hass, dt_util.utcnow() + REGULAR_INTERVAL)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "user"


@pytest.mark.parametrize(
    ("get_devices_fixture", "time_to_wait", "expected_call_count"),
    [
        ("get_devices", REGULAR_INTERVAL, 1),
        ("get_devices", FAST_INTERVAL, 0),
        ("get_devices_mode_pending", FAST_INTERVAL, 1),
        ("get_devices_setpoint_pending", FAST_INTERVAL, 1),
    ],
)
async def test_update(
    hass: HomeAssistant,
    mock_client: MagicMock,
    init_integration: MockConfigEntry,
    time_to_wait: timedelta,
    expected_call_count: int,
) -> None:
    """Test data update with differing intervals depending on device status."""
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert mock_client.get_devices.call_count == 1

    async_fire_time_changed(hass, dt_util.utcnow() + time_to_wait)
    await hass.async_block_till_done()

    assert mock_client.get_devices.call_count == 1 + expected_call_count
