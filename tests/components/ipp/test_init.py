"""Tests for the IPP integration."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyipp import (
    IPPConnectionError,
    IPPParseError,
    IPPResponseError,
    IPPVersionNotSupportedError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.ipp.const import REQUEST_TIMEOUT
from homeassistant.components.ipp.coordinator import (
    SCAN_INTERVAL,
    IPPDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant


@patch(
    "homeassistant.components.ipp.coordinator.IPP._request",
    side_effect=IPPConnectionError,
)
async def test_config_entry_not_ready(
    mock_request: MagicMock, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the IPP configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_request.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ipp: AsyncMock,
) -> None:
    """Test the IPP configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert isinstance(mock_config_entry.runtime_data, IPPDataUpdateCoordinator)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_request_timeout(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a printer gets time to wake up before we give up on it."""
    coordinator = IPPDataUpdateCoordinator(hass, mock_config_entry)

    assert coordinator.ipp.request_timeout == REQUEST_TIMEOUT


@pytest.mark.parametrize(
    ("exc", "level"),
    [
        (IPPConnectionError, logging.INFO),
        (IPPParseError, logging.ERROR),
        (IPPResponseError, logging.ERROR),
        (IPPVersionNotSupportedError, logging.ERROR),
    ],
)
async def test_update_failure_log_level(
    hass: HomeAssistant,
    exc: type[Exception],
    level: int,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_ipp: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unreachable printer is logged at info level, other errors as an error.

    A printer that cannot be connected to at all (e.g. switched off or in
    standby) is common enough on a home network that it should not be
    logged as an error on every scan interval. A response the printer did
    send but that cannot be parsed or understood is a real error.
    """
    state = hass.states.get("sensor.test_ha_1000_series")
    assert state
    assert state.state == "idle"

    mock_ipp.printer.side_effect = exc
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.LOADED
    state = hass.states.get("sensor.test_ha_1000_series")
    assert state
    assert state.state == STATE_UNAVAILABLE

    assert [
        record.levelno
        for record in caplog.records
        if record.name.startswith("homeassistant.components.ipp")
        and record.levelno > logging.DEBUG
    ] == [level]
