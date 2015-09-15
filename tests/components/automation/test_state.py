"""
tests.test_component_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests demo component.
"""
import unittest

import homeassistant.core as ha
import homeassistant.components.automation as automation


class TestAutomationState(unittest.TestCase):
    """ Test the event automation. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()
        self.hass.states.set('test.entity', 'hello')
        self.calls = []

        def record_call(service):
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_old_config_if_fires_on_entity_change(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'state',
                'state_entity_id': 'test.entity',
                'execute_service': 'test.automation'
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_old_config_if_fires_on_entity_change_with_from_filter(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'state',
                'state_entity_id': 'test.entity',
                'state_from': 'hello',
                'execute_service': 'test.automation'
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_old_config_if_fires_on_entity_change_with_to_filter(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'state',
                'state_entity_id': 'test.entity',
                'state_to': 'world',
                'execute_service': 'test.automation'
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_old_config_if_fires_on_entity_change_with_both_filters(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'state',
                'state_entity_id': 'test.entity',
                'state_from': 'hello',
                'state_to': 'world',
                'execute_service': 'test.automation'
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_old_config_if_not_fires_if_to_filter_not_match(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'state',
                'state_entity_id': 'test.entity',
                'state_from': 'hello',
                'state_to': 'world',
                'execute_service': 'test.automation'
            }
        }))

        self.hass.states.set('test.entity', 'moon')
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_old_config_if_not_fires_if_from_filter_not_match(self):
        self.hass.states.set('test.entity', 'bye')

        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'state',
                'state_entity_id': 'test.entity',
                'state_from': 'hello',
                'state_to': 'world',
                'execute_service': 'test.automation'
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_old_config_if_not_fires_if_entity_not_match(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'state',
                'state_entity_id': 'test.another_entity',
                'execute_service': 'test.automation'
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_old_config_if_action(self):
        entity_id = 'domain.test_entity'
        test_state = 'new_state'
        automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'event',
                'event_type': 'test_event',
                'execute_service': 'test.automation',
                'if': [{
                    'platform': 'state',
                    'entity_id': entity_id,
                    'state': test_state,
                }]
            }
        })

        self.hass.states.set(entity_id, test_state)
        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()

        self.assertEqual(1, len(self.calls))

        self.hass.states.set(entity_id, test_state + 'something')
        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()

        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                },
                'action': {
                    'execute_service': 'test.automation'
                }
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_with_from_filter(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'from': 'hello'
                },
                'action': {
                    'execute_service': 'test.automation'
                }
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_with_to_filter(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'to': 'world'
                },
                'action': {
                    'execute_service': 'test.automation'
                }
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_with_both_filters(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'from': 'hello',
                    'to': 'world'
                },
                'action': {
                    'execute_service': 'test.automation'
                }
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_if_to_filter_not_match(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'from': 'hello',
                    'to': 'world'
                },
                'action': {
                    'execute_service': 'test.automation'
                }
            }
        }))

        self.hass.states.set('test.entity', 'moon')
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_not_fires_if_from_filter_not_match(self):
        self.hass.states.set('test.entity', 'bye')

        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'from': 'hello',
                    'to': 'world'
                },
                'action': {
                    'execute_service': 'test.automation'
                }
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_not_fires_if_entity_not_match(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.anoter_entity',
                },
                'action': {
                    'execute_service': 'test.automation'
                }
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_action(self):
        entity_id = 'domain.test_entity'
        test_state = 'new_state'
        automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': [{
                    'platform': 'state',
                    'entity_id': entity_id,
                    'state': test_state
                }],
                'action': {
                    'execute_service': 'test.automation'
                }
            }
        })

        self.hass.states.set(entity_id, test_state)
        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()

        self.assertEqual(1, len(self.calls))

        self.hass.states.set(entity_id, test_state + 'something')
        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()

        self.assertEqual(1, len(self.calls))
