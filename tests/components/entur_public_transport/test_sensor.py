"""The tests for the entur platform."""
from datetime import datetime
import unittest
from unittest.mock import patch

from enturclient.api import RESOURCE
from enturclient.consts import ATTR_EXPECTED_AT, ATTR_ROUTE, ATTR_STOP_ID
import requests_mock

from homeassistant.components.entur_public_transport.sensor import (
    CONF_EXPAND_PLATFORMS, CONF_STOP_IDS)
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant, load_fixture

VALID_CONFIG = {
    'platform': 'entur_public_transport',
    CONF_EXPAND_PLATFORMS: False,
    CONF_STOP_IDS: [
        'NSR:StopPlace:548',
        'NSR:Quay:48550',
    ]
}

FIXTURE_FILE = 'entur_public_transport.json'
TEST_TIMESTAMP = datetime(2018, 10, 10, 7, tzinfo=dt_util.UTC)


class TestEnturPublicTransportSensor(unittest.TestCase):
    """Test the entur platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    @patch(
        'homeassistant.components.entur_public_transport.sensor.dt_util.now',
        return_value=TEST_TIMESTAMP)
    def test_setup(self, mock_req, mock_patch):
        """Test for correct sensor setup with state and proper attributes."""
        mock_req.post(RESOURCE,
                      text=load_fixture(FIXTURE_FILE),
                      status_code=200)
        self.assertTrue(
            setup_component(self.hass, 'sensor', {'sensor': VALID_CONFIG}))

        state = self.hass.states.get('sensor.entur_bergen_stasjon')
        assert state.state == '28'
        assert state.attributes.get(ATTR_STOP_ID) == 'NSR:StopPlace:548'
        assert state.attributes.get(ATTR_ROUTE) == "59 Bergen"
        assert state.attributes.get(ATTR_EXPECTED_AT) \
            == '2018-10-10T09:28:00+0200'

        state = self.hass.states.get('sensor.entur_fiskepiren_platform_2')
        assert state.state == '0'
        assert state.attributes.get(ATTR_STOP_ID) == 'NSR:Quay:48550'
        assert state.attributes.get(ATTR_ROUTE) \
            == "5 Stavanger Airport via Forum"
        assert state.attributes.get(ATTR_EXPECTED_AT) \
            == '2018-10-10T09:00:00+0200'
