"""Test the APSystem setup."""

import datetime
from unittest.mock import AsyncMock

from APsystemsEZ1 import InverterReturnedError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.apsystems.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

SCAN_INTERVAL = datetime.timedelta(seconds=12)


@pytest.mark.usefixtures("mock_apsystems")
async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_failed(
    hass: HomeAssistant,
    mock_apsystems: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test update failed."""
    mock_apsystems.get_device_info.side_effect = TimeoutError
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_update(
    hass: HomeAssistant,
    mock_apsystems: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update data with an inverter error and recover."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert "Inverter returned an error" not in caplog.text
    mock_apsystems.get_output_data.side_effect = InverterReturnedError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert "Error fetching APSystems Data data:" in caplog.text
    caplog.clear()
    mock_apsystems.get_output_data.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert "Fetching APSystems Data data recovered" in caplog.text
