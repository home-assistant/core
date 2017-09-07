"""Tests for the Input slider component."""
# pylint: disable=protected-access
import asyncio
import unittest
import datetime

from homeassistant.core import CoreState, State
from homeassistant.setup import setup_component, async_setup_component
from homeassistant.components.input_datetime import (DOMAIN, set_datetime)

from tests.common import get_test_home_assistant, mock_restore_cache


class TestInputDatetime(unittest.TestCase):
    """Test the input datetime component."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_invalid_configs(self):
        """Test config."""
        invalid_configs = [
            None,
            {},
            {'name with space': None},
            {'test_no_value': {
                'has_time': False,
                'has_date': False
            }},
        ]
        for cfg in invalid_configs:
            self.assertFalse(
                setup_component(self.hass, DOMAIN, {DOMAIN: cfg}))

    def test_set_datetime(self):
        """Test set_datetime method."""
        self.assertTrue(setup_component(self.hass, DOMAIN, {DOMAIN: {
            'test_datetime': {
                'has_date': True,
                'has_time': True,
            },
        }}))
        entity_id = 'input_datetime.test_datetime'

        dt_obj = datetime.datetime(2017, 9, 7, 19, 46)

        set_datetime(self.hass, entity_id, dt_obj)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual(state.state, str(dt_obj))
        self.assertTrue(state.attributes['has_time'])
        self.assertTrue(state.attributes['has_date'])

    def test_set_datetime_time(self):
        """Test set_datetime method with only time."""
        self.assertTrue(setup_component(self.hass, DOMAIN, {DOMAIN: {
            'test_time': {
                'has_date': False,
                'has_time': True,
            },
        }}))
        entity_id = 'input_datetime.test_time'

        dt_obj = datetime.datetime(2017, 9, 7, 19, 46)
        time_portion = dt_obj.time()

        set_datetime(self.hass, entity_id, dt_obj)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual(state.state, str(time_portion))
        self.assertTrue(state.attributes['has_time'])
        self.assertFalse(state.attributes['has_date'])

    def test_set_datetime_date(self):
        """Test set_datetime method with only date."""
        self.assertTrue(setup_component(self.hass, DOMAIN, {DOMAIN: {
            'test_date': {
                'has_date': True,
                'has_time': False,
            },
        }}))
        entity_id = 'input_datetime.test_date'

        dt_obj = datetime.datetime(2017, 9, 7, 19, 46)
        date_portion = dt_obj.date()

        set_datetime(self.hass, entity_id, dt_obj)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual(state.state, str(date_portion))
        self.assertFalse(state.attributes['has_time'])
        self.assertTrue(state.attributes['has_date'])

@asyncio.coroutine
def test_restore_state(hass):
    """Ensure states are restored on startup."""
    mock_restore_cache(hass, (
        State('input_datetime.test_time', '2017-09-07 19:46:00'),
        State('input_datetime.test_date', '2017-09-07 19:46:00'),
        State('input_datetime.test_datetime', '2017-09-07 19:46:00'),
    ))

    hass.state = CoreState.starting

    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            'test_time': {
                'has_time': True,
                'has_date': False
            },
            'test_date': {
                'has_time': False,
                'has_date': True
            },
            'test_datetime': {
                'has_time': True,
                'has_date': True
            },
        }})

    dt_obj = datetime.datetime(2017, 9, 7, 19, 46)

    state_time = hass.states.get('input_datetime.test_time')
    assert state_time.state == str(dt_obj.time())

    state_date = hass.states.get('input_datetime.test_date')
    assert state_date.state == str(dt_obj.date())

    state_datetime = hass.states.get('input_datetime.test_datetime')
    assert state_datetime.state == str(dt_obj)
