"""
tests.test_component_history
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the history component.
"""
# pylint: disable=protected-access,too-many-public-methods
from datetime import timedelta
import os
import unittest
from unittest.mock import patch

import homeassistant.core as ha
import homeassistant.util.dt as dt_util
from homeassistant.components import history, recorder

from tests.common import (
    mock_http_component, mock_state_change_event, get_test_home_assistant)


class TestComponentHistory(unittest.TestCase):
    """ Tests homeassistant.components.history module. """

    def setUp(self):  # pylint: disable=invalid-name
        """ Init needed objects. """
        self.hass = get_test_home_assistant(1)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

        db_path = self.hass.config.path(recorder.DB_FILE)
        if os.path.isfile(db_path):
            os.remove(db_path)

    def init_recorder(self):
        recorder.setup(self.hass, {})
        self.hass.start()
        self.wait_recording_done()

    def wait_recording_done(self):
        """ Block till recording is done. """
        self.hass.pool.block_till_done()
        recorder._INSTANCE.block_till_done()

    def test_setup(self):
        """ Test setup method of history. """
        mock_http_component(self.hass)
        self.assertTrue(history.setup(self.hass, {}))

    def test_last_5_states(self):
        """ Test retrieving the last 5 states. """
        self.init_recorder()
        states = []

        entity_id = 'test.last_5_states'

        for i in range(7):
            self.hass.states.set(entity_id, "State {}".format(i))

            self.wait_recording_done()

            if i > 1:
                states.append(self.hass.states.get(entity_id))

        self.assertEqual(
            list(reversed(states)), history.last_5_states(entity_id))

    def test_get_states(self):
        """ Test getting states at a specific point in time. """
        self.init_recorder()
        states = []

        now = dt_util.utcnow()
        with patch('homeassistant.components.recorder.dt_util.utcnow',
                   return_value=now):
            for i in range(5):
                state = ha.State(
                    'test.point_in_time_{}'.format(i % 5),
                    "State {}".format(i),
                    {'attribute_test': i})

                mock_state_change_event(self.hass, state)

                states.append(state)

            self.wait_recording_done()

        future = now + timedelta(seconds=1)
        with patch('homeassistant.components.recorder.dt_util.utcnow',
                   return_value=future):
            for i in range(5):
                state = ha.State(
                    'test.point_in_time_{}'.format(i % 5),
                    "State {}".format(i),
                    {'attribute_test': i})

                mock_state_change_event(self.hass, state)

            self.wait_recording_done()

        # Get states returns everything before POINT
        self.assertEqual(states,
                         sorted(history.get_states(future),
                                key=lambda state: state.entity_id))

        # Test get_state here because we have a DB setup
        self.assertEqual(
            states[0], history.get_state(future, states[0].entity_id))

    def test_state_changes_during_period(self):
        self.init_recorder()
        entity_id = 'media_player.test'

        def set_state(state):
            self.hass.states.set(entity_id, state)
            self.wait_recording_done()
            return self.hass.states.get(entity_id)

        start = dt_util.utcnow()
        point = start + timedelta(seconds=1)
        end = point + timedelta(seconds=1)

        with patch('homeassistant.components.recorder.dt_util.utcnow',
                   return_value=start):
            set_state('idle')
            set_state('YouTube')

        with patch('homeassistant.components.recorder.dt_util.utcnow',
                   return_value=point):
            states = [
                set_state('idle'),
                set_state('Netflix'),
                set_state('Plex'),
                set_state('YouTube'),
            ]

        with patch('homeassistant.components.recorder.dt_util.utcnow',
                   return_value=end):
            set_state('Netflix')
            set_state('Plex')

        hist = history.state_changes_during_period(start, end, entity_id)

        self.assertEqual(states, hist[entity_id])
