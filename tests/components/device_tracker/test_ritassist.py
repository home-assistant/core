"""The tests for the RitAssist device tracker."""
import unittest
import requests_mock
from homeassistant.setup import setup_component
from tests.common import load_fixture, get_test_home_assistant


class TestRitAssistSetup(unittest.TestCase):
    """Test the RitAssist device tracker."""

    def setUp(self):
        """Initialize values for this testcase class."""
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
        mock_req.post('https://api.ritassist.nl/api/session/login',
                     text=load_fixture('ritassist_authentication.json'))

        mock_req.get('https://api.ritassist.nl/api/equipment/Getfleet',
                     text=load_fixture('ritassist_fleet.json'))

        mock_req.get('https://secure.ritassist.nl/GenericServiceJSONP.ashx',
                     text=load_fixture('ritassist_extra_information.json'))

        self.assertTrue(setup_component(self.hass, 'device_tracker', self.config))

        entities = self.hass.states.async_entity_ids('device_tracker')
        self.assertEqual(len(entities), 1)

        state = self.hass.states.get('device_tracker.aa123a')
        self.assertIsNot(state, None)
        self.assertEqual(state.state, 'not_home')

        self.assertEqual(state.attributes.get('latitude'), 52.0)
        self.assertEqual(state.attributes.get('longitude'), 6.200000)

        self.assertEqual(state.attributes.get('fuel_level'), 55)
        self.assertEqual(state.attributes.get('coolant_temperature'), 60)
