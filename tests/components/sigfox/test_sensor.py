"""Tests for the sigfox sensor."""
import re
import unittest

import requests_mock

from homeassistant.components.sigfox.sensor import (
    API_URL,
    CONF_API_LOGIN,
    CONF_API_PASSWORD,
)
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant

TEST_API_LOGIN = "foo"
TEST_API_PASSWORD = "ebcd1234"

VALID_CONFIG = {
    "sensor": {
        "platform": "sigfox",
        CONF_API_LOGIN: TEST_API_LOGIN,
        CONF_API_PASSWORD: TEST_API_PASSWORD,
    }
}

VALID_MESSAGE = """
{"data":[{
"time":1521879720,
"data":"7061796c6f6164",
"rinfos":[{"lat":"0.0","lng":"0.0"}],
"snr":"50.0"}]}
"""


class TestSigfoxSensor(unittest.TestCase):
    """Test the sigfox platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.hass.stop)

    def test_invalid_credentials(self):
        """Test for invalid credentials."""
        with requests_mock.Mocker() as mock_req:
            url = re.compile(API_URL + "devicetypes")
            mock_req.get(url, text="{}", status_code=401)
            assert setup_component(self.hass, "sensor", VALID_CONFIG)
            self.hass.block_till_done()
        assert len(self.hass.states.entity_ids()) == 0

    def test_valid_credentials(self):
        """Test for valid credentials."""
        with requests_mock.Mocker() as mock_req:
            url1 = re.compile(API_URL + "devicetypes")
            mock_req.get(url1, text='{"data":[{"id":"fake_type"}]}', status_code=200)

            url2 = re.compile(API_URL + "devicetypes/fake_type/devices")
            mock_req.get(url2, text='{"data":[{"id":"fake_id"}]}')

            url3 = re.compile(API_URL + "devices/fake_id/messages*")
            mock_req.get(url3, text=VALID_MESSAGE)

            assert setup_component(self.hass, "sensor", VALID_CONFIG)
            self.hass.block_till_done()

            assert len(self.hass.states.entity_ids()) == 1
            state = self.hass.states.get("sensor.sigfox_fake_id")
            assert state.state == "payload"
            assert state.attributes.get("snr") == "50.0"
