"""Tests for the kraken sensor platform."""
from datetime import timedelta

from pykrakenapi.pykrakenapi import KrakenAPIError

from homeassistant.components.kraken.const import (
    CONF_TRACKED_ASSET_PAIRS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TRACKED_ASSET_PAIR,
    DOMAIN,
)
from homeassistant.const import CONF_SCAN_INTERVAL, EVENT_HOMEASSISTANT_START
import homeassistant.util.dt as dt_util

from .const import TICKER_INFORMATION_RESPONSE, TRADEABLE_ASSET_PAIR_RESPONSE

from tests.async_mock import patch
from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensor(hass):
    """Test that sensor has a value."""
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow), patch(
        "pykrakenapi.KrakenAPI.get_tradable_asset_pairs",
        return_value=TRADEABLE_ASSET_PAIR_RESPONSE,
    ), patch(
        "pykrakenapi.KrakenAPI.get_ticker_information",
        return_value=TICKER_INFORMATION_RESPONSE,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            options={
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                CONF_TRACKED_ASSET_PAIRS: [DEFAULT_TRACKED_ASSET_PAIR],
            },
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)

        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        sensor = hass.states.get("sensor.xbt_usd_last_trade_closed")
        assert sensor.state == "0.0003478"


async def test_missing_pair_marks_sensor_unavailable(hass):
    """Test that a missing tradable asset pair marks the sensor unavailable."""
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow), patch(
        "pykrakenapi.KrakenAPI.get_tradable_asset_pairs",
        return_value=TRADEABLE_ASSET_PAIR_RESPONSE,
    ):
        with patch(
            "pykrakenapi.KrakenAPI.get_ticker_information",
            return_value=TICKER_INFORMATION_RESPONSE,
        ):
            entry = MockConfigEntry(
                domain=DOMAIN,
                options={
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    CONF_TRACKED_ASSET_PAIRS: [DEFAULT_TRACKED_ASSET_PAIR],
                },
            )
            entry.add_to_hass(hass)

            await hass.config_entries.async_setup(entry.entry_id)

            await hass.async_block_till_done()

            hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
            await hass.async_block_till_done()

            sensor = hass.states.get("sensor.xbt_usd_last_trade_closed")
            assert sensor.state == "0.0003478"

        with patch(
            "pykrakenapi.KrakenAPI.get_ticker_information",
            side_effect=KrakenAPIError("EQuery:Unknown asset pair"),
        ):
            async_fire_time_changed(
                hass, utcnow + timedelta(seconds=DEFAULT_SCAN_INTERVAL * 2)
            )
            await hass.async_block_till_done()

            sensor = hass.states.get("sensor.xbt_usd_last_trade_closed")
            assert sensor.state == "unknown"

            async_fire_time_changed(
                hass, utcnow + timedelta(seconds=DEFAULT_SCAN_INTERVAL * 2)
            )
            await hass.async_block_till_done()

            sensor = hass.states.get("sensor.xbt_usd_last_trade_closed")
            assert sensor.state == "unavailable"
