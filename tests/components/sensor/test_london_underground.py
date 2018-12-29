"""The tests for the tube_state platform."""
import json
import unittest
import requests_mock

from homeassistant.components.sensor.london_underground import CONF_LINE, URL
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant

VALID_CONFIG = {
    'platform': 'london_underground',
    CONF_LINE: [
        'London Overground',
    ]
}

VALID_RESPONSE = [
    {
        "id": "london-overground",
        "name": "London Overground",
        "modeName": "overground",
        "disruptions": [
        ],
        "lineStatuses": [
            {
                "statusSeverityDescription": "Minor Delays",

                "disruption": {

                    "additionalInfo": "Something\r\nelse"
                }
            }
        ],

    },
]

class TestLondonTubeSensor(unittest.TestCase):
    """Test the tube_state platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup(self, mock_req):
        """Test for operational tube_state sensor with proper attributes."""
        mock_req.get(URL, text=json.dumps(VALID_RESPONSE))
        assert setup_component(self.hass, 'sensor', {'sensor': self.config})

        state = self.hass.states.get('sensor.london_overground')
        assert state.state == 'Minor Delays'
        assert state.attributes.get('Description') == 'Something else'
