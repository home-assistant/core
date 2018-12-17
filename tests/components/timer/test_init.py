"""The tests for the timer component."""
# pylint: disable=protected-access
import asyncio
import logging
from datetime import timedelta

from homeassistant.core import CoreState
from homeassistant.setup import async_setup_component
from homeassistant.components.timer import (
    DOMAIN, CONF_DURATION, CONF_NAME, STATUS_ACTIVE, STATUS_IDLE,
    STATUS_PAUSED, CONF_ICON, ATTR_DURATION, EVENT_TIMER_FINISHED,
    EVENT_TIMER_CANCELLED, SERVICE_START, SERVICE_PAUSE, SERVICE_CANCEL,
    SERVICE_FINISH)
from homeassistant.const import (ATTR_ICON, ATTR_FRIENDLY_NAME, CONF_ENTITY_ID)
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


async def test_config(hass):
    """Test config."""
    invalid_configs = [
        None,
        1,
        {},
        {'name with space': None},
    ]

    for cfg in invalid_configs:
        assert not await async_setup_component(hass, DOMAIN, {DOMAIN: cfg})


async def test_config_options(hass):
    """Test configuration options."""
    count_start = len(hass.states.async_entity_ids())

    _LOGGER.debug('ENTITIES @ start: %s', hass.states.async_entity_ids())

    config = {
        DOMAIN: {
            'test_1': {},
            'test_2': {
                CONF_NAME: 'Hello World',
                CONF_ICON: 'mdi:work',
                CONF_DURATION: 10,
            }
        }
    }

    assert await async_setup_component(hass, 'timer', config)
    await hass.async_block_till_done()

    assert count_start + 2 == len(hass.states.async_entity_ids())
    await hass.async_block_till_done()

    state_1 = hass.states.get('timer.test_1')
    state_2 = hass.states.get('timer.test_2')

    assert state_1 is not None
    assert state_2 is not None

    assert STATUS_IDLE == state_1.state
    assert ATTR_ICON not in state_1.attributes
    assert ATTR_FRIENDLY_NAME not in state_1.attributes

    assert STATUS_IDLE == state_2.state
    assert 'Hello World' == \
        state_2.attributes.get(ATTR_FRIENDLY_NAME)
    assert 'mdi:work' == state_2.attributes.get(ATTR_ICON)
    assert '0:00:10' == state_2.attributes.get(ATTR_DURATION)


@asyncio.coroutine
def test_methods_and_events(hass):
    """Test methods and events."""
    hass.state = CoreState.starting

    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            'test1': {
                CONF_DURATION: 10,
            }
        }})

    state = hass.states.get('timer.test1')
    assert state
    assert state.state == STATUS_IDLE

    results = []

    def fake_event_listener(event):
        """Fake event listener for trigger."""
        results.append(event)

    hass.bus.async_listen(EVENT_TIMER_FINISHED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_CANCELLED, fake_event_listener)

    yield from hass.services.async_call(DOMAIN,
                                        SERVICE_START,
                                        {CONF_ENTITY_ID: 'timer.test1'})
    yield from hass.async_block_till_done()

    state = hass.states.get('timer.test1')
    assert state
    assert state.state == STATUS_ACTIVE

    yield from hass.services.async_call(DOMAIN,
                                        SERVICE_PAUSE,
                                        {CONF_ENTITY_ID: 'timer.test1'})
    yield from hass.async_block_till_done()

    state = hass.states.get('timer.test1')
    assert state
    assert state.state == STATUS_PAUSED

    yield from hass.services.async_call(DOMAIN,
                                        SERVICE_CANCEL,
                                        {CONF_ENTITY_ID: 'timer.test1'})
    yield from hass.async_block_till_done()

    state = hass.states.get('timer.test1')
    assert state
    assert state.state == STATUS_IDLE

    assert len(results) == 1
    assert results[-1].event_type == EVENT_TIMER_CANCELLED

    yield from hass.services.async_call(DOMAIN,
                                        SERVICE_START,
                                        {CONF_ENTITY_ID: 'timer.test1'})
    yield from hass.async_block_till_done()

    state = hass.states.get('timer.test1')
    assert state
    assert state.state == STATUS_ACTIVE

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    yield from hass.async_block_till_done()

    state = hass.states.get('timer.test1')
    assert state
    assert state.state == STATUS_IDLE

    assert len(results) == 2
    assert results[-1].event_type == EVENT_TIMER_FINISHED

    yield from hass.services.async_call(DOMAIN,
                                        SERVICE_START,
                                        {CONF_ENTITY_ID: 'timer.test1'})
    yield from hass.async_block_till_done()

    state = hass.states.get('timer.test1')
    assert state
    assert state.state == STATUS_ACTIVE

    yield from hass.services.async_call(DOMAIN,
                                        SERVICE_FINISH,
                                        {CONF_ENTITY_ID: 'timer.test1'})
    yield from hass.async_block_till_done()

    state = hass.states.get('timer.test1')
    assert state
    assert state.state == STATUS_IDLE

    assert len(results) == 3
    assert results[-1].event_type == EVENT_TIMER_FINISHED


@asyncio.coroutine
def test_no_initial_state_and_no_restore_state(hass):
    """Ensure that entity is create without initial and restore feature."""
    hass.state = CoreState.starting

    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            'test1': {
                CONF_DURATION: 10,
            }
        }})

    state = hass.states.get('timer.test1')
    assert state
    assert state.state == STATUS_IDLE
