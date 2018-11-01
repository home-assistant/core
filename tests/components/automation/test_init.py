"""The tests for the automation component."""
import asyncio
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.core import State, CoreState
from homeassistant.setup import async_setup_component
import homeassistant.components.automation as automation
from homeassistant.const import (
    ATTR_ENTITY_ID, STATE_ON, STATE_OFF, EVENT_HOMEASSISTANT_START)
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.dt as dt_util

from tests.common import (
    assert_setup_component, async_fire_time_changed,
    mock_restore_cache, async_mock_service)
from tests.components.automation import common


@pytest.fixture
def calls(hass):
    """Track calls to a mock serivce."""
    return async_mock_service(hass, 'test', 'automation')


async def test_service_data_not_a_dict(hass, calls):
    """Test service data not dict."""
    with assert_setup_component(0, automation.DOMAIN):
        assert await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'action': {
                    'service': 'test.automation',
                    'data': 100,
                }
            }
        })


async def test_service_specify_data(hass, calls):
    """Test service data."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'alias': 'hello',
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'action': {
                'service': 'test.automation',
                'data_template': {
                    'some': '{{ trigger.platform }} - '
                            '{{ trigger.event.event_type }}'
                },
            }
        }
    })

    time = dt_util.utcnow()

    with patch('homeassistant.components.automation.utcnow',
               return_value=time):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data['some'] == 'event - test_event'
    state = hass.states.get('automation.hello')
    assert state is not None
    assert state.attributes.get('last_triggered') == time

    state = hass.states.get('group.all_automations')
    assert state is not None
    assert state.attributes.get('entity_id') == ('automation.hello',)


async def test_action_delay(hass, calls):
    """Test action delay."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'alias': 'hello',
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'action': [
                {
                    'service': 'test.automation',
                    'data_template': {
                        'some': '{{ trigger.platform }} - '
                                '{{ trigger.event.event_type }}'
                    }
                },
                {'delay': {'minutes': '10'}},
                {
                    'service': 'test.automation',
                    'data_template': {
                        'some': '{{ trigger.platform }} - '
                                '{{ trigger.event.event_type }}'
                    }
                },
            ]
        }
    })

    time = dt_util.utcnow()

    with patch('homeassistant.components.automation.utcnow',
               return_value=time):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data['some'] == 'event - test_event'

    future = dt_util.utcnow() + timedelta(minutes=10)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert len(calls) == 2
    assert calls[1].data['some'] == 'event - test_event'

    state = hass.states.get('automation.hello')
    assert state is not None
    assert state.attributes.get('last_triggered') == time
    state = hass.states.get('group.all_automations')
    assert state is not None
    assert state.attributes.get('entity_id') == ('automation.hello',)


async def test_service_specify_entity_id(hass, calls):
    """Test service data."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'action': {
                'service': 'test.automation',
                'entity_id': 'hello.world'
            }
        }
    })

    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()
    assert 1 == len(calls)
    assert ['hello.world'] == \
        calls[0].data.get(ATTR_ENTITY_ID)


async def test_service_specify_entity_id_list(hass, calls):
    """Test service data."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'action': {
                'service': 'test.automation',
                'entity_id': ['hello.world', 'hello.world2']
            }
        }
    })

    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()
    assert 1 == len(calls)
    assert ['hello.world', 'hello.world2'] == \
        calls[0].data.get(ATTR_ENTITY_ID)


async def test_two_triggers(hass, calls):
    """Test triggers."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': [
                {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                }
            ],
            'action': {
                'service': 'test.automation',
            }
        }
    })

    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()
    assert 1 == len(calls)
    hass.states.async_set('test.entity', 'hello')
    await hass.async_block_till_done()
    assert 2 == len(calls)


async def test_trigger_service_ignoring_condition(hass, calls):
    """Test triggers."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'alias': 'test',
            'trigger': [
                {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
            ],
            'condition': {
                'condition': 'state',
                'entity_id': 'non.existing',
                'state': 'beer',
            },
            'action': {
                'service': 'test.automation',
            }
        }
    })

    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()
    assert len(calls) == 0

    await hass.services.async_call(
        'automation', 'trigger',
        {'entity_id': 'automation.test'},
        blocking=True)
    assert len(calls) == 1


async def test_two_conditions_with_and(hass, calls):
    """Test two and conditions."""
    entity_id = 'test.entity'
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': [
                {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
            ],
            'condition': [
                {
                    'condition': 'state',
                    'entity_id': entity_id,
                    'state': '100'
                },
                {
                    'condition': 'numeric_state',
                    'entity_id': entity_id,
                    'below': 150
                }
            ],
            'action': {
                'service': 'test.automation',
            }
        }
    })

    hass.states.async_set(entity_id, 100)
    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()
    assert 1 == len(calls)

    hass.states.async_set(entity_id, 101)
    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()
    assert 1 == len(calls)

    hass.states.async_set(entity_id, 151)
    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_automation_list_setting(hass, calls):
    """Event is not a valid condition."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: [{
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },

            'action': {
                'service': 'test.automation',
            }
        }, {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event_2',
            },
            'action': {
                'service': 'test.automation',
            }
        }]
    })

    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()
    assert 1 == len(calls)

    hass.bus.async_fire('test_event_2')
    await hass.async_block_till_done()
    assert 2 == len(calls)


async def test_automation_calling_two_actions(hass, calls):
    """Test if we can call two actions from automation async definition."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },

            'action': [{
                'service': 'test.automation',
                'data': {'position': 0},
            }, {
                'service': 'test.automation',
                'data': {'position': 1},
            }],
        }
    })

    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()

    assert len(calls) == 2
    assert calls[0].data['position'] == 0
    assert calls[1].data['position'] == 1


async def test_services(hass, calls):
    """Test the automation services for turning entities on/off."""
    entity_id = 'automation.hello'

    assert hass.states.get(entity_id) is None
    assert not automation.is_on(hass, entity_id)

    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'alias': 'hello',
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'action': {
                'service': 'test.automation',
            }
        }
    })

    assert hass.states.get(entity_id) is not None
    assert automation.is_on(hass, entity_id)

    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()
    assert len(calls) == 1

    await common.async_turn_off(hass, entity_id)
    await hass.async_block_till_done()

    assert not automation.is_on(hass, entity_id)
    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()
    assert len(calls) == 1

    await common.async_toggle(hass, entity_id)
    await hass.async_block_till_done()

    assert automation.is_on(hass, entity_id)
    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()
    assert len(calls) == 2

    await common.async_trigger(hass, entity_id)
    await hass.async_block_till_done()
    assert len(calls) == 3

    await common.async_turn_off(hass, entity_id)
    await hass.async_block_till_done()
    await common.async_trigger(hass, entity_id)
    await hass.async_block_till_done()
    assert len(calls) == 4

    await common.async_turn_on(hass, entity_id)
    await hass.async_block_till_done()
    assert automation.is_on(hass, entity_id)


