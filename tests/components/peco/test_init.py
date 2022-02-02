"""Test the PECO Outage Counter init file."""
from aiohttp import ClientSession
from peco import PecoOutageApi
from pytest import raises

from homeassistant.components.peco import InvalidCountyError, async_setup_entry
from homeassistant.components.peco.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_ENTRY_DATA = {"county": "TOTAL"}
INVALID_COUNTY_DATA = {"county": "INVALID_COUNTY_THAT_SHOULD_NOT_EXIST", "test": True}


async def test_invalid_county(hass: HomeAssistant) -> None:
    """Test the invalid county error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=INVALID_COUNTY_DATA)
    config_entry.add_to_hass(hass)

    with raises(InvalidCountyError):
        await async_setup_entry(
            hass, config_entry
        )  # This is the one that actually raises the error
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test the unload entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert hass.data[DOMAIN]

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    assert entries[0].state == ConfigEntryState.NOT_LOADED


async def test_data(hass: HomeAssistant) -> None:
    """Test the data."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert hass.data[DOMAIN]
    assert isinstance(hass.data[DOMAIN][config_entry.entry_id]["api"], PecoOutageApi)
    assert isinstance(
        hass.data[DOMAIN][config_entry.entry_id]["websession"], ClientSession
    )
