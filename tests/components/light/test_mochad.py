"""The tests for the mochad light platform."""
import unittest
import unittest.mock as mock

import pytest

from homeassistant.components import light
from homeassistant.components.light import mochad
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


@pytest.fixture(autouse=True)
def pymochad_mock():
    """Mock pymochad."""
    with mock.patch.dict('sys.modules', {
        'pymochad': mock.MagicMock(),
    }):
        yield


class TestMochadSwitchSetup(unittest.TestCase):
    """Test the mochad light."""

    PLATFORM = mochad
    COMPONENT = light
    THING = 'light'

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch('homeassistant.components.light.mochad.MochadLight')
    def test_setup_adds_proper_devices(self, mock_light):
        """Test if setup adds devices."""
        good_config = {
            'mochad': {},
            'light': {
                'platform': 'mochad',
                'devices': [
                    {
                        'name': 'Light1',
                        'address': 'a1',
                    },
                ],
            }
        }
        self.assertTrue(setup_component(self.hass, light.DOMAIN, good_config))


class TestMochadLight(unittest.TestCase):
    """Test for mochad light platform."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        controller_mock = mock.MagicMock()
        dev_dict = {'address': 'a1', 'name': 'fake_light'}
        self.light = mochad.MochadLight(self.hass, controller_mock,
                                        dev_dict)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_name(self):
        """Test the name."""
        self.assertEqual('fake_light', self.light.name)

    def test_turn_on_with_no_brightness(self):
        """Test turn_on."""
        self.light.turn_on()
        self.light.device.send_cmd.assert_called_once_with('xdim 255')

    def test_turn_on_with_brightness(self):
        """Test turn_on."""
        self.light.turn_on(brightness=45)
        self.light.device.send_cmd.assert_called_once_with('xdim 45')

    def test_turn_off(self):
        """Test turn_off."""
        self.light.turn_off()
        self.light.device.send_cmd.assert_called_once_with('off')
