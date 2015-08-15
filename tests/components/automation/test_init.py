"""
tests.test_component_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests demo component.
"""
import unittest

import homeassistant as ha
import homeassistant.components.automation as automation
import homeassistant.components.automation.event as event
from homeassistant.const import CONF_PLATFORM, ATTR_ENTITY_ID


class TestAutomationEvent(unittest.TestCase):
    """ Test the event automation. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()
        self.calls = []

        def record_call(service):
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_setup_fails_if_unknown_platform(self):
        self.assertFalse(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'i_do_not_exist'
            }
        }))

    def test_service_data_not_a_dict(self):
        automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'event',
                event.CONF_EVENT_TYPE: 'test_event',
                automation.CONF_SERVICE: 'test.automation',
                automation.CONF_SERVICE_DATA: 100
            }
        })

        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_service_specify_data(self):
        automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'event',
                event.CONF_EVENT_TYPE: 'test_event',
                automation.CONF_SERVICE: 'test.automation',
                automation.CONF_SERVICE_DATA: {'some': 'data'}
            }
        })

        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('data', self.calls[0].data['some'])

    def test_service_specify_entity_id(self):
        automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'event',
                event.CONF_EVENT_TYPE: 'test_event',
                automation.CONF_SERVICE: 'test.automation',
                automation.CONF_SERVICE_ENTITY_ID: 'hello.world'
            }
        })

        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual(['hello.world'], self.calls[0].data[ATTR_ENTITY_ID])
