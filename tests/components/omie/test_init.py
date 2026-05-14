"""Test the OMIE - Spain and Portugal electricity prices integration."""

from unittest.mock import MagicMock

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import spot_price_fetcher

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyomie: MagicMock,
) -> None:
    """Test setup and unload of a config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_pyomie.spot_price.call_count == 1

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("hass_madrid")
@pytest.mark.freeze_time("2024-01-15T12:01:00Z")
async def test_coordinator_unavailability_logging(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_pyomie: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator logs unavailability and recovery appropriately."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_pyomie.spot_price.call_count == 1
    assert "ERROR" not in caplog.text

    # Trigger refresh with API failure
    mock_pyomie.spot_price.side_effect = aiohttp.ClientError("Connection timeout")
    freezer.move_to("2024-01-15T12:16:02Z")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_pyomie.spot_price.call_count == 2
    assert "Error requesting omie data" in caplog.text
    assert "Connection timeout" in caplog.text

    # Second failure should not log again
    caplog.clear()
    freezer.move_to("2024-01-15T12:31:02Z")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_pyomie.spot_price.call_count == 3
    assert "Error" not in caplog.text

    # Trigger recovery
    mock_pyomie.spot_price.side_effect = spot_price_fetcher({})
    freezer.move_to("2024-01-15T12:46:02Z")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_pyomie.spot_price.call_count == 4
    assert "Fetching omie data recovered" in caplog.text


@pytest.mark.freeze_time("2025-11-11T10:17:32.153544Z")
async def test_update_interval(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_pyomie: MagicMock,
) -> None:
    """Test that the coordinator schedules updates at the correct 15-minute intervals."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_pyomie.spot_price.reset_mock()

    # The next update should be scheduled for 10:30:01Z (11:30:01 CET, 15-minute boundary + 1 second)
    freezer.move_to("2025-11-11T10:30:00.000000Z")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_pyomie.spot_price.call_count == 0

    freezer.tick(1)  # Move to 10:30:01
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_pyomie.spot_price.call_count == 1
    mock_pyomie.spot_price.reset_mock()

    freezer.tick(14 * 60)  # Move to 10:44:01
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_pyomie.spot_price.call_count == 0

    freezer.tick(60)  # Move to 10:45:01
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_pyomie.spot_price.call_count == 1
