"""The tests for the automation component."""
import unittest

import homeassistant.components.automation as automation
from homeassistant.const import ATTR_ENTITY_ID

from tests.common import get_test_home_assistant


class TestAutomation(unittest.TestCase):
    """Test the event automation."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.calls = []

        def record_call(service):
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_old_config_service_data_not_a_dict(self):
        """Test old configuration service data."""
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
        """Test old configuration service data."""
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
        """Test old configuration service data."""
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
        """Test old configuration service data."""
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
        """Test service data not dict."""
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
        """Test service data."""
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
        """Test service data."""
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
        """Test service data."""
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
        """Test triggers."""
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
        """Test two and conditions."""
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
        """Test two or conditions."""
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
        """Test triggers as condition."""
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
        """Event is not a valid condition."""
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
        """Event is not a valid condition."""
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
