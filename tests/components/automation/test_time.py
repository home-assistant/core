"""
tests.test_component_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests demo component.
"""
import unittest

import homeassistant.core as ha
import homeassistant.loader as loader
import homeassistant.util.dt as dt_util
import homeassistant.components.automation as automation
import homeassistant.components.automation.time as time
from homeassistant.const import CONF_PLATFORM

from tests.common import fire_time_changed


class TestAutomationTime(unittest.TestCase):
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

    def test_if_fires_when_hour_matches(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'time',
                time.CONF_HOURS: 0,
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        fire_time_changed(self.hass, dt_util.utcnow().replace(hour=0))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_when_minute_matches(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'time',
                time.CONF_MINUTES: 0,
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        fire_time_changed(self.hass, dt_util.utcnow().replace(minute=0))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_when_second_matches(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'time',
                time.CONF_SECONDS: 0,
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        fire_time_changed(self.hass, dt_util.utcnow().replace(second=0))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_when_all_matches(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'time',
                time.CONF_HOURS: 0,
                time.CONF_MINUTES: 0,
                time.CONF_SECONDS: 0,
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        fire_time_changed(self.hass, dt_util.utcnow().replace(
            hour=0, minute=0, second=0))

        self.hass.states.set('test.entity', 'world')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
