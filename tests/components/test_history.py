"""The tests the History component."""
# pylint: disable=protected-access,too-many-public-methods
from datetime import timedelta
import unittest
from unittest.mock import patch, sentinel

from homeassistant.bootstrap import setup_component
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
            setup_component(self.hass, recorder.DOMAIN, {
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
        self.assertTrue(setup_component(self.hass, history.DOMAIN, {}))

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

        We should get back every thermostat change that
        includes an attribute change, but only the state updates for
        media player (attribute changes are not significant and not returned).
        """
        zero, four, states = self.record_states()
        hist = history.get_significant_states(zero, four)
        assert states == hist

    def test_get_significant_states_enitty_id(self):
        """Test that only significant states are returned for one entity."""
        zero, four, states = self.record_states()
        del states['media_player.test2']
        del states['thermostat.test']
        del states['thermostat.test2']
        del states['script.can_cancel_this_one']

        hist = history.get_significant_states(zero, four, 'media_player.test')
        assert states == hist

    def test_get_significant_states_exclude_domain(self):
        """Test if significant states are returned when excluding domains.

        We should get back every thermostat change that includes an attribute
        change, but no media player changes.
        """
        zero, four, states = self.record_states()
        del states['media_player.test']
        del states['media_player.test2']

        config = history.CONFIG_SCHEMA({
            ha.DOMAIN: {},
            history.DOMAIN: {history.CONF_EXCLUDE: {
                history.CONF_DOMAINS: ['media_player', ]}}})
        self.check_significant_states(zero, four, states, config)

    def test_get_significant_states_exclude_entity(self):
        """Test if significant states are returned when excluding entities.

        We should get back every thermostat and script changes, but no media
        player changes.
        """
        zero, four, states = self.record_states()
        del states['media_player.test']

        config = history.CONFIG_SCHEMA({
            ha.DOMAIN: {},
            history.DOMAIN: {history.CONF_EXCLUDE: {
                history.CONF_ENTITIES: ['media_player.test', ]}}})
        self.check_significant_states(zero, four, states, config)

    def test_get_significant_states_include_domain(self):
        """Test if significant states are returned when including domains.

        We should get back every thermostat and script changes, but no media
        player changes.
        """
        zero, four, states = self.record_states()
        del states['media_player.test']
        del states['media_player.test2']

        config = history.CONFIG_SCHEMA({
            ha.DOMAIN: {},
            history.DOMAIN: {history.CONF_INCLUDE: {
                history.CONF_DOMAINS: ['thermostat', 'script']}}})
        self.check_significant_states(zero, four, states, config)

    def test_get_significant_states_include_entity(self):
        """Test if significant states are returned when excluding domains.

        We should only get back changes of the media_player.test entity.
        """
        zero, four, states = self.record_states()
        del states['media_player.test2']
        del states['thermostat.test']
        del states['thermostat.test2']
        del states['script.can_cancel_this_one']

        config = history.CONFIG_SCHEMA({
            ha.DOMAIN: {},
            history.DOMAIN: {history.CONF_INCLUDE: {
                history.CONF_ENTITIES: ['media_player.test']}}})
        self.check_significant_states(zero, four, states, config)

    def test_get_significant_states_include_exclude_domain(self):
        """Test if significant states are returned when excluding and including
        domains.

        We should not get back any changes since we include only the
        media_player domain but also exclude it.
        """
        zero, four, states = self.record_states()
        del states['media_player.test']
        del states['media_player.test2']
        del states['thermostat.test']
        del states['thermostat.test2']
        del states['script.can_cancel_this_one']

        config = history.CONFIG_SCHEMA({
            ha.DOMAIN: {},
            history.DOMAIN: {history.CONF_INCLUDE: {
                    history.CONF_DOMAINS: ['media_player']},
                history.CONF_EXCLUDE: {
                    history.CONF_DOMAINS: ['media_player']}}})
        self.check_significant_states(zero, four, states, config)

    def test_get_significant_states_include_exclude_entity(self):
        """Test if significant states are returned when excluding and including
        domains.

        We should not get back any changes since we include only
        media_player.test but also exclude it.
        """
        zero, four, states = self.record_states()
        del states['media_player.test']
        del states['media_player.test2']
        del states['thermostat.test']
        del states['thermostat.test2']
        del states['script.can_cancel_this_one']

        config = history.CONFIG_SCHEMA({
            ha.DOMAIN: {},
            history.DOMAIN: {history.CONF_INCLUDE: {
                    history.CONF_ENTITIES: ['media_player.test']},
                history.CONF_EXCLUDE: {
                    history.CONF_ENTITIES: ['media_player.test']}}})
        self.check_significant_states(zero, four, states, config)

    def test_get_significant_states_include_exclude(self):
        """Test if significant states are returned when excluding and including
        domains and entities.

        We should only get back changes of the media_player.test2 entity.
        """
        zero, four, states = self.record_states()
        del states['media_player.test']
        del states['thermostat.test']
        del states['thermostat.test2']
        del states['script.can_cancel_this_one']

        config = history.CONFIG_SCHEMA({
            ha.DOMAIN: {},
            history.DOMAIN: {history.CONF_INCLUDE: {
                    history.CONF_DOMAINS: ['media_player'],
                    history.CONF_ENTITIES: ['thermostat.test']},
                history.CONF_EXCLUDE: {
                    history.CONF_DOMAINS: ['thermostat'],
                    history.CONF_ENTITIES: ['media_player.test']}}})
        self.check_significant_states(zero, four, states, config)

    def check_significant_states(self, zero, four, states, config):
        """Check if significant states are retrieved."""
        filters = history.Filters(config)
        hist = history.get_significant_states(zero, four, filters=filters)
        assert states == hist

    def record_states(self):
        """Record some test states.

        We inject a bunch of state updates from media player, zone and
        thermostat.
        """
        self.init_recorder()
        mp = 'media_player.test'
        mp2 = 'media_player.test2'
        therm = 'thermostat.test'
        therm2 = 'thermostat.test2'
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

        states = {therm: [], therm2: [], mp: [], mp2: [], script_c: []}
        with patch('homeassistant.components.recorder.dt_util.utcnow',
                   return_value=one):
            states[mp].append(
                set_state(mp, 'idle',
                          attributes={'media_title': str(sentinel.mt1)}))
            states[mp].append(
                set_state(mp, 'YouTube',
                          attributes={'media_title': str(sentinel.mt2)}))
            states[mp2].append(
                set_state(mp2, 'YouTube',
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
            states[therm2].append(
                set_state(therm2, 20, attributes={'current_temperature': 19}))

        with patch('homeassistant.components.recorder.dt_util.utcnow',
                   return_value=three):
            states[mp].append(
                set_state(mp, 'Netflix',
                          attributes={'media_title': str(sentinel.mt4)}))
            # Attributes changed even though state is the same
            states[therm].append(
                set_state(therm, 21, attributes={'current_temperature': 20}))
            # state will be skipped since entity is hidden
            set_state(therm, 22, attributes={'current_temperature': 21,
                                             'hidden': True})
        return zero, four, states
