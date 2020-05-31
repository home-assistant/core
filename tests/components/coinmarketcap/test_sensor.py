"""Tests for the CoinMarketCap sensor platform."""
import json
import unittest

import homeassistant.components.sensor as sensor
from homeassistant.setup import setup_component

from tests.async_mock import patch
from tests.common import assert_setup_component, get_test_home_assistant, load_fixture

VALID_CONFIG = {
    "platform": "coinmarketcap",
    "currency_id": 1027,
    "display_currency": "EUR",
    "display_currency_decimals": 3,
}


class TestCoinMarketCapSensor(unittest.TestCase):
    """Test the CoinMarketCap sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch(
        "coinmarketcap.Market.ticker",
        return_value=json.loads(load_fixture("coinmarketcap.json")),
    )
    def test_setup(self, mock_request):
        """Test the setup with custom settings."""
        with assert_setup_component(1, sensor.DOMAIN):
            assert setup_component(self.hass, sensor.DOMAIN, {"sensor": VALID_CONFIG})

        state = self.hass.states.get("sensor.ethereum")
        assert state is not None

        assert state.state == "493.455"
        assert state.attributes.get("symbol") == "ETH"
        assert state.attributes.get("unit_of_measurement") == "EUR"
