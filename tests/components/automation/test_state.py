"""
tests.test_component_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests demo component.
"""
import unittest

import homeassistant.core as ha
import homeassistant.components.automation as automation
import homeassistant.components.automation.state as state
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
                CONF_PLATFORM: 'state',
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

    def test_if_fires_on_entity_change(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'state',
                state.CONF_ENTITY_ID: 'test.entity',
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_with_from_filter(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'state',
                state.CONF_ENTITY_ID: 'test.entity',
                state.CONF_FROM: 'hello',
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_with_to_filter(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'state',
                state.CONF_ENTITY_ID: 'test.entity',
                state.CONF_TO: 'world',
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_with_both_filters(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'state',
                state.CONF_ENTITY_ID: 'test.entity',
                state.CONF_FROM: 'hello',
                state.CONF_TO: 'world',
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_if_to_filter_not_match(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'state',
                state.CONF_ENTITY_ID: 'test.entity',
                state.CONF_FROM: 'hello',
                state.CONF_TO: 'world',
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        self.hass.states.set('test.entity', 'moon')
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_not_fires_if_from_filter_not_match(self):
        self.hass.states.set('test.entity', 'bye')

        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'state',
                state.CONF_ENTITY_ID: 'test.entity',
                state.CONF_FROM: 'hello',
                state.CONF_TO: 'world',
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_not_fires_if_entity_not_match(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'state',
                state.CONF_ENTITY_ID: 'test.another_entity',
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))
