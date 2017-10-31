"""The tests for the wake on lan switch platform."""
import json
import os
import unittest
from unittest.mock import patch

from homeassistant.setup import setup_component
from homeassistant.const import STATE_ON, STATE_OFF
import homeassistant.components.switch as switch
#import homeassistant.components.switch.wake_on_lan as wake_on_lan

from tests.common import get_test_home_assistant


TEST_STATE = None


def send_magic_packet(*macs, **kwargs):
    """Fake call for sending magic packets."""
    print("send_magic_packet", macs)
    return


def call(cmd, stdout, stderr):
    """Return fake subprocess return codes."""
    print("call(", cmd[5], ")")
    if cmd[5] == 'validhostname' and TEST_STATE:
        print("call_ok", TEST_STATE)
        return 0
    print("call_nook", TEST_STATE)
    return 2


def system():
    """Fake system call to test the windows platform."""
    return 'Windows'


class TestWOLSwitch(unittest.TestCase):
    """Test the wol switch."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('wakeonlan.wol.send_magic_packet', new=send_magic_packet)
    @patch('subprocess.call', new=call)
    def test_valid_hostname(self):
        """Test with valid hostname."""
        global TEST_STATE
        TEST_STATE = False
        self.assertTrue(setup_component(self.hass, switch.DOMAIN, {
            'switch': {
                'platform': 'wake_on_lan',
                'mac_address': '00-01-02-03-04-05',
                'host': 'validhostname',
            }
        }))

        state = self.hass.states.get('switch.wake_on_lan')
        self.assertEqual(STATE_OFF, state.state)
        
        TEST_STATE = True

        switch.turn_on(self.hass, 'switch.wake_on_lan')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.wake_on_lan')
        self.assertEqual(STATE_ON, state.state)

        switch.turn_off(self.hass, 'switch.wake_on_lan')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.wake_on_lan')
        self.assertEqual(STATE_ON, state.state)

    @patch('wakeonlan.wol.send_magic_packet', new=send_magic_packet)
    @patch('subprocess.call', new=call)
    @patch('platform.system', new=system)
    def test_valid_hostname_windows(self):
        """Test with valid hostname on windows."""
        global TEST_STATE
        TEST_STATE = False
        self.assertTrue(setup_component(self.hass, switch.DOMAIN, {
            'switch': {
                'platform': 'wake_on_lan',
                'mac_address': '00-01-02-03-04-05',
                'host': 'validhostname',
            }
        }))

        state = self.hass.states.get('switch.wake_on_lan')
        self.assertEqual(STATE_OFF, state.state)
        
        TEST_STATE = True

        switch.turn_on(self.hass, 'switch.wake_on_lan')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.wake_on_lan')
        self.assertEqual(STATE_ON, state.state)

    @patch('wakeonlan.wol.send_magic_packet', new=send_magic_packet)
    def test_minimal_config(self):
        """Test with minimal config."""
        self.assertTrue(setup_component(self.hass, switch.DOMAIN, {
            'switch': {
                'platform': 'wake_on_lan',
                'mac_address': '00-01-02-03-04-05',
            }
        }))

    @patch('wakeonlan.wol.send_magic_packet', new=send_magic_packet)
    @patch('subprocess.call', new=call)
    def test_broadcast_config(self):
        """Test with broadcast address config."""
        self.assertTrue(setup_component(self.hass, switch.DOMAIN, {
            'switch': {
                'platform': 'wake_on_lan',
                'mac_address': '00-01-02-03-04-05',
                'broadcast_address': '255.255.255.255',
            }
        }))

        state = self.hass.states.get('switch.wake_on_lan')
        self.assertEqual(STATE_OFF, state.state)

        switch.turn_on(self.hass, 'switch.wake_on_lan')
        self.hass.block_till_done()

    @patch('wakeonlan.wol.send_magic_packet', new=send_magic_packet)
    @patch('subprocess.call', new=call)
    def test_off_script(self):
        """Test with turn off script."""
        global TEST_STATE
        TEST_STATE = False
        self.assertTrue(setup_component(self.hass, switch.DOMAIN, {
            'switch': {
                'platform': 'wake_on_lan',
                'mac_address': '00-01-02-03-04-05',
                'host': 'validhostname',
                'turn_off': {
                    'service': 'shell_command.turn_off_TARGET',
                },
            }
        }))

        state = self.hass.states.get('switch.wake_on_lan')
        self.assertEqual(STATE_OFF, state.state)
        
        TEST_STATE = True

        switch.turn_on(self.hass, 'switch.wake_on_lan')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.wake_on_lan')
        self.assertEqual(STATE_ON, state.state)
        
        TEST_STATE = False

        switch.turn_off(self.hass, 'switch.wake_on_lan')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.wake_on_lan')
        self.assertEqual(STATE_OFF, state.state)

    @patch('wakeonlan.wol.send_magic_packet', new=send_magic_packet)
    @patch('subprocess.call', new=call)
    @patch('platform.system', new=system)
    def test_invalid_hostname_windows(self):
        """Test with invalid hostname on windows."""
        global TEST_STATE
        TEST_STATE = False
        self.assertTrue(setup_component(self.hass, switch.DOMAIN, {
            'switch': {
                'platform': 'wake_on_lan',
                'mac_address': '00-01-02-03-04-05',
                'host': 'invalidhostname',
            }
        }))

        state = self.hass.states.get('switch.wake_on_lan')
        self.assertEqual(STATE_OFF, state.state)
        
        TEST_STATE = True

        switch.turn_on(self.hass, 'switch.wake_on_lan')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.wake_on_lan')
        self.assertEqual(STATE_OFF, state.state)
