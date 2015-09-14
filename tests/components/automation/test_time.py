"""
tests.test_component_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests demo component.
"""
from datetime import timedelta
import unittest
from unittest.mock import patch

import homeassistant.core as ha
import homeassistant.util.dt as dt_util
import homeassistant.components.automation as automation
from homeassistant.components.automation import time, event
from homeassistant.const import CONF_PLATFORM

from tests.common import fire_time_changed


class TestAutomationTime(unittest.TestCase):
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

    def test_if_action_before(self):
        automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'event',
                event.CONF_EVENT_TYPE: 'test_event',
                automation.CONF_SERVICE: 'test.automation',
                automation.CONF_IF: {
                    CONF_PLATFORM: 'time',
                    time.CONF_BEFORE: '10:00'
                }
            }
        })

        before_10 = dt_util.now().replace(hour=8)
        after_10 = dt_util.now().replace(hour=14)

        with patch('homeassistant.components.automation.time.dt_util.now',
                   return_value=before_10):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()

        self.assertEqual(1, len(self.calls))

        with patch('homeassistant.components.automation.time.dt_util.now',
                   return_value=after_10):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()

        self.assertEqual(1, len(self.calls))

    def test_if_action_after(self):
        automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'event',
                event.CONF_EVENT_TYPE: 'test_event',
                automation.CONF_SERVICE: 'test.automation',
                automation.CONF_IF: {
                    CONF_PLATFORM: 'time',
                    time.CONF_AFTER: '10:00'
                }
            }
        })

        before_10 = dt_util.now().replace(hour=8)
        after_10 = dt_util.now().replace(hour=14)

        with patch('homeassistant.components.automation.time.dt_util.now',
                   return_value=before_10):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()

        self.assertEqual(0, len(self.calls))

        with patch('homeassistant.components.automation.time.dt_util.now',
                   return_value=after_10):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()

        self.assertEqual(1, len(self.calls))

    def test_if_action_one_weekday(self):
        automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'event',
                event.CONF_EVENT_TYPE: 'test_event',
                automation.CONF_SERVICE: 'test.automation',
                automation.CONF_IF: {
                    CONF_PLATFORM: 'time',
                    time.CONF_WEEKDAY: 'mon',
                }
            }
        })

        days_past_monday = dt_util.now().weekday()
        monday = dt_util.now() - timedelta(days=days_past_monday)
        tuesday = monday + timedelta(days=1)

        with patch('homeassistant.components.automation.time.dt_util.now',
                   return_value=monday):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()

        self.assertEqual(1, len(self.calls))

        with patch('homeassistant.components.automation.time.dt_util.now',
                   return_value=tuesday):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()

        self.assertEqual(1, len(self.calls))

    def test_if_action_list_weekday(self):
        automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'event',
                event.CONF_EVENT_TYPE: 'test_event',
                automation.CONF_SERVICE: 'test.automation',
                automation.CONF_IF: {
                    CONF_PLATFORM: 'time',
                    time.CONF_WEEKDAY: ['mon', 'tue'],
                }
            }
        })

        days_past_monday = dt_util.now().weekday()
        monday = dt_util.now() - timedelta(days=days_past_monday)
        tuesday = monday + timedelta(days=1)
        wednesday = tuesday + timedelta(days=1)

        with patch('homeassistant.components.automation.time.dt_util.now',
                   return_value=monday):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()

        self.assertEqual(1, len(self.calls))

        with patch('homeassistant.components.automation.time.dt_util.now',
                   return_value=tuesday):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()

        self.assertEqual(2, len(self.calls))

        with patch('homeassistant.components.automation.time.dt_util.now',
                   return_value=wednesday):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()

        self.assertEqual(2, len(self.calls))
