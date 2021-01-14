"""Tests for the kraken integration."""
from unittest.mock import patch

from homeassistant.components import kraken
from homeassistant.components.kraken.const import DOMAIN

from .const import TICKER_INFORMATION_RESPONSE, TRADEABLE_ASSET_PAIR_RESPONSE

from tests.common import MockConfigEntry


async def test_unload_entry(hass):
    """Test unload for Kraken."""
    with patch(
        "pykrakenapi.KrakenAPI.get_tradable_asset_pairs",
        return_value=TRADEABLE_ASSET_PAIR_RESPONSE,
    ), patch(
        "pykrakenapi.KrakenAPI.get_ticker_information",
        return_value=TICKER_INFORMATION_RESPONSE,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert await kraken.async_unload_entry(hass, entry)
        assert DOMAIN not in hass.data
