"""The tests for the RitAssist device tracker."""
import unittest
import requests_mock
from tests.common import load_fixture, get_test_home_assistant

from homeassistant.components.device_tracker.ritassist import (
    RitAssistDeviceScanner)


class TestRitAssistSetup(unittest.TestCase):
    """Test the RitAssist device tracker."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.devices = []
        self.hass = get_test_home_assistant()
        self.config = {
            'device_tracker': {
                'platform': 'ritassist',
                'client_id': 'client_id',
                'client_secret': 'client_secret',
                'username': 'username',
                'password': 'passwword',
                'include': [
                    'AA-123-A'
                ]
            }
        }

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup(self, mock_req):
        """Test for successfully setting up the platform."""
        self._setup_mock_requests(mock_req)

        scanner = RitAssistDeviceScanner(self.hass, self.config, None, None)
        self.assertEqual(len(scanner.devices), 1)

        device = scanner.devices[0]
        self.assertEqual(device.longitude, 6.2)
        self.assertEqual(device.latitude, 52.0)
        self.assertEqual(device.license_plate, 'AA-123-A')
        self.assertEqual(device.equipment_id, '12344321')
        self.assertEqual(device.identifier, 3372993813)

        self.assertEqual(device.state_attributes['fuel_level'], 55)
        self.assertEqual(device.state_attributes['coolant_temperature'], 60)

    def _setup_mock_requests(self, mock_req):
        mock_req.post('https://api.ritassist.nl/api/session/login',
                      text=load_fixture('ritassist_authentication.json'))

        mock_req.get('https://api.ritassist.nl/api/equipment/Getfleet',
                     text=load_fixture('ritassist_fleet.json'))

        mock_req.get('https://secure.ritassist.nl/GenericServiceJSONP.ashx',
                     text=load_fixture('ritassist_extra_information.json'))
