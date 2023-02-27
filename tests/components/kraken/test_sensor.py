"""Tests for the kraken sensor platform."""
from datetime import timedelta
from unittest.mock import patch

from pykrakenapi.pykrakenapi import KrakenAPIError

from homeassistant.components.kraken.const import (
    CONF_TRACKED_ASSET_PAIRS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TRACKED_ASSET_PAIR,
    DOMAIN,
)
from homeassistant.const import CONF_SCAN_INTERVAL, EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.util.dt as dt_util

from .const import (
    MISSING_PAIR_TICKER_INFORMATION_RESPONSE,
    MISSING_PAIR_TRADEABLE_ASSET_PAIR_RESPONSE,
    TICKER_INFORMATION_RESPONSE,
    TRADEABLE_ASSET_PAIR_RESPONSE,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensor(hass: HomeAssistant) -> None:
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
            unique_id="0123456789",
            options={
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                CONF_TRACKED_ASSET_PAIRS: [
                    "ADA/XBT",
                    "ADA/ETH",
                    "XBT/EUR",
                    "XBT/GBP",
                    "XBT/USD",
                    "XBT/JPY",
                ],
            },
        )
        entry.add_to_hass(hass)

        registry = er.async_get(hass)

        # Pre-create registry entries for disabled by default sensors
        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "xbt_usd_ask_volume",
            suggested_object_id="xbt_usd_ask_volume",
            disabled_by=None,
        )

        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "xbt_usd_last_trade_closed",
            suggested_object_id="xbt_usd_last_trade_closed",
            disabled_by=None,
        )

        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "xbt_usd_bid_volume",
            suggested_object_id="xbt_usd_bid_volume",
            disabled_by=None,
        )

        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "xbt_usd_volume_today",
            suggested_object_id="xbt_usd_volume_today",
            disabled_by=None,
        )

        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "xbt_usd_volume_last_24h",
            suggested_object_id="xbt_usd_volume_last_24h",
            disabled_by=None,
        )

        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "xbt_usd_volume_weighted_average_today",
            suggested_object_id="xbt_usd_volume_weighted_average_today",
            disabled_by=None,
        )

        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "xbt_usd_volume_weighted_average_last_24h",
            suggested_object_id="xbt_usd_volume_weighted_average_last_24h",
            disabled_by=None,
        )

        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "xbt_usd_number_of_trades_today",
            suggested_object_id="xbt_usd_number_of_trades_today",
            disabled_by=None,
        )

        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "xbt_usd_number_of_trades_last_24h",
            suggested_object_id="xbt_usd_number_of_trades_last_24h",
            disabled_by=None,
        )

        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "xbt_usd_low_last_24h",
            suggested_object_id="xbt_usd_low_last_24h",
            disabled_by=None,
        )

        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "xbt_usd_high_last_24h",
            suggested_object_id="xbt_usd_high_last_24h",
            disabled_by=None,
        )

        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "xbt_usd_opening_price_today",
            suggested_object_id="xbt_usd_opening_price_today",
            disabled_by=None,
        )

        await hass.config_entries.async_setup(entry.entry_id)

        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        xbt_usd_sensor = hass.states.get("sensor.xbt_usd_ask")
        assert xbt_usd_sensor.state == "0.0003494"
        assert xbt_usd_sensor.attributes["icon"] == "mdi:currency-usd"

        xbt_eur_sensor = hass.states.get("sensor.xbt_eur_ask")
        assert xbt_eur_sensor.state == "0.0003494"
        assert xbt_eur_sensor.attributes["icon"] == "mdi:currency-eur"

        ada_xbt_sensor = hass.states.get("sensor.ada_xbt_ask")
        assert ada_xbt_sensor.state == "0.0003494"
        assert ada_xbt_sensor.attributes["icon"] == "mdi:currency-btc"

        xbt_jpy_sensor = hass.states.get("sensor.xbt_jpy_ask")
        assert xbt_jpy_sensor.state == "0.0003494"
        assert xbt_jpy_sensor.attributes["icon"] == "mdi:currency-jpy"

        xbt_gbp_sensor = hass.states.get("sensor.xbt_gbp_ask")
        assert xbt_gbp_sensor.state == "0.0003494"
        assert xbt_gbp_sensor.attributes["icon"] == "mdi:currency-gbp"

        ada_eth_sensor = hass.states.get("sensor.ada_eth_ask")
        assert ada_eth_sensor.state == "0.0003494"
        assert ada_eth_sensor.attributes["icon"] == "mdi:cash"

        xbt_usd_ask_volume = hass.states.get("sensor.xbt_usd_ask_volume")
        assert xbt_usd_ask_volume.state == "15949"

        xbt_usd_last_trade_closed = hass.states.get("sensor.xbt_usd_last_trade_closed")
        assert xbt_usd_last_trade_closed.state == "0.0003478"

        xbt_usd_bid_volume = hass.states.get("sensor.xbt_usd_bid_volume")
        assert xbt_usd_bid_volume.state == "20792"

        xbt_usd_volume_today = hass.states.get("sensor.xbt_usd_volume_today")
        assert xbt_usd_volume_today.state == "146300.24906838"

        xbt_usd_volume_last_24h = hass.states.get("sensor.xbt_usd_volume_last_24h")
        assert xbt_usd_volume_last_24h.state == "253478.04715403"

        xbt_usd_volume_weighted_average_today = hass.states.get(
            "sensor.xbt_usd_volume_weighted_average_today"
        )
        assert xbt_usd_volume_weighted_average_today.state == "0.000348573"

        xbt_usd_volume_weighted_average_last_24h = hass.states.get(
            "sensor.xbt_usd_volume_weighted_average_last_24h"
        )
        assert xbt_usd_volume_weighted_average_last_24h.state == "0.000344881"

        xbt_usd_number_of_trades_today = hass.states.get(
            "sensor.xbt_usd_number_of_trades_today"
        )
        assert xbt_usd_number_of_trades_today.state == "82"

        xbt_usd_number_of_trades_last_24h = hass.states.get(
            "sensor.xbt_usd_number_of_trades_last_24h"
        )
        assert xbt_usd_number_of_trades_last_24h.state == "128"

        xbt_usd_low_last_24h = hass.states.get("sensor.xbt_usd_low_last_24h")
        assert xbt_usd_low_last_24h.state == "0.0003446"

        xbt_usd_high_last_24h = hass.states.get("sensor.xbt_usd_high_last_24h")
        assert xbt_usd_high_last_24h.state == "0.0003521"

        xbt_usd_opening_price_today = hass.states.get(
            "sensor.xbt_usd_opening_price_today"
        )
        assert xbt_usd_opening_price_today.state == "0.0003513"


