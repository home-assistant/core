"""Tests for the CoinMarketCap sensor platform."""
import json
from unittest.mock import patch

import pytest

from homeassistant.components.sensor import DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, load_fixture

VALID_CONFIG = {
    DOMAIN: {
        "platform": "coinmarketcap",
        "currency_id": 1027,
        "display_currency": "EUR",
        "display_currency_decimals": 3,
    }
}


@pytest.fixture
async def setup_sensor(hass):
    """Set up demo sensor component."""
    with assert_setup_component(1, DOMAIN):
        with patch(
            "coinmarketcap.Market.ticker",
            return_value=json.loads(load_fixture("coinmarketcap.json")),
        ):
            await async_setup_component(hass, DOMAIN, VALID_CONFIG)
            await hass.async_block_till_done()


async def test_setup(hass, setup_sensor):
    """Test the setup with custom settings."""
    state = hass.states.get("sensor.ethereum")
    assert state is not None

    assert state.name == "Ethereum"
    assert state.state == "493.455"
    assert state.attributes.get("symbol") == "ETH"
    assert state.attributes.get("unit_of_measurement") == "EUR"
