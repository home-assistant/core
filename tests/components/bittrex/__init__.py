"""Tests for Bittrex integration."""
from homeassistant.components.bittrex.const import CONF_API_SECRET, CONF_MARKETS
from homeassistant.const import CONF_API_KEY

USER_INPUT = {
    CONF_API_KEY: "mock-api-key",
    CONF_API_SECRET: "mock-api-secret",
}

USER_INPUT_MARKETS = {CONF_MARKETS: ["DGB-USDT", "BTC-USDT"]}

INTEGRATION_TITLE = "DGB-USDT, BTC-USDT"
