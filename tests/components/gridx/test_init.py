"""Tests for the gridX integration setup."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from gridx_connector import (
    GridXAuthenticationError,
    GridXConnectionError,
    GridXResponseError,
)
import pytest

from homeassistant.components.gridx.const import LIVE_UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_connector")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entry loads and unloads."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (GridXAuthenticationError("denied"), ConfigEntryState.SETUP_ERROR),
        (GridXConnectionError("offline"), ConfigEntryState.SETUP_RETRY),
        (GridXResponseError("HTTP 500", 500), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test setup errors map to the right entry state."""
    mock_connector.initialize.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is state


@pytest.mark.parametrize(
    "exception",
    [GridXConnectionError("offline"), GridXResponseError("HTTP 500", 500)],
)
async def test_update_failure_makes_entities_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: AsyncMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test a failed refresh after setup marks entities unavailable."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.home_pv_power").state == "1512"

    mock_connector.get_live_data.side_effect = exception
    freezer.tick(LIVE_UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.home_pv_power").state == STATE_UNAVAILABLE

    mock_connector.get_live_data.side_effect = None
    freezer.tick(LIVE_UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.home_pv_power").state == "1512"


async def test_auth_failure_on_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test rejected credentials after setup mark entities unavailable."""
    await setup_integration(hass, mock_config_entry)

    mock_connector.get_live_data.side_effect = GridXAuthenticationError("denied")
    freezer.tick(LIVE_UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.home_pv_power").state == STATE_UNAVAILABLE
