"""Tests for the Input slider component."""
# pylint: disable=protected-access
import asyncio
import unittest
import datetime

from homeassistant.core import CoreState, State, Context
from homeassistant.setup import setup_component, async_setup_component
from homeassistant.components.input_datetime import (
    DOMAIN, ATTR_ENTITY_ID, ATTR_DATE, ATTR_TIME, SERVICE_SET_DATETIME)

from tests.common import get_test_home_assistant, mock_restore_cache


async def async_set_datetime(hass, entity_id, dt_value):
    """Set date and / or time of input_datetime."""
    await hass.services.async_call(DOMAIN, SERVICE_SET_DATETIME, {
        ATTR_ENTITY_ID: entity_id,
        ATTR_DATE: dt_value.date(),
        ATTR_TIME: dt_value.time()
    }, blocking=True)


class TestInputDatetime(unittest.TestCase):
    """Test the input datetime component."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
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
            assert not setup_component(self.hass, DOMAIN, {DOMAIN: cfg})


@asyncio.coroutine
def test_set_datetime(hass):
    """Test set_datetime method."""
    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            'test_datetime': {
                'has_time': True,
                'has_date': True
            },
        }})

    entity_id = 'input_datetime.test_datetime'

    dt_obj = datetime.datetime(2017, 9, 7, 19, 46)

    yield from async_set_datetime(hass, entity_id, dt_obj)

    state = hass.states.get(entity_id)
    assert state.state == str(dt_obj)
    assert state.attributes['has_time']
    assert state.attributes['has_date']

    assert state.attributes['year'] == 2017
    assert state.attributes['month'] == 9
    assert state.attributes['day'] == 7
    assert state.attributes['hour'] == 19
    assert state.attributes['minute'] == 46
    assert state.attributes['timestamp'] == dt_obj.timestamp()


@asyncio.coroutine
def test_set_datetime_time(hass):
    """Test set_datetime method with only time."""
    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            'test_time': {
                'has_time': True,
                'has_date': False
            }
        }})

    entity_id = 'input_datetime.test_time'

    dt_obj = datetime.datetime(2017, 9, 7, 19, 46)
    time_portion = dt_obj.time()

    yield from async_set_datetime(hass, entity_id, dt_obj)

    state = hass.states.get(entity_id)
    assert state.state == str(time_portion)
    assert state.attributes['has_time']
    assert not state.attributes['has_date']

    assert state.attributes['timestamp'] == (19 * 3600) + (46 * 60)


@asyncio.coroutine
def test_set_invalid(hass):
    """Test set_datetime method with only time."""
    initial = '2017-01-01'
    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            'test_date': {
                'has_time': False,
                'has_date': True,
                'initial': initial
            }
        }})

    entity_id = 'input_datetime.test_date'

    dt_obj = datetime.datetime(2017, 9, 7, 19, 46)
    time_portion = dt_obj.time()

    yield from hass.services.async_call('input_datetime', 'set_datetime', {
        'entity_id': 'test_date',
        'time': time_portion
    })
    yield from hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == initial


@asyncio.coroutine
def test_set_datetime_date(hass):
    """Test set_datetime method with only date."""
    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            'test_date': {
                'has_time': False,
                'has_date': True
            }
        }})

    entity_id = 'input_datetime.test_date'

    dt_obj = datetime.datetime(2017, 9, 7, 19, 46)
    date_portion = dt_obj.date()

    yield from async_set_datetime(hass, entity_id, dt_obj)

    state = hass.states.get(entity_id)
    assert state.state == str(date_portion)
    assert not state.attributes['has_time']
    assert state.attributes['has_date']

    date_dt_obj = datetime.datetime(2017, 9, 7)
    assert state.attributes['timestamp'] == date_dt_obj.timestamp()


@asyncio.coroutine
def test_restore_state(hass):
    """Ensure states are restored on startup."""
    mock_restore_cache(hass, (
        State('input_datetime.test_time', '19:46:00'),
        State('input_datetime.test_date', '2017-09-07'),
        State('input_datetime.test_datetime', '2017-09-07 19:46:00'),
        State('input_datetime.test_bogus_data', 'this is not a date'),
    ))

    hass.state = CoreState.starting

    initial = datetime.datetime(2017, 1, 1, 23, 42)

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
            'test_bogus_data': {
                'has_time': True,
                'has_date': True,
                'initial': str(initial)
            },
        }})

    dt_obj = datetime.datetime(2017, 9, 7, 19, 46)
    state_time = hass.states.get('input_datetime.test_time')
    assert state_time.state == str(dt_obj.time())

    state_date = hass.states.get('input_datetime.test_date')
    assert state_date.state == str(dt_obj.date())

    state_datetime = hass.states.get('input_datetime.test_datetime')
    assert state_datetime.state == str(dt_obj)

    state_bogus = hass.states.get('input_datetime.test_bogus_data')
    assert state_bogus.state == str(initial)


async def test_input_datetime_context(hass):
    """Test that input_datetime context works."""
    assert await async_setup_component(hass, 'input_datetime', {
        'input_datetime': {
            'only_date': {
                'has_date': True,
            }
        }
    })

    state = hass.states.get('input_datetime.only_date')
    assert state is not None

    await hass.services.async_call('input_datetime', 'set_datetime', {
        'entity_id': state.entity_id,
        'date': '2018-01-02'
    }, True, Context(user_id='abcd'))

    state2 = hass.states.get('input_datetime.only_date')
    assert state2 is not None
    assert state.state != state2.state
    assert state2.context.user_id == 'abcd'
