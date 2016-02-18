"""
tests.components.automation.test_init
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests automation component.
"""
import unittest

import homeassistant.components.automation as automation
from homeassistant.const import ATTR_ENTITY_ID

from tests.common import get_test_home_assistant


class TestAutomation(unittest.TestCase):
    """ Test the event automation. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = get_test_home_assistant()
        self.calls = []

        def record_call(service):
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_old_config_service_data_not_a_dict(self):
        automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'event',
                'event_type': 'test_event',
                'execute_service': 'test.automation',
                'service_data': 100
            }
        })

        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_old_config_service_specify_data(self):
        automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'event',
                'event_type': 'test_event',
                'execute_service': 'test.automation',
                'service_data': {'some': 'data'}
            }
        })

        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('data', self.calls[0].data['some'])

    def test_old_config_service_specify_entity_id(self):
        automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'event',
                'event_type': 'test_event',
                'execute_service': 'test.automation',
                'service_entity_id': 'hello.world'
            }
        })

        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual(['hello.world'],
                         self.calls[0].data.get(ATTR_ENTITY_ID))

    def test_old_config_service_specify_entity_id_list(self):
        automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'event',
                'event_type': 'test_event',
                'execute_service': 'test.automation',
                'service_entity_id': ['hello.world', 'hello.world2']
            }
        })

        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual(['hello.world', 'hello.world2'],
                         self.calls[0].data.get(ATTR_ENTITY_ID))

    def test_service_data_not_a_dict(self):
        automation.setup(self.hass, {
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

        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_service_specify_data(self):
        automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'action': {
                    'service': 'test.automation',
                    'data': {'some': 'data'}
                }
            }
        })

        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('data', self.calls[0].data['some'])

    def test_service_specify_entity_id(self):
        automation.setup(self.hass, {
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
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual(['hello.world'],
                         self.calls[0].data.get(ATTR_ENTITY_ID))

    def test_service_specify_entity_id_list(self):
        automation.setup(self.hass, {
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
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual(['hello.world', 'hello.world2'],
                         self.calls[0].data.get(ATTR_ENTITY_ID))

    def test_two_triggers(self):
        automation.setup(self.hass, {
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
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.hass.states.set('test.entity', 'hello')
        self.hass.pool.block_till_done()
        self.assertEqual(2, len(self.calls))

    def test_two_conditions_with_and(self):
        entity_id = 'test.entity'
        automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': [
                    {
                        'platform': 'event',
                        'event_type': 'test_event',
                    },
                ],
                'condition': [
                    {
                        'platform': 'state',
                        'entity_id': entity_id,
                        'state': 100
                    },
                    {
                        'platform': 'numeric_state',
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
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

        self.hass.states.set(entity_id, 101)
        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

        self.hass.states.set(entity_id, 151)
        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_two_conditions_with_or(self):
        entity_id = 'test.entity'
        automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': [
                    {
                        'platform': 'event',
                        'event_type': 'test_event',
                    },
                ],
                'condition_type': 'OR',
                'condition': [
                    {
                        'platform': 'state',
                        'entity_id': entity_id,
                        'state': 200
                    },
                    {
                        'platform': 'numeric_state',
                        'entity_id': entity_id,
                        'below': 150
                    }
                ],
                'action': {
                    'service': 'test.automation',
                }
            }
        })

        self.hass.states.set(entity_id, 200)
        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

        self.hass.states.set(entity_id, 100)
        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(2, len(self.calls))

        self.hass.states.set(entity_id, 250)
        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(2, len(self.calls))

    def test_using_trigger_as_condition(self):
        """ """
        entity_id = 'test.entity'
        automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': [
                    {
                        'platform': 'state',
                        'entity_id': entity_id,
                        'state': 100
                    },
                    {
                        'platform': 'numeric_state',
                        'entity_id': entity_id,
                        'below': 150
                    }
                ],
                'condition': 'use_trigger_values',
                'action': {
                    'service': 'test.automation',
                }
            }
        })

        self.hass.states.set(entity_id, 100)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

        self.hass.states.set(entity_id, 120)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

        self.hass.states.set(entity_id, 151)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_using_trigger_as_condition_with_invalid_condition(self):
        """ Event is not a valid condition. Will it still work? """
        entity_id = 'test.entity'
        self.hass.states.set(entity_id, 100)
        automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': [
                    {
                        'platform': 'event',
                        'event_type': 'test_event',
                    },
                    {
                        'platform': 'numeric_state',
                        'entity_id': entity_id,
                        'below': 150
                    }
                ],
                'condition': 'use_trigger_values',
                'action': {
                    'service': 'test.automation',
                }
            }
        })

        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_automation_list_setting(self):
        """ Event is not a valid condition. Will it still work? """
        self.assertTrue(automation.setup(self.hass, {
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
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

        self.hass.bus.fire('test_event_2')
        self.hass.pool.block_till_done()
        self.assertEqual(2, len(self.calls))
