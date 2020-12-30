"""Tests for Bittrex integration."""
from homeassistant.components.bittrex.const import CONF_API_SECRET, CONF_MARKETS, DOMAIN
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry

ENTRY_CONFIG = {
    CONF_API_KEY: "mock-api-key",
    CONF_API_SECRET: "mock-api-secret",
    CONF_MARKETS: ["BTC-USDT", "DGB-USDT"],
}

USER_INPUT = {
    CONF_API_KEY: "mock-api-key",
    CONF_API_SECRET: "mock-api-secret",
}


async def init_integration(hass, skip_setup=False) -> MockConfigEntry:
    """Set up the Bittrex integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="DGB-USD, BTC-USD",
        unique_id="0123456789",
        data=ENTRY_CONFIG,
    )

    entry.add_to_hass(hass)
    return entry
