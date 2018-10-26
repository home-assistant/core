"""The tests for the time automation."""
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
import homeassistant.components.automation as automation

from tests.common import (
    async_fire_time_changed, assert_setup_component, mock_component)
from tests.components.automation import common
from tests.common import async_mock_service


@pytest.fixture
def calls(hass):
    """Track calls to a mock serivce."""
    return async_mock_service(hass, 'test', 'automation')


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, 'group')


async def test_if_fires_when_hour_matches(hass, calls):
    """Test for firing if hour is matching."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'time',
                'hours': 0,
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    async_fire_time_changed(hass, dt_util.utcnow().replace(hour=0))
    await hass.async_block_till_done()
    assert 1 == len(calls)

    await common.async_turn_off(hass)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow().replace(hour=0))
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_fires_when_minute_matches(hass, calls):
    """Test for firing if minutes are matching."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'time',
                'minutes': 0,
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    async_fire_time_changed(hass, dt_util.utcnow().replace(minute=0))

    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_fires_when_second_matches(hass, calls):
    """Test for firing if seconds are matching."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'time',
                'seconds': 0,
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    async_fire_time_changed(hass, dt_util.utcnow().replace(second=0))

    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_fires_when_all_matches(hass, calls):
    """Test for firing if everything matches."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'time',
                'hours': 1,
                'minutes': 2,
                'seconds': 3,
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    async_fire_time_changed(hass, dt_util.utcnow().replace(
        hour=1, minute=2, second=3))

    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_fires_periodic_seconds(hass, calls):
    """Test for firing periodically every second."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'time',
                'seconds': "/2",
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    async_fire_time_changed(hass, dt_util.utcnow().replace(
        hour=0, minute=0, second=2))

    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_fires_periodic_minutes(hass, calls):
    """Test for firing periodically every minute."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'time',
                'minutes': "/2",
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    async_fire_time_changed(hass, dt_util.utcnow().replace(
        hour=0, minute=2, second=0))

    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_fires_periodic_hours(hass, calls):
    """Test for firing periodically every hour."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'time',
                'hours': "/2",
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    async_fire_time_changed(hass, dt_util.utcnow().replace(
        hour=2, minute=0, second=0))

    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_fires_using_at(hass, calls):
    """Test for firing at."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'time',
                'at': '5:00:00',
            },
            'action': {
                'service': 'test.automation',
                'data_template': {
                    'some': '{{ trigger.platform }} - '
                            '{{ trigger.now.hour }}'
                },
            }
        }
    })

    async_fire_time_changed(hass, dt_util.utcnow().replace(
        hour=5, minute=0, second=0))

    await hass.async_block_till_done()
    assert 1 == len(calls)
    assert 'time - 5' == calls[0].data['some']


async def test_if_not_working_if_no_values_in_conf_provided(hass, calls):
    """Test for failure if no configuration."""
    with assert_setup_component(0):
        assert await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'time',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

    async_fire_time_changed(hass, dt_util.utcnow().replace(
        hour=5, minute=0, second=0))

    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_if_not_fires_using_wrong_at(hass, calls):
    """YAML translates time values to total seconds.

    This should break the before rule.
    """
    with assert_setup_component(0):
        assert await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'time',
                    'at': 3605,
                    # Total seconds. Hour = 3600 second
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

    async_fire_time_changed(hass, dt_util.utcnow().replace(
        hour=1, minute=0, second=5))

    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_if_action_before(hass, calls):
    """Test for if action before."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event'
            },
            'condition': {
                'condition': 'time',
                'before': '10:00',
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    before_10 = dt_util.now().replace(hour=8)
    after_10 = dt_util.now().replace(hour=14)

    with patch('homeassistant.helpers.condition.dt_util.now',
               return_value=before_10):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()

    assert 1 == len(calls)

    with patch('homeassistant.helpers.condition.dt_util.now',
               return_value=after_10):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()

    assert 1 == len(calls)


async def test_if_action_after(hass, calls):
    """Test for if action after."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event'
            },
            'condition': {
                'condition': 'time',
                'after': '10:00',
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    before_10 = dt_util.now().replace(hour=8)
    after_10 = dt_util.now().replace(hour=14)

    with patch('homeassistant.helpers.condition.dt_util.now',
               return_value=before_10):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()

    assert 0 == len(calls)

    with patch('homeassistant.helpers.condition.dt_util.now',
               return_value=after_10):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()

    assert 1 == len(calls)


async def test_if_action_one_weekday(hass, calls):
    """Test for if action with one weekday."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event'
            },
            'condition': {
                'condition': 'time',
                'weekday': 'mon',
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    days_past_monday = dt_util.now().weekday()
    monday = dt_util.now() - timedelta(days=days_past_monday)
    tuesday = monday + timedelta(days=1)

    with patch('homeassistant.helpers.condition.dt_util.now',
               return_value=monday):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()

    assert 1 == len(calls)

    with patch('homeassistant.helpers.condition.dt_util.now',
               return_value=tuesday):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()

    assert 1 == len(calls)


async def test_if_action_list_weekday(hass, calls):
    """Test for action with a list of weekdays."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event'
            },
            'condition': {
                'condition': 'time',
                'weekday': ['mon', 'tue'],
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    days_past_monday = dt_util.now().weekday()
    monday = dt_util.now() - timedelta(days=days_past_monday)
    tuesday = monday + timedelta(days=1)
    wednesday = tuesday + timedelta(days=1)

    with patch('homeassistant.helpers.condition.dt_util.now',
               return_value=monday):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()

    assert 1 == len(calls)

    with patch('homeassistant.helpers.condition.dt_util.now',
               return_value=tuesday):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()

    assert 2 == len(calls)

    with patch('homeassistant.helpers.condition.dt_util.now',
               return_value=wednesday):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()

    assert 2 == len(calls)
