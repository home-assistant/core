"""The tests the History component."""
# pylint: disable=protected-access,too-many-public-methods
from datetime import timedelta
import unittest
from unittest.mock import patch, sentinel

import homeassistant.core as ha
import homeassistant.util.dt as dt_util
from homeassistant.components import history, recorder

from tests.common import (
    mock_http_component, mock_state_change_event, get_test_home_assistant)


class TestComponentHistory(unittest.TestCase):
    """Test History component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def init_recorder(self):
        """Initialize the recorder."""
        db_uri = 'sqlite://'
        with patch('homeassistant.core.Config.path', return_value=db_uri):
            recorder.setup(self.hass, config={
                "recorder": {
                    "db_url": db_uri}})
        self.hass.start()
        recorder._INSTANCE.block_till_db_ready()
        self.wait_recording_done()

    def wait_recording_done(self):
        """Block till recording is done."""
        self.hass.block_till_done()
        recorder._INSTANCE.block_till_done()

    def test_setup(self):
        """Test setup method of history."""
        mock_http_component(self.hass)
        self.assertTrue(history.setup(self.hass, {}))

    def test_last_5_states(self):
        """Test retrieving the last 5 states."""
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
        """Test getting states at a specific point in time."""
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
        """Test state change during period."""
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

    def test_get_significant_states(self):
        """Test that only significant states are returned.

        We inject a bunch of state updates from media player, zone and
        thermostat. We should get back every thermostat change that
        includes an attribute change, but only the state updates for
        media player (attribute changes are not significant and not returned).
        """
        self.init_recorder()
        mp = 'media_player.test'
        therm = 'thermostat.test'
        zone = 'zone.home'
        script_nc = 'script.cannot_cancel_this_one'
        script_c = 'script.can_cancel_this_one'

        def set_state(entity_id, state, **kwargs):
            self.hass.states.set(entity_id, state, **kwargs)
            self.wait_recording_done()
            return self.hass.states.get(entity_id)

        zero = dt_util.utcnow()
        one = zero + timedelta(seconds=1)
        two = one + timedelta(seconds=1)
        three = two + timedelta(seconds=1)
        four = three + timedelta(seconds=1)

        states = {therm: [], mp: [], script_c: []}
        with patch('homeassistant.components.recorder.dt_util.utcnow',
                   return_value=one):
            states[mp].append(
                set_state(mp, 'idle',
                          attributes={'media_title': str(sentinel.mt1)}))
            states[mp].append(
                set_state(mp, 'YouTube',
                          attributes={'media_title': str(sentinel.mt2)}))
            states[therm].append(
                set_state(therm, 20, attributes={'current_temperature': 19.5}))

        with patch('homeassistant.components.recorder.dt_util.utcnow',
                   return_value=two):
            # This state will be skipped only different in time
            set_state(mp, 'YouTube',
                      attributes={'media_title': str(sentinel.mt3)})
            # This state will be skipped because domain blacklisted
            set_state(zone, 'zoning')
            set_state(script_nc, 'off')
            states[script_c].append(
                set_state(script_c, 'off', attributes={'can_cancel': True}))
            states[therm].append(
                set_state(therm, 21, attributes={'current_temperature': 19.8}))

        with patch('homeassistant.components.recorder.dt_util.utcnow',
                   return_value=three):
            states[mp].append(
                set_state(mp, 'Netflix',
                          attributes={'media_title': str(sentinel.mt4)}))
            # Attributes changed even though state is the same
            states[therm].append(
                set_state(therm, 21, attributes={'current_temperature': 20}))

        hist = history.get_significant_states(zero, four)
        assert states == hist
