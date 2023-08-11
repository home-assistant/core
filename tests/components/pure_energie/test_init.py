"""Tests for the Pure Energie integration."""
from unittest.mock import AsyncMock, MagicMock, patch

from gridnet import GridNetConnectionError
import pytest

from homeassistant.components.pure_energie.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "mock_pure_energie", ["pure_energie/device.json"], indirect=True
)
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pure_energie: AsyncMock,
) -> None:
    """Test the Pure Energie configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.unique_id == "unique_thingy"
    assert len(mock_pure_energie.mock_calls) == 3

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@patch(
    "homeassistant.components.pure_energie.GridNet._request",
    side_effect=GridNetConnectionError,
)
async def test_config_entry_not_ready(
    mock_request: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Pure Energie configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