async def test_reload_config_service(hass, calls):
    """Test the reload config service."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'alias': 'hello',
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'action': {
                'service': 'test.automation',
                'data_template': {
                    'event': '{{ trigger.event.event_type }}'
                }
            }
        }
    })
    assert hass.states.get('automation.hello') is not None
    assert hass.states.get('automation.bye') is None
    listeners = hass.bus.async_listeners()
    assert listeners.get('test_event') == 1
    assert listeners.get('test_event2') is None

    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data.get('event') == 'test_event'

    with patch('homeassistant.config.load_yaml_config_file', autospec=True,
               return_value={
                automation.DOMAIN: {
                    'alias': 'bye',
                    'trigger': {
                        'platform': 'event',
                        'event_type': 'test_event2',
                    },
                    'action': {
                        'service': 'test.automation',
                        'data_template': {
                            'event': '{{ trigger.event.event_type }}'
                        }
                    }
                }}):
        with patch('homeassistant.config.find_config_file',
                   return_value=''):
            await common.async_reload(hass)
            await hass.async_block_till_done()
            # De-flake ?!
            await hass.async_block_till_done()

    assert hass.states.get('automation.hello') is None
    assert hass.states.get('automation.bye') is not None
    listeners = hass.bus.async_listeners()
    assert listeners.get('test_event') is None
    assert listeners.get('test_event2') == 1

    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.bus.async_fire('test_event2')
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data.get('event') == 'test_event2'


async def test_reload_config_when_invalid_config(hass, calls):
    """Test the reload config service handling invalid config."""
    with assert_setup_component(1, automation.DOMAIN):
        assert await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'alias': 'hello',
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'action': {
                    'service': 'test.automation',
                    'data_template': {
                        'event': '{{ trigger.event.event_type }}'
                    }
                }
            }
        })
    assert hass.states.get('automation.hello') is not None

    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data.get('event') == 'test_event'

    with patch('homeassistant.config.load_yaml_config_file', autospec=True,
               return_value={automation.DOMAIN: 'not valid'}):
        with patch('homeassistant.config.find_config_file',
                   return_value=''):
            await common.async_reload(hass)
            await hass.async_block_till_done()

    assert hass.states.get('automation.hello') is None

    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_reload_config_handles_load_fails(hass, calls):
    """Test the reload config service."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'alias': 'hello',
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'action': {
                'service': 'test.automation',
                'data_template': {
                    'event': '{{ trigger.event.event_type }}'
                }
            }
        }
    })
    assert hass.states.get('automation.hello') is not None

    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data.get('event') == 'test_event'

    with patch('homeassistant.config.load_yaml_config_file',
               side_effect=HomeAssistantError('bla')):
        with patch('homeassistant.config.find_config_file',
                   return_value=''):
            await common.async_reload(hass)
            await hass.async_block_till_done()

    assert hass.states.get('automation.hello') is not None

    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()
    assert len(calls) == 2


@asyncio.coroutine
def test_automation_restore_state(hass):
    """Ensure states are restored on startup."""
    time = dt_util.utcnow()

    mock_restore_cache(hass, (
        State('automation.hello', STATE_ON),
        State('automation.bye', STATE_OFF, {'last_triggered': time}),
    ))

    config = {automation.DOMAIN: [{
        'alias': 'hello',
        'trigger': {
            'platform': 'event',
            'event_type': 'test_event_hello',
        },
        'action': {'service': 'test.automation'}
    }, {
        'alias': 'bye',
        'trigger': {
            'platform': 'event',
            'event_type': 'test_event_bye',
        },
        'action': {'service': 'test.automation'}
    }]}

    assert (yield from async_setup_component(hass, automation.DOMAIN, config))

    state = hass.states.get('automation.hello')
    assert state
    assert state.state == STATE_ON

    state = hass.states.get('automation.bye')
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get('last_triggered') == time

    calls = async_mock_service(hass, 'test', 'automation')

    assert automation.is_on(hass, 'automation.bye') is False

    hass.bus.async_fire('test_event_bye')
    yield from hass.async_block_till_done()
    assert len(calls) == 0

    assert automation.is_on(hass, 'automation.hello')

    hass.bus.async_fire('test_event_hello')
    yield from hass.async_block_till_done()

    assert len(calls) == 1


@asyncio.coroutine
def test_initial_value_off(hass):
    """Test initial value off."""
    calls = async_mock_service(hass, 'test', 'automation')

    res = yield from async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'alias': 'hello',
            'initial_state': 'off',
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'action': {
                'service': 'test.automation',
                'entity_id': 'hello.world'
            }
        }
    })
    assert res
    assert not automation.is_on(hass, 'automation.hello')

    hass.bus.async_fire('test_event')
    yield from hass.async_block_till_done()
    assert len(calls) == 0


