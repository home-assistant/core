"""Tests for Wibeee coordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock
from xml.etree.ElementTree import ParseError as XMLParseError

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.wibeee.coordinator import WibeeeCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator_update_failed(
    hass: HomeAssistant, mock_wibeee_api: AsyncMock
) -> None:
    """Test coordinator update failure."""
    coordinator = WibeeeCoordinator(hass, mock_wibeee_api, config_entry=AsyncMock())
    # Must be an exception that the coordinator catches (TimeoutError, ClientError, etc)
    mock_wibeee_api.async_fetch_sensors_data.side_effect = TimeoutError("Fetch failed")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_xml_parse_error(
    hass: HomeAssistant, mock_wibeee_api: AsyncMock
) -> None:
    """Test coordinator translates XMLParseError into UpdateFailed."""
    coordinator = WibeeeCoordinator(hass, mock_wibeee_api, config_entry=AsyncMock())
    mock_wibeee_api.async_fetch_sensors_data.side_effect = XMLParseError("bad xml")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_no_data(
    hass: HomeAssistant, mock_wibeee_api: AsyncMock
) -> None:
    """Test coordinator handles no data received."""
    coordinator = WibeeeCoordinator(hass, mock_wibeee_api, config_entry=AsyncMock())
    mock_wibeee_api.async_fetch_sensors_data.return_value = None

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_invalid_data(
    hass: HomeAssistant, mock_wibeee_api: AsyncMock
) -> None:
    """Test coordinator handles invalid data format."""
    coordinator = WibeeeCoordinator(hass, mock_wibeee_api, config_entry=AsyncMock())
    mock_wibeee_api.async_fetch_sensors_data.return_value = "invalid"

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_push_update_invalid(
    hass: HomeAssistant, mock_wibeee_api: AsyncMock
) -> None:
    """Test coordinator handles invalid push update data."""
    coordinator = WibeeeCoordinator(hass, mock_wibeee_api, config_entry=AsyncMock())

    # Push non-dict data should be ignored
    coordinator.async_push_update("not_a_dict")  # type: ignore[arg-type]
    assert coordinator.data is None


async def test_coordinator_push_staleness_watchdog(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test push-mode coordinator marks data stale after timeout."""
    coordinator = loaded_entry.runtime_data.coordinator
    assert coordinator.last_update_success is True

    # No further pushes; advance past the staleness window.
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False


async def test_coordinator_push_resets_watchdog(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a fresh push update resets the staleness watchdog."""
    coordinator = loaded_entry.runtime_data.coordinator

    # Almost stale, then a push arrives -> watchdog reset.
    freezer.tick(timedelta(minutes=4))
    coordinator.async_push_update({"fase4": {"vrms": "230.0"}})
    await hass.async_block_till_done()
    assert coordinator.last_update_success is True

    # Advance another 4 minutes (total 8) -> still under the window since reset.
    freezer.tick(timedelta(minutes=4))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert coordinator.last_update_success is True


async def test_coordinator_shutdown_cancels_watchdog(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test unloading a push-mode entry cancels the staleness watchdog."""
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED
