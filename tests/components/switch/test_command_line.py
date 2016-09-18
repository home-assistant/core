"""the tests for the Command line switch platform."""
import json
import os
import tempfile
import unittest

from homeassistant.bootstrap import setup_component
from homeassistant.const import STATE_ON, STATE_OFF
import homeassistant.components.switch as switch
import homeassistant.components.switch.command_line as command_line

from tests.common import get_test_home_assistant


class TestCommandSwitch(unittest.TestCase):
    """Test the command switch."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_state_none(self):
        """Test with none state."""
        with tempfile.TemporaryDirectory() as tempdirname:
            path = os.path.join(tempdirname, 'switch_status')
            test_switch = {
                'command_on': 'echo 1 > {}'.format(path),
                'command_off': 'echo 0 > {}'.format(path),
            }
            self.assertTrue(setup_component(self.hass, switch.DOMAIN, {
                'switch': {
                    'platform': 'command_line',
                    'switches': {
                        'test': test_switch
                    }
                }
            }))

            state = self.hass.states.get('switch.test')
            self.assertEqual(STATE_OFF, state.state)

            switch.turn_on(self.hass, 'switch.test')
            self.hass.block_till_done()

            state = self.hass.states.get('switch.test')
            self.assertEqual(STATE_ON, state.state)

            switch.turn_off(self.hass, 'switch.test')
            self.hass.block_till_done()

            state = self.hass.states.get('switch.test')
            self.assertEqual(STATE_OFF, state.state)

    def test_state_value(self):
        """Test with state value."""
        with tempfile.TemporaryDirectory() as tempdirname:
            path = os.path.join(tempdirname, 'switch_status')
            test_switch = {
                'command_state': 'cat {}'.format(path),
                'command_on': 'echo 1 > {}'.format(path),
                'command_off': 'echo 0 > {}'.format(path),
                'value_template': '{{ value=="1" }}'
            }
            self.assertTrue(setup_component(self.hass, switch.DOMAIN, {
                'switch': {
                    'platform': 'command_line',
                    'switches': {
                        'test': test_switch
                    }
                }
            }))

            state = self.hass.states.get('switch.test')
            self.assertEqual(STATE_OFF, state.state)

            switch.turn_on(self.hass, 'switch.test')
            self.hass.block_till_done()

            state = self.hass.states.get('switch.test')
            self.assertEqual(STATE_ON, state.state)

            switch.turn_off(self.hass, 'switch.test')
            self.hass.block_till_done()

            state = self.hass.states.get('switch.test')
            self.assertEqual(STATE_OFF, state.state)

    def test_state_json_value(self):
        """Test with state JSON value."""
        with tempfile.TemporaryDirectory() as tempdirname:
            path = os.path.join(tempdirname, 'switch_status')
            oncmd = json.dumps({'status': 'ok'})
            offcmd = json.dumps({'status': 'nope'})
            test_switch = {
                'command_state': 'cat {}'.format(path),
                'command_on': 'echo \'{}\' > {}'.format(oncmd, path),
                'command_off': 'echo \'{}\' > {}'.format(offcmd, path),
                'value_template': '{{ value_json.status=="ok" }}'
            }
            self.assertTrue(setup_component(self.hass, switch.DOMAIN, {
                'switch': {
                    'platform': 'command_line',
                    'switches': {
                        'test': test_switch
                    }
                }
            }))

            state = self.hass.states.get('switch.test')
            self.assertEqual(STATE_OFF, state.state)

            switch.turn_on(self.hass, 'switch.test')
            self.hass.block_till_done()

            state = self.hass.states.get('switch.test')
            self.assertEqual(STATE_ON, state.state)

            switch.turn_off(self.hass, 'switch.test')
            self.hass.block_till_done()

            state = self.hass.states.get('switch.test')
            self.assertEqual(STATE_OFF, state.state)

    def test_state_code(self):
        """Test with state code."""
        with tempfile.TemporaryDirectory() as tempdirname:
            path = os.path.join(tempdirname, 'switch_status')
            test_switch = {
                'command_state': 'cat {}'.format(path),
                'command_on': 'echo 1 > {}'.format(path),
                'command_off': 'echo 0 > {}'.format(path),
            }
            self.assertTrue(setup_component(self.hass, switch.DOMAIN, {
                'switch': {
                    'platform': 'command_line',
                    'switches': {
                        'test': test_switch
                    }
                }
            }))

            state = self.hass.states.get('switch.test')
            self.assertEqual(STATE_OFF, state.state)

            switch.turn_on(self.hass, 'switch.test')
            self.hass.block_till_done()

            state = self.hass.states.get('switch.test')
            self.assertEqual(STATE_ON, state.state)

            switch.turn_off(self.hass, 'switch.test')
            self.hass.block_till_done()

            state = self.hass.states.get('switch.test')
            self.assertEqual(STATE_ON, state.state)

    def test_assumed_state_should_be_true_if_command_state_is_false(self):
        """Test with state value."""
        self.hass = get_test_home_assistant()

        # Set state command to false
        statecmd = False

        no_state_device = command_line.CommandSwitch(self.hass, "Test", "echo",
                                                     "echo", statecmd, None)
        self.assertTrue(no_state_device.assumed_state)

        # Set state command
        statecmd = 'cat {}'

        state_device = command_line.CommandSwitch(self.hass, "Test", "echo",
                                                  "echo", statecmd, None)
        self.assertFalse(state_device.assumed_state)
