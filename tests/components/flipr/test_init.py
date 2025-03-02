"""Tests for init methods."""

from unittest.mock import AsyncMock

from homeassistant.components.flipr.const import DOMAIN
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


async def test_duplicate_config_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flipr_client: AsyncMock,
) -> None:
    """Test duplicate config entries."""

    mock_config_entry_dup = MockConfigEntry(
        version=2,
        domain=DOMAIN,
        unique_id="toto@toto.com",
        data={
            CONF_EMAIL: "toto@toto.com",
            CONF_PASSWORD: "myPassword",
            "flipr_id": "myflipr_id_dup",
        },
    )

    mock_config_entry.add_to_hass(hass)
    # Initialize the first entry with default mock
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Initialize the second entry with another flipr id
    mock_config_entry_dup.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry_dup.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry_dup.state is ConfigEntryState.SETUP_ERROR


async def test_migrate_entry(
    hass: HomeAssistant,
    mock_flipr_client: AsyncMock,
) -> None:
    """Test migrate config entry from v1 to v2."""

    mock_config_entry_v1 = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="myfliprid",
        unique_id="test_entry_unique_id",
        data={
            CONF_EMAIL: "toto@toto.com",
            CONF_PASSWORD: "myPassword",
            "flipr_id": "myfliprid",
        },
    )

    await setup_integration(hass, mock_config_entry_v1)
    assert mock_config_entry_v1.state is ConfigEntryState.LOADED
    assert mock_config_entry_v1.version == 2
    assert mock_config_entry_v1.unique_id == "toto@toto.com"
    assert mock_config_entry_v1.data == {
        CONF_EMAIL: "toto@toto.com",
        CONF_PASSWORD: "myPassword",
        "flipr_id": "myfliprid",
    }
