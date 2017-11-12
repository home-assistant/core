"""Tests for FS20 switch."""

import unittest
from unittest.mock import patch
import homeassistant.components.switch as switch

from homeassistant.components import fhz
from homeassistant.components.switch import fs20
from homeassistant.const import STATE_ON, STATE_OFF
from tests.common import get_test_home_assistant, setup_component


def test_code_to_byte():
    """Conversion of FS20 codes to byte."""
    assert fs20.code_to_byte("1121") == 4
    assert fs20.code_to_byte("3123") == 134


class TestSwitchFS20(unittest.TestCase):
    """Test FS20 switch."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self._code = None
        self._command = None
        self._number_of_repeats = None

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_valid_config(self):
        """Test configuration."""
        assert setup_component(self.hass, 'switch', {
            'switch': {
                'platform': 'fs20',
                'name': 'Light in Kitchen',
                'code': '1234',
                }
            })

    def mock_send_fs20_command(self, *args, **kwargs):
        """Mock the send_fs20_command method of the fhz device."""
        self._code = args[0]
        self._command = args[1]
        self._number_of_repeats = args[2]

    @patch('homeassistant.components.fhz.FhzDevice')
    def test_switch_on(self, mock_fhz_device):
        """Switch on the light."""
        fhz.DEVICE = mock_fhz_device()
        fhz.DEVICE.send_fs20_command.side_effect = self.mock_send_fs20_command

        assert setup_component(self.hass, 'switch', {
            'switch': {
                'platform': 'fs20',
                'name': 'kitchen_light',
                'code': '3123',
                'number_of_repeats': 3,
                }
            })
        state = self.hass.states.get('switch.kitchen_light')
        self.assertEqual(STATE_OFF, state.state)

        switch.turn_on(self.hass, 'switch.kitchen_light')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.kitchen_light')
        self.assertEqual(STATE_ON, state.state)

        # pylint: disable=E1101
        assert fhz.DEVICE.send_fs20_command.call_count == 1
        assert self._code == 134
        assert self._command == fhz.COMMAND_ON
        assert self._number_of_repeats == 3

    @patch('homeassistant.components.fhz.FhzDevice')
    def test_switch_off(self, mock_fhz_device):
        """Switch off the light."""
        fhz.DEVICE = mock_fhz_device()
        fhz.DEVICE.send_fs20_command.side_effect = self.mock_send_fs20_command

        assert setup_component(self.hass, 'switch', {
            'switch': {
                'platform': 'fs20',
                'name': 'kitchen_light',
                'code': '1121',
                }
            })
        # By default it is already off initial but anyway. #
        state = self.hass.states.get('switch.kitchen_light')
        self.assertEqual(STATE_OFF, state.state)

        switch.turn_off(self.hass, 'switch.kitchen_light')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.kitchen_light')
        self.assertEqual(STATE_OFF, state.state)

        # pylint: disable=E1101
        assert fhz.DEVICE.send_fs20_command.call_count == 1
        assert self._code == 4
        assert self._command == fhz.COMMAND_OFF
        assert self._number_of_repeats == 1