async def test_sensors_available_after_restart(hass: HomeAssistant) -> None:
    """Test that all sensors are added again after a restart."""
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

        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "XBT_USD")},
            name="XBT USD",
            manufacturer="Kraken.com",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)

        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        sensor = hass.states.get("sensor.xbt_usd_ask")
        assert sensor.state == "0.0003494"


async def test_sensors_added_after_config_update(hass: HomeAssistant) -> None:
    """Test that sensors are added when another tracked asset pair is added."""
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

        assert hass.states.get("sensor.xbt_usd_ask")
        assert not hass.states.get("sensor.ada_xbt_ask")

        hass.config_entries.async_update_entry(
            entry,
            options={
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                CONF_TRACKED_ASSET_PAIRS: [DEFAULT_TRACKED_ASSET_PAIR, "ADA/XBT"],
            },
        )
        async_fire_time_changed(
            hass, utcnow + timedelta(seconds=DEFAULT_SCAN_INTERVAL * 2)
        )
        await hass.async_block_till_done()

        assert hass.states.get("sensor.ada_xbt_ask")


async def test_missing_pair_marks_sensor_unavailable(hass: HomeAssistant) -> None:
    """Test that a missing tradable asset pair marks the sensor unavailable."""
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow), patch(
        "pykrakenapi.KrakenAPI.get_tradable_asset_pairs",
        return_value=TRADEABLE_ASSET_PAIR_RESPONSE,
    ) as tradeable_asset_pairs_mock, patch(
        "pykrakenapi.KrakenAPI.get_ticker_information",
        return_value=TICKER_INFORMATION_RESPONSE,
    ) as ticket_information_mock:
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

        sensor = hass.states.get("sensor.xbt_usd_ask")
        assert sensor.state == "0.0003494"

        tradeable_asset_pairs_mock.return_value = (
            MISSING_PAIR_TRADEABLE_ASSET_PAIR_RESPONSE
        )
        ticket_information_mock.side_effect = KrakenAPIError(
            "EQuery:Unknown asset pair"
        )
        async_fire_time_changed(
            hass, utcnow + timedelta(seconds=DEFAULT_SCAN_INTERVAL * 2)
        )
        await hass.async_block_till_done()

        ticket_information_mock.side_effect = None
        ticket_information_mock.return_value = MISSING_PAIR_TICKER_INFORMATION_RESPONSE
        async_fire_time_changed(
            hass, utcnow + timedelta(seconds=DEFAULT_SCAN_INTERVAL * 2)
        )
        await hass.async_block_till_done()

        sensor = hass.states.get("sensor.xbt_usd_ask")
        assert sensor.state == "unavailable"
