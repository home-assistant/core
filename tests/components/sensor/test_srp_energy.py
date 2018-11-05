"""The tests for the Srp Energy Platform."""
from unittest.mock import patch
import logging
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant

_LOGGER = logging.getLogger(__name__)

VALID_CONFIG_MINIMAL = {
    'sensor': {
        'platform': 'srp_energy',
        'username': 'foo',
        'password': 'bar',
        'id': 1234
    }
}


def mock_init(self, accountid, username, password):
    """Mock srpusage usage."""
    _LOGGER.log(logging.INFO, "Calling mock Init")
    return None

def mock_validate(self):
    """Mock srpusage usage."""
    _LOGGER.log(logging.INFO, "Calling mock Validate")
    return True

def mock_usage(self, startdate, enddate):  # pylint: disable=invalid-name
    """Mock srpusage usage."""
    _LOGGER.log(logging.INFO, "Calling mock usage")
    usage = [
        ('9/19/2018', '12:00 AM', '2018-09-19T00:00:00-7:00', '1.2', '0.17'),
        ('9/19/2018', '1:00 AM', '2018-09-19T01:00:00-7:00', '2.1', '0.30'),
        ('9/19/2018', '2:00 AM', '2018-09-19T02:00:00-7:00', '1.5', '0.23'),
        ('9/19/2018', '9:00 PM', '2018-09-19T21:00:00-7:00', '1.2', '0.19'),
        ('9/19/2018', '10:00 PM', '2018-09-19T22:00:00-7:00', '1.1', '0.18'),
        ('9/19/2018', '11:00 PM', '2018-09-19T23:00:00-7:00', '0.4', '0.09')
        ]
    return usage

def test_setup_with_config():
    """Test the platform setup with configuration."""
    with patch('srpenergy.client.SrpEnergyClient.__init__', new=mock_init), \
         patch('srpenergy.client.SrpEnergyClient.validate', new=mock_validate), \
         patch('srpenergy.client.SrpEnergyClient.usage', new=mock_usage):

        hass = get_test_home_assistant()

        setup_component(hass, 'sensor', VALID_CONFIG_MINIMAL)

        state = hass.states.get('sensor.srp_energy')
        assert state is not None
      
def test_daily_usage():
    """Test the platform setup with configuration."""
    with patch('srpenergy.client.SrpEnergyClient.__init__', new=mock_init), \
         patch('srpenergy.client.SrpEnergyClient.validate', new=mock_validate), \
         patch('srpenergy.client.SrpEnergyClient.usage', new=mock_usage):

        hass = get_test_home_assistant()
        setup_component(hass, 'sensor', VALID_CONFIG_MINIMAL)

        state = hass.states.get('sensor.srp_energy')

        assert state
        assert state.state == '7.50'

        assert state.attributes
        assert state.attributes.get('unit_of_measurement')
