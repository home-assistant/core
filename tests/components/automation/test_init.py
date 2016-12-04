"""The tests for the automation component."""
import unittest
from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import callback
from homeassistant.bootstrap import setup_component
import homeassistant.components.automation as automation
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant, assert_setup_component, \
    fire_time_changed


# pylint: disable=invalid-name
class TestAutomation(unittest.TestCase):
    """Test the event automation."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.components.append('group')
        self.calls = []

        @callback
        def record_call(service):
            """Helper to record calls."""
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_service_data_not_a_dict(self):
        """Test service data not dict."""
        with assert_setup_component(0):
            assert not setup_component(self.hass, automation.DOMAIN, {
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

    def test_service_initial_value_off(self):
        """Test initial value off."""
        entity_id = 'automation.hello'

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'alias': 'hello',
                'initial_state': 'off',
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
        assert not automation.is_on(self.hass, entity_id)

    def test_service_initial_value_on(self):
        """Test initial value on."""
        entity_id = 'automation.hello'

        assert setup_component(self.hass, automation.DOMAIN, {
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
        assert automation.is_on(self.hass, entity_id)

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

        self.hass.services.call('automation', 'trigger', blocking=True)
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

    @patch('homeassistant.config.load_yaml_config_file', autospec=True,
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
               }
           })
    def test_reload_config_service(self, mock_load_yaml):
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

    @patch('homeassistant.config.load_yaml_config_file', autospec=True,
           return_value={automation.DOMAIN: 'not valid'})
    def test_reload_config_when_invalid_config(self, mock_load_yaml):
        """Test the reload config service handling invalid config."""
        with assert_setup_component(1):
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
            automation.reload(self.hass)
            self.hass.block_till_done()

        assert self.hass.states.get('automation.hello') is not None

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        assert len(self.calls) == 2
