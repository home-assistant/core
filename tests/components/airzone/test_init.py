"""Define tests for the Airzone init."""

from homeassistant.components.airzone.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState

from .util import CONFIG, airzone_requests_mock

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import mock_aiohttp_client


async def test_unload_entry(hass):
    """Test unload."""

    with mock_aiohttp_client() as _m:
        airzone_requests_mock(_m)

        config_entry = MockConfigEntry(
            domain=DOMAIN, unique_id="airzone_unique_id", data=CONFIG
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED
