"""The tests for the mochad switch platform."""
import unittest
import unittest.mock as mock

import pytest

from homeassistant.setup import setup_component
from homeassistant.components import switch
from homeassistant.components.switch import mochad

from tests.common import get_test_home_assistant


@pytest.fixture(autouse=True)
def pymochad_mock():
    """Mock pymochad."""
    with mock.patch.dict('sys.modules', {
        'pymochad': mock.MagicMock(),
    }):
        yield


class TestMochadSwitchSetup(unittest.TestCase):
    """Test the mochad switch."""

    PLATFORM = mochad
    COMPONENT = switch
    THING = 'switch'

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch('homeassistant.components.switch.mochad.MochadSwitch')
    def test_setup_adds_proper_devices(self, mock_switch):
        """Test if setup adds devices."""
        good_config = {
            'mochad': {},
            'switch': {
                'platform': 'mochad',
                'devices': [
                    {
                        'name': 'Switch1',
                        'address': 'a1',
                    },
                ],
            }
        }
        self.assertTrue(setup_component(self.hass, switch.DOMAIN, good_config))


class TestMochadSwitch(unittest.TestCase):
    """Test for mochad switch platform."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        controller_mock = mock.MagicMock()
        dev_dict = {'address': 'a1', 'name': 'fake_switch'}
        self.switch = mochad.MochadSwitch(self.hass, controller_mock,
                                          dev_dict)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_name(self):
        """Test the name."""
        self.assertEqual('fake_switch', self.switch.name)

    def test_turn_on(self):
        """Test turn_on."""
        self.switch.turn_on()
        self.switch.device.send_cmd.assert_called_once_with('on')

    def test_turn_off(self):
        """Test turn_off."""
        self.switch.turn_off()
        self.switch.device.send_cmd.assert_called_once_with('off')
