"""The tests for the sun automation."""
from datetime import datetime

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


@pytest.fixture
def calls(hass):
    """Track calls to a mock serivce."""
    return async_mock_service(hass, 'test', 'automation')


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, 'group')
    hass.loop.run_until_complete(async_setup_component(hass, sun.DOMAIN, {
            sun.DOMAIN: {sun.CONF_ELEVATION: 0}}))


async def test_sunset_trigger(hass, calls):
    """Test the sunset trigger."""
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
    now = datetime(2015, 9, 13, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 14, tzinfo=dt_util.UTC)

    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'sun',
                    'event': SUN_EVENT_SUNRISE,
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_sunset_trigger_with_offset(hass, calls):
    """Test the sunset trigger with offset."""
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
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 0 == len(calls)

    now = datetime(2015, 9, 16, 10, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)


async def test_if_action_after(hass, calls):
    """Test if action was after."""
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
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 0 == len(calls)

    now = datetime(2015, 9, 16, 15, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)


async def test_if_action_before_with_offset(hass, calls):
    """Test if action was before offset."""
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
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 0 == len(calls)

    now = datetime(2015, 9, 16, 14, 32, 43, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)


async def test_if_action_after_with_offset(hass, calls):
    """Test if action was after offset."""
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
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 0 == len(calls)

    now = datetime(2015, 9, 16, 14, 32, 43, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)


async def test_if_action_before_and_after_during(hass, calls):
    """Test if action was before and after during."""
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
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 0 == len(calls)

    now = datetime(2015, 9, 17, 2, 25, 18, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 0 == len(calls)

    now = datetime(2015, 9, 16, 16, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)
