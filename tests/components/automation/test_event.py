"""
tests.components.automation.test_event
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests event automation.
"""
import unittest

import homeassistant.components.automation as automation

from tests.common import get_test_home_assistant


class TestAutomationEvent(unittest.TestCase):
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

    def test_old_config_if_fires_on_event(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'event',
                'event_type': 'test_event',
                'execute_service': 'test.automation'
            }
        }))

        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_old_config_if_fires_on_event_with_data(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'event',
                'event_type': 'test_event',
                'event_data': {'some_attr': 'some_value'},
                'execute_service': 'test.automation'
            }
        }))

        self.hass.bus.fire('test_event', {'some_attr': 'some_value'})
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_old_config_if_not_fires_if_event_data_not_matches(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'event',
                'event_type': 'test_event',
                'event_data': {'some_attr': 'some_value'},
                'execute_service': 'test.automation'
            }
        }))

        self.hass.bus.fire('test_event', {'some_attr': 'some_other_value'})
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_event(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        }))

        self.hass.bus.fire('test_event')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_event_with_data(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                    'event_data': {'some_attr': 'some_value'}
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        }))

        self.hass.bus.fire('test_event', {'some_attr': 'some_value',
                                          'another': 'value'})
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_if_event_data_not_matches(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                    'event_data': {'some_attr': 'some_value'}
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        }))

        self.hass.bus.fire('test_event', {'some_attr': 'some_other_value'})
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))
