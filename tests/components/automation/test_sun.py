"""The tests for the sun automation."""
from datetime import datetime
import logging

import pytest
from unittest.mock import patch

from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.setup import async_setup_component
from homeassistant.components import sun
import homeassistant.components.automation as automation
import homeassistant.util.dt as dt_util

from tests.common import (
    async_fire_time_changed, mock_component, async_mock_service)
from tests.components.automation import common

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, 'test', 'automation')


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, 'group')
    dt_util.set_default_time_zone(hass.config.time_zone)
    yield setup_comp
    dt_util.set_default_time_zone(dt_util.get_time_zone('UTC'))


async def fake_time_fire_event_count_calls(hass, now, action_count, calls):
    """Fake time, fire an event and assert number of actions."""
    with patch('homeassistant.util.dt.utcnow', return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert action_count == len(calls)


async def print_sun_states_at_time(hass, now):
    """Fake time and print sun states."""
    with patch('homeassistant.helpers.condition.dt_util.utcnow',
               return_value=now):
        await async_setup_component(hass, sun.DOMAIN, {
            sun.DOMAIN: {sun.CONF_ELEVATION: 0}})
        await hass.async_block_till_done()
        state = hass.states.get(sun.ENTITY_ID)
    _LOGGER.debug("Sun states @%s: %s", now, state)


async def sun_trigger_helper(hass, calls, trigger, times):
    """Test the specified sun trigger."""
    now = times[0]
    trigger_time = times[1]

    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'sun',
                    'event': trigger,
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def action_during_test_helper(hass, calls, period, times):
    """Test if action is during period."""
    await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'condition': {
                'condition': 'sun',
                'during': period,
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    now = times[0][0]
    await print_sun_states_at_time(hass, now)

    for time, expected_calls in times:
        now = time
        await fake_time_fire_event_count_calls(
            hass, now, expected_calls, calls)


async def action_from_until_test_helper(hass, calls, from_, until, times):
    """Test if action is during period."""
    await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'condition': {
                'condition': 'sun',
                'from': from_,
                'until': until,
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    now = times[0][0]
    await print_sun_states_at_time(hass, now)

    for time, expected_calls in times:
        now = time
        await fake_time_fire_event_count_calls(
            hass, now, expected_calls, calls)


async def test_sunset_trigger(hass, calls):
    """Test the sunset trigger."""
    # Sunset at 2015-09-16T01:56:46+00:00
    now = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 2, tzinfo=dt_util.UTC)

    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'sun',
                    'event': SUN_EVENT_SUNSET,
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

    await common.async_turn_off(hass)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert 0 == len(calls)

    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        await common.async_turn_on(hass)
        await hass.async_block_till_done()

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_sunrise_trigger(hass, calls):
    """Test the sunrise trigger."""
    # Sunrise at 2015-09-16T13:32:43+00:00
    init_time = datetime(2015, 9, 16, 13, tzinfo=dt_util.UTC)
    trig_time = datetime(2015, 9, 16, 14, tzinfo=dt_util.UTC)
    await sun_trigger_helper(hass, calls, 'sunrise', [init_time, trig_time])


async def test_astronomical_dawn_trigger(hass, calls):
    """Test the astronomical_dawn trigger."""
    # Astronomical dawn at 2015-09-16T12:09:37+00:00
    init_time = datetime(2015, 9, 16, 12, 9, 0, tzinfo=dt_util.UTC)
    trig_time = datetime(2015, 9, 16, 12, 9, 37, tzinfo=dt_util.UTC)
    await sun_trigger_helper(
        hass, calls, 'astronomical_dawn', [init_time, trig_time])


async def test_astronomical_dusk_trigger(hass, calls):
    """Test the astronomical_dusk trigger."""
    # Astronomical dusk at 2015-09-16T03:19:59+00:00
    init_time = datetime(2015, 9, 16, 3, 19, 0, tzinfo=dt_util.UTC)
    trig_time = datetime(2015, 9, 16, 3, 19, 59, tzinfo=dt_util.UTC)
    await sun_trigger_helper(
        hass, calls, 'astronomical_dusk', [init_time, trig_time])


async def test_civil_dawn_trigger(hass, calls):
    """Test the civil_dawn trigger."""
    # Civil dawn at 2015-09-16T13:07:59+00:00
    init_time = datetime(2015, 9, 16, 13, 7, 0, tzinfo=dt_util.UTC)
    trig_time = datetime(2015, 9, 16, 13, 7, 59, tzinfo=dt_util.UTC)
    await sun_trigger_helper(hass, calls, 'civil_dawn', [init_time, trig_time])


async def test_civil_dusk_trigger(hass, calls):
    """Test the civil_dusk trigger."""
    # Civil dusk at 2015-09-16T02:21:31+00:00
    init_time = datetime(2015, 9, 16, 2, 21, 0, tzinfo=dt_util.UTC)
    trig_time = datetime(2015, 9, 16, 2, 21, 31, tzinfo=dt_util.UTC)
    await sun_trigger_helper(hass, calls, 'civil_dusk', [init_time, trig_time])


async def test_nautical_dawn_trigger(hass, calls):
    """Test the nautical_dawn trigger."""
    # Nautical dawn at 2015-09-16T12:39:01+00:00
    init_time = datetime(2015, 9, 16, 12, 39, 0, tzinfo=dt_util.UTC)
    trig_time = datetime(2015, 9, 16, 12, 39, 1, tzinfo=dt_util.UTC)
    await sun_trigger_helper(
        hass, calls, 'nautical_dawn', [init_time, trig_time])


async def test_nautical_dusk_trigger(hass, calls):
    """Test the nautical_dusk trigger."""
    # Nautical dusk at 2015-09-16T02:50:31+00:00
    init_time = datetime(2015, 9, 16, 2, 50, 0, tzinfo=dt_util.UTC)
    trig_time = datetime(2015, 9, 16, 2, 50, 31, tzinfo=dt_util.UTC)
    await sun_trigger_helper(
        hass, calls, 'nautical_dusk', [init_time, trig_time])


async def test_sunset_trigger_with_offset(hass, calls):
    """Test the sunset trigger with offset."""
    # Sunset at 2015-09-16T01:56:46+00:00
    now = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 2, 30, tzinfo=dt_util.UTC)

    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'sun',
                    'event': SUN_EVENT_SUNSET,
                    'offset': '0:30:00'
                },
                'action': {
                    'service': 'test.automation',
                    'data_template': {
                        'some':
                        '{{ trigger.%s }}' % '}} - {{ trigger.'.join((
                            'platform', 'event', 'offset'))
                    },
                }
            }
        })

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    assert 'sun - sunset - 0:30:00' == calls[0].data['some']


