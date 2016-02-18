"""
tests.components.switch.test_mfi
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests mFi switch.
"""
import unittest
import unittest.mock as mock

import homeassistant.components.switch as switch
import homeassistant.components.switch.mfi as mfi
from tests.components.sensor import test_mfi as test_mfi_sensor

from tests.common import get_test_home_assistant


class TestMfiSwitchSetup(test_mfi_sensor.TestMfiSensorSetup):
    PLATFORM = mfi
    COMPONENT = switch
    THING = 'switch'
    GOOD_CONFIG = {
        'switch': {
            'platform': 'mfi',
            'host': 'foo',
            'port': 6123,
            'username': 'user',
            'password': 'pass',
        }
    }

    @mock.patch('mficlient.client.MFiClient')
    @mock.patch('homeassistant.components.switch.mfi.MfiSwitch')
    def test_setup_adds_proper_devices(self, mock_switch, mock_client):
        ports = {i: mock.MagicMock(model=model)
                 for i, model in enumerate(mfi.SWITCH_MODELS)}
        ports['bad'] = mock.MagicMock(model='notaswitch')
        print(ports['bad'].model)
        mock_client.return_value.get_devices.return_value = \
            [mock.MagicMock(ports=ports)]
        assert self.COMPONENT.setup(self.hass, self.GOOD_CONFIG)
        for ident, port in ports.items():
            if ident != 'bad':
                mock_switch.assert_any_call(port)
        assert mock.call(ports['bad'], self.hass) not in mock_switch.mock_calls


class TestMfiSwitch(unittest.TestCase):
    def setup_method(self, method):
        self.hass = get_test_home_assistant()
        self.hass.config.latitude = 32.87336
        self.hass.config.longitude = 117.22743
        self.port = mock.MagicMock()
        self.switch = mfi.MfiSwitch(self.port)

    def teardown_method(self, method):
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_name(self):
        self.assertEqual(self.port.label, self.switch.name)

    def test_update(self):
        self.switch.update()
        self.port.refresh.assert_called_once_with()

    def test_update_with_target_state(self):
        self.switch._target_state = True
        self.port.data = {}
        self.port.data['output'] = 'stale'
        self.switch.update()
        self.assertEqual(1.0, self.port.data['output'])
        self.assertEqual(None, self.switch._target_state)
        self.port.data['output'] = 'untouched'
        self.switch.update()
        self.assertEqual('untouched', self.port.data['output'])

    def test_turn_on(self):
        self.switch.turn_on()
        self.port.control.assert_called_once_with(True)
        self.assertTrue(self.switch._target_state)

    def test_turn_off(self):
        self.switch.turn_off()
        self.port.control.assert_called_once_with(False)
        self.assertFalse(self.switch._target_state)

    def test_current_power_mwh(self):
        self.port.data = {'active_pwr': 1}
        self.assertEqual(1000, self.switch.current_power_mwh)

    def test_current_power_mwh_no_data(self):
        self.port.data = {'notpower': 123}
        self.assertEqual(0, self.switch.current_power_mwh)

    def test_device_state_attributes(self):
        self.port.data = {'v_rms': 1.25,
                          'i_rms': 2.75}
        self.assertEqual({'volts': 1.2, 'amps': 2.8},
                         self.switch.device_state_attributes)
