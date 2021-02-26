"""Tests for Binance integration."""
from homeassistant.components.binance.const import (
    CONF_API_SECRET,
    CONF_BALANCES,
    CONF_MARKETS,
)
from homeassistant.const import CONF_API_KEY

USER_INPUT = {
    CONF_API_KEY: "mock-api-key",
    CONF_API_SECRET: "mock-api-secret",
}

USER_INPUT_MARKETS = {CONF_MARKETS: ["DGB-USDT", "BTC-USDT"]}

USER_INPUT_BALANCES = {CONF_BALANCES: ["USDT", "DGB"]}

INTEGRATION_TITLE = "Markets: DGB-USDT, BTC-USDT"
