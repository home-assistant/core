"""
tests.components.rollershutter.command_rollershutter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests the command_rollershutter component
"""

import os
import tempfile
import unittest
from unittest import mock

import homeassistant.core as ha
import homeassistant.components.rollershutter as rollershutter
from homeassistant.components.rollershutter import (
    command_rollershutter as cmd_rs)

class TestCommandRollerShutter(unittest.TestCase):
    def setup_method(self, method):
        self.hass = ha.HomeAssistant()
        self.hass.config.latitude = 32.87336
        self.hass.config.longitude = 117.22743
        self.rs = cmd_rs.CommandRollershutter(self.hass, 'foo',
                                              'cmd_up', 'cmd_dn',
                                              'cmd_stop', 'cmd_state',
                                              None)  # FIXME

    def teardown_method(self, method):
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_should_poll(self):
        self.assertTrue(self.rs.should_poll)
        self.rs._command_state = None
        self.assertFalse(self.rs.should_poll)

    def test_query_state_value(self):
        with mock.patch('subprocess.check_output') as mock_run:
            mock_run.return_value = b' foo bar '
            result = self.rs._query_state_value('runme')
            self.assertEqual('foo bar', result)
            mock_run.assert_called_once_with('runme', shell=True)

    def test_state_attributes_current_position(self):
        # self.assertTrue(rollershutter.setup(self.hass, {
        add_devices = mock.MagicMock()
        self.assertTrue(cmd_rs.setup_platform(self.hass, {
            'rollershutter': {
                'platform': 'command_rollershutter',
                'name': 'test',
                'upcmd': 'up-cmd',
                'downcmd': 'down-cmd',
                'stopcmd': 'stop-cmd',
                'statecmd': 'state-cmd'
            }
        # }))
        }, add_devices))

        state_attributes_dict = self.hass.states.get(
            'rollershutter.test').attributes
        self.assertFalse('current_position' in state_attributes_dict)

        # fire_mqtt_message(self.hass, 'state-topic', '0')
        fire_state_changed(self.hass, 'state-cmd', '0')
        self.hass.pool.block_till_done()
        current_position = self.hass.states.get(
            'rollershutter.test').attributes['current_position']
        self.assertEqual(0, current_position)

        # fire_mqtt_message(self.hass, 'state-topic', '50')
        fire_state_changed(self.hass, 'state-cmd', '50')
        self.hass.pool.block_till_done()
        current_position = self.hass.states.get(
            'rollershutter.test').attributes['current_position']
        self.assertEqual(50, current_position)

        # fire_mqtt_message(self.hass, 'state-topic', '101')
        fire_state_changed(self.hass, 'state-cmd', '101')
        self.hass.pool.block_till_done()
        current_position = self.hass.states.get(
            'rollershutter.test').attributes['current_position']
        self.assertEqual(50, current_position)

        # fire_mqtt_message(self.hass, 'state-topic', 'non-numeric')
        fire_state_changed(self.hass, 'state-cmd', 'non-numeric')
        self.hass.pool.block_till_done()
        current_position = self.hass.states.get(
            'rollershutter.test').attributes['current_position']
        self.assertEqual(50, current_position)

    def test_state_value(self):
        add_devices = mock.MagicMock()
        with tempfile.TemporaryDirectory() as tempdirname:
            path = os.path.join(tempdirname, 'rollershutter_status')
            test_rollershutter = {
                'statecmd': 'cat {}'.format(path),
                'upcmd': 'echo 1 > {}'.format(path),
                'downcmd': 'echo 1 > {}'.format(path),
                'stopcmd': 'echo 0 > {}'.format(path),
                'value_template': '{{ value }}'
            }
#            self.assertTrue(rollershutter.setup(self.hass, {
            self.assertTrue(cmd_rs.setup_platform(self.hass, {
                'rollershutter': {
                    'platform': 'command_rollershutter',
                    'rollershutters': {
                        'test': test_rollershutter
                    }
                }
#            }))
            }, add_devices))

            state = self.hass.states.get('rollershutter.test')
            self.assertEqual('closed', state.state)

            rollershutter.move_up(self.hass, 'rollershutter.test')
            self.hass.pool.block_till_done()

            state = self.hass.states.get('rollershutter.test')
            self.assertEqual('open', state.state)

            rollershutter.move_down(self.hass, 'rollershutter.test')
            self.hass.pool.block_till_done()

            state = self.hass.states.get('rollershutter.test')
            self.assertEqual('open', state.state)

            rollershutter.stop(self.hass, 'rollershutter.test')
            self.hass.pool.block_till_done()

            state = self.hass.states.get('rollershutter.test')
            self.assertEqual('closed', state.state)


