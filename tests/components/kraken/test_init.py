"""Tests for the kraken integration."""
from unittest.mock import patch

from pykrakenapi.pykrakenapi import CallRateLimitError, KrakenAPIError
import pytest

from homeassistant.components.kraken.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import TICKER_INFORMATION_RESPONSE, TRADEABLE_ASSET_PAIR_RESPONSE

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant) -> None:
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
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert DOMAIN not in hass.data


async def test_unknown_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test unload for Kraken."""
    with patch(
        "pykrakenapi.KrakenAPI.get_tradable_asset_pairs",
        return_value=TRADEABLE_ASSET_PAIR_RESPONSE,
    ), patch(
        "pykrakenapi.KrakenAPI.get_ticker_information",
        side_effect=KrakenAPIError("EQuery: Error"),
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert "Unable to fetch data from Kraken.com:" in caplog.text


async def test_callrate_limit(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test unload for Kraken."""
    with patch(
        "pykrakenapi.KrakenAPI.get_tradable_asset_pairs",
        return_value=TRADEABLE_ASSET_PAIR_RESPONSE,
    ), patch(
        "pykrakenapi.KrakenAPI.get_ticker_information",
        side_effect=CallRateLimitError(),
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert (
            "Exceeded the Kraken.com call rate limit. Increase the update interval to"
            " prevent this error" in caplog.text
        )
