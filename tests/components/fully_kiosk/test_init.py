"""Tests for the Fully Kiosk Browser integration."""
import asyncio
from unittest.mock import MagicMock

from fullykiosk import FullyKioskError
import pytest

from homeassistant.components.fully_kiosk.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fully_kiosk: MagicMock,
) -> None:
    """Test the Fully Kiosk Browser configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_fully_kiosk.getDeviceInfo.mock_calls) == 1
    assert len(mock_fully_kiosk.getSettings.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "side_effect",
    [FullyKioskError("error", "status"), asyncio.TimeoutError],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fully_kiosk: MagicMock,
    side_effect: Exception,
) -> None:
    """Test the Fully Kiosk Browser configuration entry not ready."""
    mock_fully_kiosk.getDeviceInfo.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
