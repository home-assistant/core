"""Tests for the initialization of the A. O. Smith integration."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from py_aosmith import AOSmithUnknownException
import pytest

from homeassistant.components.aosmith.const import (
    DOMAIN,
    FAST_INTERVAL,
    REGULAR_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import build_device_fixture

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_config_entry_setup(init_integration: MockConfigEntry) -> None:
    """Test setup of the config entry."""
    mock_config_entry = init_integration

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_config_entry_not_ready_get_devices_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the config entry not ready when get_devices fails."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_devices",
        side_effect=AOSmithUnknownException("Unknown error"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_not_ready_get_energy_use_data_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the config entry not ready when get_energy_use_data fails."""
    mock_config_entry.add_to_hass(hass)

    get_devices_fixture = [
        build_device_fixture(
            heat_pump=True,
            mode_pending=False,
            setpoint_pending=False,
            has_vacation_mode=True,
        )
    ]

    with patch(
        "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_devices",
        return_value=get_devices_fixture,
    ), patch(
        "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_energy_use_data",
        side_effect=AOSmithUnknownException("Unknown error"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    (
        "get_devices_fixture_mode_pending",
        "get_devices_fixture_setpoint_pending",
        "time_to_wait",
        "expected_call_count",
    ),
    [
        (False, False, REGULAR_INTERVAL, 1),
        (False, False, FAST_INTERVAL, 0),
        (True, False, FAST_INTERVAL, 1),
        (False, True, FAST_INTERVAL, 1),
    ],
)
async def test_update(
    freezer: FrozenDateTimeFactory,
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

    freezer.tick(time_to_wait)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.get_devices.call_count == 1 + expected_call_count
