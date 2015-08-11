"""
tests.test_component_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests demo component.
"""
import unittest

import homeassistant as ha
import homeassistant.loader as loader
import homeassistant.components.automation as automation
import homeassistant.components.automation.event as event
from homeassistant.const import CONF_PLATFORM


class TestAutomationEvent(unittest.TestCase):
    """ Test the event automation. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()
        loader.prepare(self.hass)
        self.calls = []

        def record_call(service):
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_if_fires_on_event(self):
        automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'event',
                event.CONF_EVENT_TYPE: 'test_event',
                automation.CONF_SERVICE: 'test.automation'
            }
        })

        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_event_with_data(self):
        automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'event',
                event.CONF_EVENT_TYPE: 'test_event',
                event.CONF_EVENT_DATA: {'some_attr': 'some_value'},
                automation.CONF_SERVICE: 'test.automation'
            }
        })

        self.hass.bus.fire('test_event', {'some_attr': 'some_value'})
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_if_event_data_not_matches(self):
        automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'event',
                event.CONF_EVENT_TYPE: 'test_event',
                event.CONF_EVENT_DATA: {'some_attr': 'some_value'},
                automation.CONF_SERVICE: 'test.automation'
            }
        })

        self.hass.bus.fire('test_event', {'some_attr': 'some_other_value'})
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))
