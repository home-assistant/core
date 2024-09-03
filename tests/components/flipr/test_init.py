"""Tests for init methods."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flipr_client: AsyncMock,
) -> None:
    """Test unload entry."""

    mock_flipr_client.search_all_ids.return_value = {
        "flipr": ["myfliprid"],
        "hub": ["hubid"],
    }

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_migrate_entry(
    hass: HomeAssistant,
    mock_config_entry_v1: MockConfigEntry,
    mock_flipr_client: AsyncMock,
) -> None:
    """Test migrate config entry from v1 to v2."""

    await setup_integration(hass, mock_config_entry_v1)
    assert mock_config_entry_v1.state is ConfigEntryState.LOADED
    assert mock_config_entry_v1.version == 2
    assert mock_config_entry_v1.title == "Flipr toto@toto.com"
    assert mock_config_entry_v1.data == {
        CONF_EMAIL: "toto@toto.com",
        CONF_PASSWORD: "myPassword",
    }
