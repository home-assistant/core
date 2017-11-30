"""The test for the hydroquebec sensor platform."""
import asyncio
import sys
import unittest
from unittest.mock import patch, MagicMock

from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant

CONTRACT = "123456789"


class HydroQuebecClientMock(MagicMock):
    """Fake Hydroquebec client."""

    def __init__(self, username, password, contract=None):
        """Fake Hydroquebec client init."""
        pass

    def get_data(self, contract):
        """Return fake hydroquebec data."""
        return {CONTRACT: {"balance": 160.12}}

    def get_contracts(self):
        """Return fake hydroquebec contracts."""
        return [CONTRACT]

    @asyncio.coroutine
    def fetch_data(self):
        """Return fake fetching data."""
        pass


class PyHydroQuebecErrorMock(Exception):
    """Fake PyHydroquebec Error."""


class TestHydroquebecSensor(unittest.TestCase):
    """Test the Random number sensor."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Setup things to be run when tests are started."""
        sys.modules['pyhydroquebec'] = MagicMock()
        sys.modules['pyhydroquebec.client'] = MagicMock()
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('pyhydroquebec.HydroQuebecClient',
           new=HydroQuebecClientMock)
    @patch('pyhydroquebec.client.PyHydroQuebecError',
           new=PyHydroQuebecErrorMock)
    def test_hydroquebec_sensor(self):
        """Test the Hydroquebec number sensor."""
        config = {
            'sensor': {
                'platform': 'hydroquebec',
                'name': 'hydro',
                'contract': CONTRACT,
                'username': 'myusername',
                'password': 'password',
                'monitored_variables': [
                    'balance',
                ],
            }
        }
        assert setup_component(self.hass, 'sensor', config)
        state = self.hass.states.get('sensor.hydro_balance')
        self.assertEqual(state.state, "160.12")
        self.assertEqual(state.attributes.get('unit_of_measurement'), "CAD")
