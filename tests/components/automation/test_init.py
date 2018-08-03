"""The tests for the automation component."""
import asyncio
from datetime import timedelta
import unittest
from unittest.mock import patch

from homeassistant.core import State, CoreState
from homeassistant.setup import setup_component, async_setup_component
import homeassistant.components.automation as automation
from homeassistant.const import (
    ATTR_ENTITY_ID, STATE_ON, STATE_OFF, EVENT_HOMEASSISTANT_START)
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.dt as dt_util

from tests.common import (
    assert_setup_component, get_test_home_assistant, fire_time_changed,
    mock_service, async_mock_service, mock_restore_cache)


# pylint: disable=invalid-name
class TestAutomation(unittest.TestCase):
    """Test the event automation."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.calls = mock_service(self.hass, 'test', 'automation')

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_service_data_not_a_dict(self):
        """Test service data not dict."""
        with assert_setup_component(0, automation.DOMAIN):
            assert setup_component(self.hass, automation.DOMAIN, {
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

    def test_service_specify_data(self):
        """Test service data."""
        assert setup_component(self.hass, automation.DOMAIN, {
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
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
        assert len(self.calls) == 1
        assert self.calls[0].data['some'] == 'event - test_event'
        state = self.hass.states.get('automation.hello')
        assert state is not None
        assert state.attributes.get('last_triggered') == time

        state = self.hass.states.get('group.all_automations')
        assert state is not None
        assert state.attributes.get('entity_id') == ('automation.hello',)

    def test_action_delay(self):
        """Test action delay."""
        assert setup_component(self.hass, automation.DOMAIN, {
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
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()

        assert len(self.calls) == 1
        assert self.calls[0].data['some'] == 'event - test_event'

        future = dt_util.utcnow() + timedelta(minutes=10)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()

        assert len(self.calls) == 2
        assert self.calls[1].data['some'] == 'event - test_event'

        state = self.hass.states.get('automation.hello')
        assert state is not None
        assert state.attributes.get('last_triggered') == time
        state = self.hass.states.get('group.all_automations')
        assert state is not None
        assert state.attributes.get('entity_id') == ('automation.hello',)

    def test_service_specify_entity_id(self):
        """Test service data."""
        assert setup_component(self.hass, automation.DOMAIN, {
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

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual(['hello.world'],
                         self.calls[0].data.get(ATTR_ENTITY_ID))

    def test_service_specify_entity_id_list(self):
        """Test service data."""
        assert setup_component(self.hass, automation.DOMAIN, {
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

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual(['hello.world', 'hello.world2'],
                         self.calls[0].data.get(ATTR_ENTITY_ID))

    def test_two_triggers(self):
        """Test triggers."""
        assert setup_component(self.hass, automation.DOMAIN, {
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

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.hass.states.set('test.entity', 'hello')
        self.hass.block_till_done()
        self.assertEqual(2, len(self.calls))

    def test_trigger_service_ignoring_condition(self):
        """Test triggers."""
        assert setup_component(self.hass, automation.DOMAIN, {
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

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        assert len(self.calls) == 0

        self.hass.services.call('automation', 'trigger',
                                {'entity_id': 'automation.test'},
                                blocking=True)
        self.hass.block_till_done()
        assert len(self.calls) == 1

    def test_two_conditions_with_and(self):
        """Test two and conditions."""
        entity_id = 'test.entity'
        assert setup_component(self.hass, automation.DOMAIN, {
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

        self.hass.states.set(entity_id, 100)
        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

        self.hass.states.set(entity_id, 101)
        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

        self.hass.states.set(entity_id, 151)
        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_automation_list_setting(self):
        """Event is not a valid condition."""
        self.assertTrue(setup_component(self.hass, automation.DOMAIN, {
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
        }))

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

        self.hass.bus.fire('test_event_2')
        self.hass.block_till_done()
        self.assertEqual(2, len(self.calls))

    def test_automation_calling_two_actions(self):
        """Test if we can call two actions from automation definition."""
        self.assertTrue(setup_component(self.hass, automation.DOMAIN, {
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
        }))

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()

        assert len(self.calls) == 2
        assert self.calls[0].data['position'] == 0
        assert self.calls[1].data['position'] == 1

    def test_services(self):
        """Test the automation services for turning entities on/off."""
        entity_id = 'automation.hello'

        assert self.hass.states.get(entity_id) is None
        assert not automation.is_on(self.hass, entity_id)

        assert setup_component(self.hass, automation.DOMAIN, {
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

        assert self.hass.states.get(entity_id) is not None
        assert automation.is_on(self.hass, entity_id)

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        assert len(self.calls) == 1

        automation.turn_off(self.hass, entity_id)
        self.hass.block_till_done()

        assert not automation.is_on(self.hass, entity_id)
        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        assert len(self.calls) == 1

        automation.toggle(self.hass, entity_id)
        self.hass.block_till_done()

        assert automation.is_on(self.hass, entity_id)
        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        assert len(self.calls) == 2

        automation.trigger(self.hass, entity_id)
        self.hass.block_till_done()
        assert len(self.calls) == 3

        automation.turn_off(self.hass, entity_id)
        self.hass.block_till_done()
        automation.trigger(self.hass, entity_id)
        self.hass.block_till_done()
        assert len(self.calls) == 4

        automation.turn_on(self.hass, entity_id)
        self.hass.block_till_done()
        assert automation.is_on(self.hass, entity_id)

    def test_reload_config_service(self):
        """Test the reload config service."""
        assert setup_component(self.hass, automation.DOMAIN, {
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
        assert self.hass.states.get('automation.hello') is not None
        assert self.hass.states.get('automation.bye') is None
        listeners = self.hass.bus.listeners
        assert listeners.get('test_event') == 1
        assert listeners.get('test_event2') is None

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()

        assert len(self.calls) == 1
        assert self.calls[0].data.get('event') == 'test_event'

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
                automation.reload(self.hass)
                self.hass.block_till_done()
                # De-flake ?!
                self.hass.block_till_done()

        assert self.hass.states.get('automation.hello') is None
        assert self.hass.states.get('automation.bye') is not None
        listeners = self.hass.bus.listeners
        assert listeners.get('test_event') is None
        assert listeners.get('test_event2') == 1

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        assert len(self.calls) == 1

        self.hass.bus.fire('test_event2')
        self.hass.block_till_done()
        assert len(self.calls) == 2
        assert self.calls[1].data.get('event') == 'test_event2'

    def test_reload_config_when_invalid_config(self):
        """Test the reload config service handling invalid config."""
        with assert_setup_component(1, automation.DOMAIN):
            assert setup_component(self.hass, automation.DOMAIN, {
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
        assert self.hass.states.get('automation.hello') is not None

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()

        assert len(self.calls) == 1
        assert self.calls[0].data.get('event') == 'test_event'

        with patch('homeassistant.config.load_yaml_config_file', autospec=True,
                   return_value={automation.DOMAIN: 'not valid'}):
            with patch('homeassistant.config.find_config_file',
                       return_value=''):
                automation.reload(self.hass)
                self.hass.block_till_done()

        assert self.hass.states.get('automation.hello') is None

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        assert len(self.calls) == 1

    def test_reload_config_handles_load_fails(self):
        """Test the reload config service."""
        assert setup_component(self.hass, automation.DOMAIN, {
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
        assert self.hass.states.get('automation.hello') is not None

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()

        assert len(self.calls) == 1
        assert self.calls[0].data.get('event') == 'test_event'

        with patch('homeassistant.config.load_yaml_config_file',
                   side_effect=HomeAssistantError('bla')):
            with patch('homeassistant.config.find_config_file',
                       return_value=''):
                automation.reload(self.hass)
                self.hass.block_till_done()

        assert self.hass.states.get('automation.hello') is not None

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        assert len(self.calls) == 2


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
