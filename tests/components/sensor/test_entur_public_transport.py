"""The tests for the tube_state platform."""
from datetime import datetime
import unittest
from unittest.mock import patch

import requests_mock

from homeassistant.components.sensor.entur_public_transport import (
    ATTR_EXPECTED_AT, ATTR_ROUTE, ATTR_STOP_ID, CONF_STOP_IDS, RESOURCE)
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant, load_fixture

VALID_CONFIG = {
    'platform': 'entur_public_transport',
    CONF_STOP_IDS: [
        'NSR:StopPlace:548',
        'NSR:Quay:48550',
    ]
}

FIXTURE_FILE = 'entur_public_transport.json'
TEST_TIMESTAMP = datetime(2018, 10, 10, 7, tzinfo=dt_util.UTC)


class TestEnturPublicTransportSensor(unittest.TestCase):
    """Test the tube_state platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    @patch(
        'homeassistant.components.sensor.entur_public_transport.dt_util.now',
        return_value=TEST_TIMESTAMP)
    def test_setup(self, mock_req, mock_patch):
        """Test for correct sensor setup with state and proper attributes."""
        mock_req.post(RESOURCE,
                      text=load_fixture(FIXTURE_FILE),
                      status_code=200)
        self.assertTrue(
            setup_component(self.hass, 'sensor', {'sensor': self.config}))

        state = self.hass.states.get('sensor.entur_bergen_stasjon_departures')
        assert state.state == '28'
        assert state.attributes.get(ATTR_STOP_ID) == 'NSR:StopPlace:548'
        assert state.attributes.get(ATTR_ROUTE) == "Vossabanen Bergen"
        assert state.attributes.get(ATTR_EXPECTED_AT) \
            == '2018-10-10T09:28:00+0200'

        state = self.hass.states.get('sensor.entur_fiskepiren_departures')
        assert state.state == '0'
        assert state.attributes.get(ATTR_STOP_ID) == 'NSR:Quay:48550'
        assert state.attributes.get(ATTR_ROUTE) \
            == "Flybussen Stavanger Airport via Forum"
        assert state.attributes.get(ATTR_EXPECTED_AT) \
            == '2018-10-10T09:00:00+0200'
