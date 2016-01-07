"""
tests.test_component_librato
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the librato compoment.
"""
# pylint: disable=protected-access,too-many-public-methods
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from tests.common import (mock_state_change_event, fire_time_changed)

import librato

import homeassistant.core as ha
from homeassistant.components import librato as librato_component
from homeassistant.const import STATE_ON
from homeassistant import util
import homeassistant.util.dt as dt_util

class TestComponentsLibrato(unittest.TestCase):
    """ Tests homeassistant.components.librato module. """

    def setUp(self):  # pylint: disable=invalid-name
        """ Init needed objects. """
        self.hass = ha.HomeAssistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_config_validation(self):
        """ Ensure valid configuration is required """
        self.assertFalse(librato_component.setup(self.hass, {'librato': {}}))

    def test_setup(self):
        """ Ensure setup returns True when proper configuration is provided """
        self.assertTrue(librato_component.setup(self.hass, {
                'librato': {
                    'user': 'foo',
                    'token': 'foo'
                }
            }))

    @patch('librato.queue.Queue.add')
    def test_state_submitted(self, mock_librato):
        """ Test that known states are submitted """
        self.assertTrue(librato_component.setup(self.hass, {
                'librato': {
                    'user': 'foo',
                    'token': 'foo'
                }
            }))

        state = ha.State('test.entity',STATE_ON)
        mock_state_change_event(self.hass, state)
        self.hass.pool.block_till_done()
        self.assertEqual(1, mock_librato.call_count)

    @patch('librato.queue.Queue.add')
    def test_attributes_submitted(self, mock_librato):
        """ Test that numerical attributes are parsed and submitted. """
        self.assertTrue(librato_component.setup(self.hass, {
                'librato': {
                    'user': 'foo',
                    'token': 'foo'
                }
            }))

        state = ha.State(
            'test.entity',
            STATE_ON,
            {
                'battery_level': 99,
                'another_floatish': '0.5',
                'string': 'string',
                'auto': 'ignored',
                'node_id': 'also ignored'
            })
        mock_state_change_event(self.hass, state)
        self.hass.pool.block_till_done()
        self.assertEqual(3, mock_librato.call_count)

    @patch('librato.queue.Queue.add')
    def test_periodic_metrics(self, mock_librato):
        self.assertTrue(librato_component.setup(self.hass, {
                'librato': {
                    'user': 'foo',
                    'token': 'foo'
                }
            }))

        state = ha.State(
            'test.entity',
            STATE_ON,
            {
                'battery_level': 99,
                'another_floatish': '0.5',
                'string': 'string',
                'auto': 'ignored',
                'node_id': 'also ignored'
            })
        mock_state_change_event(self.hass, state)
        self.hass.pool.block_till_done()
        self.assertEqual(3, mock_librato.call_count)

        now = dt_util.utcnow()
        for i in range(60):
            future = now + timedelta(seconds=i)
            fire_time_changed(self.hass, future)
            self.hass.pool.block_till_done()

        self.assertEqual(6, mock_librato.call_count)