async def test_sunrise_trigger_with_offset(hass, calls):
    """Test the sunrise trigger with offset."""
    # Sunrise at 2015-09-16T13:32:43+00:00
    now = datetime(2015, 9, 13, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 13, 30, tzinfo=dt_util.UTC)

    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'sun',
                    'event': SUN_EVENT_SUNRISE,
                    'offset': '-0:30:00'
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_action_before(hass, calls):
    """Test if action was before."""
    # Sunrise at 2015-09-16T13:32:43+00:00
    await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'condition': {
                'condition': 'sun',
                'before': SUN_EVENT_SUNRISE,
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    now = datetime(2015, 9, 16, 15, tzinfo=dt_util.UTC)
    await fake_time_fire_event_count_calls(hass, now, 0, calls)

    now = datetime(2015, 9, 16, 10, tzinfo=dt_util.UTC)
    await fake_time_fire_event_count_calls(hass, now, 1, calls)


async def test_if_action_from_sunrise_until_nautical_dusk(hass, calls):
    """Test if action is during day."""
    # Sunrise at 2015-09-16T13:32:43+00:00
    # Nautical dusk at 2015-09-17T02:49:06+00:00
    times = [
        (datetime(2015, 9, 16, 3, tzinfo=dt_util.UTC), 0),
        (datetime(2015, 9, 16, 13, 32, 42, tzinfo=dt_util.UTC), 0),
        (datetime(2015, 9, 16, 13, 32, 43, tzinfo=dt_util.UTC), 1),
        (datetime(2015, 9, 17, 2, 49, 5, tzinfo=dt_util.UTC), 2),
        (datetime(2015, 9, 17, 2, 49, 6, tzinfo=dt_util.UTC), 2),
    ]
    from_ = 'sunrise'
    until = 'nautical_dusk'
    await action_from_until_test_helper(hass, calls, from_, until, times)


async def test_if_action_after(hass, calls):
    """Test if action was after."""
    # Sunrise at 2015-09-16T13:32:43+00:00
    await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'condition': {
                'condition': 'sun',
                'after': SUN_EVENT_SUNRISE,
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    now = datetime(2015, 9, 16, 13, tzinfo=dt_util.UTC)
    await fake_time_fire_event_count_calls(hass, now, 0, calls)

    now = datetime(2015, 9, 16, 15, tzinfo=dt_util.UTC)
    await fake_time_fire_event_count_calls(hass, now, 1, calls)


async def test_if_action_before_with_offset(hass, calls):
    """Test if action was before offset."""
    # Sunrise at 2015-09-16T13:32:43+00:00
    await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'condition': {
                'condition': 'sun',
                'before': SUN_EVENT_SUNRISE,
                'before_offset': '+1:00:00'
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    now = datetime(2015, 9, 16, 14, 32, 44, tzinfo=dt_util.UTC)
    await fake_time_fire_event_count_calls(hass, now, 0, calls)

    now = datetime(2015, 9, 16, 14, 32, 43, tzinfo=dt_util.UTC)
    await fake_time_fire_event_count_calls(hass, now, 1, calls)


async def test_if_action_after_with_offset(hass, calls):
    """Test if action was after offset."""
    # Sunrise at 2015-09-16T13:32:43+00:00
    await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'condition': {
                'condition': 'sun',
                'after': SUN_EVENT_SUNRISE,
                'after_offset': '+1:00:00'
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    now = datetime(2015, 9, 16, 14, 32, 42, tzinfo=dt_util.UTC)
    await fake_time_fire_event_count_calls(hass, now, 0, calls)

    now = datetime(2015, 9, 16, 14, 32, 43, tzinfo=dt_util.UTC)
    await fake_time_fire_event_count_calls(hass, now, 1, calls)


async def test_if_action_before_and_after_during(hass, calls):
    """Test if action was before and after during."""
    # Sunset at 2015-09-16T01:56:46+00:00
    await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'condition': {
                'condition': 'sun',
                'after': SUN_EVENT_SUNRISE,
                'before': SUN_EVENT_SUNSET
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    now = datetime(2015, 9, 16, 13, 8, 51, tzinfo=dt_util.UTC)
    await fake_time_fire_event_count_calls(hass, now, 0, calls)

    now = datetime(2015, 9, 17, 2, 25, 18, tzinfo=dt_util.UTC)
    await fake_time_fire_event_count_calls(hass, now, 0, calls)

    now = datetime(2015, 9, 16, 16, tzinfo=dt_util.UTC)
    await fake_time_fire_event_count_calls(hass, now, 1, calls)
