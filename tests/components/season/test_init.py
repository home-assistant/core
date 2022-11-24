"""Tests for the Season integration."""
from unittest.mock import AsyncMock

from spencerassistant.components.season.const import DOMAIN, TYPE_ASTRONOMICAL
from spencerassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from spencerassistant.config_entries import ConfigEntryState
from spencerassistant.const import CONF_NAME, CONF_TYPE
from spencerassistant.core import spencerAssistant
from spencerassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: spencerAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Season configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_import_config(
    hass: spencerAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test Season being set up from config via import."""
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                CONF_NAME: "My Season",
            }
        },
    )
    await hass.async_block_till_done()

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1

    entry = config_entries[0]
    assert entry.title == "My Season"
    assert entry.unique_id == TYPE_ASTRONOMICAL
    assert entry.data == {CONF_TYPE: TYPE_ASTRONOMICAL}
