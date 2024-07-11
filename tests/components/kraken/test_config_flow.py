"""Tests for the kraken config_flow."""

from unittest.mock import patch

from homeassistant.components.kraken.const import CONF_TRACKED_ASSET_PAIRS, DOMAIN
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    MISSING_PAIR_TRADEABLE_ASSET_PAIR_RESPONSE,
    TICKER_INFORMATION_RESPONSE,
    TRADEABLE_ASSET_PAIR_RESPONSE,
)

from tests.common import MockConfigEntry


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test we can finish a config flow."""
    with patch(
        "homeassistant.components.kraken.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test we cannot add a second config flow."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options(hass: HomeAssistant) -> None:
    """Test options for Kraken."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_SCAN_INTERVAL: 60,
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

    with (
        patch(
            "homeassistant.components.kraken.config_flow.KrakenAPI.get_tradable_asset_pairs",
            return_value=TRADEABLE_ASSET_PAIR_RESPONSE,
        ),
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

        assert hass.states.get("sensor.xbt_usd_ask")

        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_SCAN_INTERVAL: 10,
                CONF_TRACKED_ASSET_PAIRS: ["ADA/ETH"],
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()

        ada_eth_sensor = hass.states.get("sensor.ada_eth_ask")
        assert ada_eth_sensor.state == "0.0003494"

        assert hass.states.get("sensor.xbt_usd_ask") is None


async def test_deselect_removed_pair(hass: HomeAssistant) -> None:
    """Test options for Kraken."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_SCAN_INTERVAL: 60,
            CONF_TRACKED_ASSET_PAIRS: [
                "XBT/USD",
            ],
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.kraken.config_flow.KrakenAPI.get_tradable_asset_pairs",
            return_value=TRADEABLE_ASSET_PAIR_RESPONSE,
        ),
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

    with (
        patch(
            "homeassistant.components.kraken.config_flow.KrakenAPI.get_tradable_asset_pairs",
            return_value=MISSING_PAIR_TRADEABLE_ASSET_PAIR_RESPONSE,
        ),
        patch(
            "pykrakenapi.KrakenAPI.get_tradable_asset_pairs",
            return_value=MISSING_PAIR_TRADEABLE_ASSET_PAIR_RESPONSE,
        ),
        patch(
            "pykrakenapi.KrakenAPI.get_ticker_information",
            return_value=TICKER_INFORMATION_RESPONSE,
        ),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        schema = result["data_schema"].schema
        assert "XBT/USD" in schema.get(CONF_TRACKED_ASSET_PAIRS).options
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_SCAN_INTERVAL: 10,
                CONF_TRACKED_ASSET_PAIRS: ["ADA/ETH"],
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()

        ada_eth_sensor = hass.states.get("sensor.ada_eth_ask")
        assert ada_eth_sensor.state == "0.0003494"
