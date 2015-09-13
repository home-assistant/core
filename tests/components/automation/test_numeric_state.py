"""
tests.test_component_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests demo component.
"""
import unittest

import homeassistant.core as ha
import homeassistant.components.automation as automation
import homeassistant.components.automation.numeric_state as numeric_state
from homeassistant.const import CONF_PLATFORM


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

    def test_setup_fails_if_no_entity_id(self):
        self.assertFalse(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'numeric_state',
                numeric_state.CONF_BELOW: 10,
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

    def test_setup_fails_if_no_condition(self):
        self.assertFalse(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'numeric_state',
                numeric_state.CONF_ENTITY_ID: 'test.entity',
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

    def test_if_fires_on_entity_change_below(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'numeric_state',
                numeric_state.CONF_ENTITY_ID: 'test.entity',
                numeric_state.CONF_BELOW: 10,
                automation.CONF_SERVICE: 'test.automation'
            }
        }))
        # 9 is below 10
        self.hass.states.set('test.entity', 9)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_over_to_below(self):
        self.hass.states.set('test.entity', 11)
        self.hass.pool.block_till_done()

        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'numeric_state',
                numeric_state.CONF_ENTITY_ID: 'test.entity',
                numeric_state.CONF_BELOW: 10,
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        # 9 is below 10
        self.hass.states.set('test.entity', 9)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))


    def test_if_not_fires_on_entity_change_below_to_below(self):
        self.hass.states.set('test.entity', 9)
        self.hass.pool.block_till_done()

        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'numeric_state',
                numeric_state.CONF_ENTITY_ID: 'test.entity',
                numeric_state.CONF_BELOW: 10,
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        # 9 is below 10 so this should not fire again
        self.hass.states.set('test.entity', 8)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))


    def test_if_fires_on_entity_change_above(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'numeric_state',
                numeric_state.CONF_ENTITY_ID: 'test.entity',
                numeric_state.CONF_ABOVE: 10,
                automation.CONF_SERVICE: 'test.automation'
            }
        }))
        # 11 is above 10
        self.hass.states.set('test.entity', 11)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_below_to_above(self):
        # set initial state
        self.hass.states.set('test.entity', 9)
        self.hass.pool.block_till_done()

        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'numeric_state',
                numeric_state.CONF_ENTITY_ID: 'test.entity',
                numeric_state.CONF_ABOVE: 10,
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        # 11 is above 10 and 9 is below
        self.hass.states.set('test.entity', 11)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))


    def test_if_not_fires_on_entity_change_above_to_above(self):
        # set initial state
        self.hass.states.set('test.entity', 11)
        self.hass.pool.block_till_done()

        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'numeric_state',
                numeric_state.CONF_ENTITY_ID: 'test.entity',
                numeric_state.CONF_ABOVE: 10,
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        # 11 is above 10 so this should fire again
        self.hass.states.set('test.entity', 12)
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_entity_change_below_range(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'numeric_state',
                numeric_state.CONF_ENTITY_ID: 'test.entity',
                numeric_state.CONF_ABOVE: 5,
                numeric_state.CONF_BELOW: 10,
                automation.CONF_SERVICE: 'test.automation'
            }
        }))
        # 9 is below 10
        self.hass.states.set('test.entity', 9)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_below_above_range(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'numeric_state',
                numeric_state.CONF_ENTITY_ID: 'test.entity',
                numeric_state.CONF_ABOVE: 5,
                numeric_state.CONF_BELOW: 10,
                automation.CONF_SERVICE: 'test.automation'
            }
        }))
        # 4 is below 5
        self.hass.states.set('test.entity', 4)
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_entity_change_over_to_below_range(self):
        self.hass.states.set('test.entity', 11)
        self.hass.pool.block_till_done()

        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'numeric_state',
                numeric_state.CONF_ENTITY_ID: 'test.entity',
                numeric_state.CONF_ABOVE: 5,
                numeric_state.CONF_BELOW: 10,
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        # 9 is below 10
        self.hass.states.set('test.entity', 9)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_over_to_below_above_range(self):
        self.hass.states.set('test.entity', 11)
        self.hass.pool.block_till_done()

        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'numeric_state',
                numeric_state.CONF_ENTITY_ID: 'test.entity',
                numeric_state.CONF_ABOVE: 5,
                numeric_state.CONF_BELOW: 10,
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        # 4 is below 5 so it should not fire
        self.hass.states.set('test.entity', 4)
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_not_fires_if_entity_not_match(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'numeric_state',
                numeric_state.CONF_ENTITY_ID: 'test.another_entity',
                numeric_state.CONF_ABOVE: 10,
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        self.hass.states.set('test.entity', 11)
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))