@asyncio.coroutine
def test_initial_value_on(hass):
    """Test initial value on."""
    calls = async_mock_service(hass, 'test', 'automation')

    res = yield from async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'alias': 'hello',
            'initial_state': 'on',
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'action': {
                'service': 'test.automation',
                'entity_id': ['hello.world', 'hello.world2']
            }
        }
    })
    assert res
    assert automation.is_on(hass, 'automation.hello')

    hass.bus.async_fire('test_event')
    yield from hass.async_block_till_done()
    assert len(calls) == 1


@asyncio.coroutine
def test_initial_value_off_but_restore_on(hass):
    """Test initial value off and restored state is turned on."""
    calls = async_mock_service(hass, 'test', 'automation')
    mock_restore_cache(hass, (
        State('automation.hello', STATE_ON),
    ))

    res = yield from async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'alias': 'hello',
            'initial_state': 'off',
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'action': {
                'service': 'test.automation',
                'entity_id': 'hello.world'
            }
        }
    })
    assert res
    assert not automation.is_on(hass, 'automation.hello')

    hass.bus.async_fire('test_event')
    yield from hass.async_block_till_done()
    assert len(calls) == 0


@asyncio.coroutine
def test_initial_value_on_but_restore_off(hass):
    """Test initial value on and restored state is turned off."""
    calls = async_mock_service(hass, 'test', 'automation')
    mock_restore_cache(hass, (
        State('automation.hello', STATE_OFF),
    ))

    res = yield from async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'alias': 'hello',
            'initial_state': 'on',
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'action': {
                'service': 'test.automation',
                'entity_id': 'hello.world'
            }
        }
    })
    assert res
    assert automation.is_on(hass, 'automation.hello')

    hass.bus.async_fire('test_event')
    yield from hass.async_block_till_done()
    assert len(calls) == 1


@asyncio.coroutine
def test_no_initial_value_and_restore_off(hass):
    """Test initial value off and restored state is turned on."""
    calls = async_mock_service(hass, 'test', 'automation')
    mock_restore_cache(hass, (
        State('automation.hello', STATE_OFF),
    ))

    res = yield from async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'alias': 'hello',
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'action': {
                'service': 'test.automation',
                'entity_id': 'hello.world'
            }
        }
    })
    assert res
    assert not automation.is_on(hass, 'automation.hello')

    hass.bus.async_fire('test_event')
    yield from hass.async_block_till_done()
    assert len(calls) == 0


@asyncio.coroutine
def test_automation_is_on_if_no_initial_state_or_restore(hass):
    """Test initial value is on when no initial state or restored state."""
    calls = async_mock_service(hass, 'test', 'automation')

    res = yield from async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'alias': 'hello',
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'action': {
                'service': 'test.automation',
                'entity_id': 'hello.world'
            }
        }
    })
    assert res
    assert automation.is_on(hass, 'automation.hello')

    hass.bus.async_fire('test_event')
    yield from hass.async_block_till_done()
    assert len(calls) == 1


@asyncio.coroutine
def test_automation_not_trigger_on_bootstrap(hass):
    """Test if automation is not trigger on bootstrap."""
    hass.state = CoreState.not_running
    calls = async_mock_service(hass, 'test', 'automation')

    res = yield from async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'alias': 'hello',
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'action': {
                'service': 'test.automation',
                'entity_id': 'hello.world'
            }
        }
    })
    assert res
    assert not automation.is_on(hass, 'automation.hello')

    hass.bus.async_fire('test_event')
    yield from hass.async_block_till_done()
    assert len(calls) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    yield from hass.async_block_till_done()
    assert automation.is_on(hass, 'automation.hello')

    hass.bus.async_fire('test_event')
    yield from hass.async_block_till_done()

    assert len(calls) == 1
    assert ['hello.world'] == calls[0].data.get(ATTR_ENTITY_ID)
