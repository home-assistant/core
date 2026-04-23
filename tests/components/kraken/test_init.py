"""Tests for the kraken integration."""

from unittest.mock import patch

from pykrakenapi.pykrakenapi import CallRateLimitError, KrakenAPIError
import pytest

from homeassistant.components.kraken.const import CONF_TRACKED_ASSET_PAIRS, DOMAIN
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from .const import TICKER_INFORMATION_RESPONSE, TRADEABLE_ASSET_PAIR_RESPONSE

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload for Kraken."""
    with (
        patch(
            "pykrakenapi.KrakenAPI.get_tradable_asset_pairs",
            return_value=TRADEABLE_ASSET_PAIR_RESPONSE,
        ),
        patch(
            "pykrakenapi.KrakenAPI.get_ticker_information",
            return_value=TICKER_INFORMATION_RESPONSE,
        ),
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
    with (
        patch(
            "pykrakenapi.KrakenAPI.get_tradable_asset_pairs",
            return_value=TRADEABLE_ASSET_PAIR_RESPONSE,
        ),
        patch(
            "pykrakenapi.KrakenAPI.get_ticker_information",
            side_effect=KrakenAPIError("EQuery: Error"),
        ),
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
    with (
        patch(
            "pykrakenapi.KrakenAPI.get_tradable_asset_pairs",
            return_value=TRADEABLE_ASSET_PAIR_RESPONSE,
        ),
        patch(
            "pykrakenapi.KrakenAPI.get_ticker_information",
            side_effect=CallRateLimitError(),
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert "Exceeded the Kraken.com call rate limit" in caplog.text


async def test_migrate_entry_removes_scan_interval(hass: HomeAssistant) -> None:
    """Test migrating a v1.1 entry strips CONF_SCAN_INTERVAL from options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        options={
            CONF_SCAN_INTERVAL: 60,
            CONF_TRACKED_ASSET_PAIRS: ["XBT/USD"],
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "pykrakenapi.KrakenAPI.get_tradable_asset_pairs",
            return_value=TRADEABLE_ASSET_PAIR_RESPONSE,
        ),
        patch(
            "pykrakenapi.KrakenAPI.get_ticker_information",
            return_value=TICKER_INFORMATION_RESPONSE,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert CONF_SCAN_INTERVAL not in entry.options
    assert entry.options[CONF_TRACKED_ASSET_PAIRS] == ["XBT/USD"]
