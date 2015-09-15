"""
tests.components.automation.test_sun
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests sun automation.
"""
from datetime import datetime
import unittest

import homeassistant.core as ha
from homeassistant.components import sun
import homeassistant.components.automation as automation
import homeassistant.util.dt as dt_util

from tests.common import fire_time_changed


class TestAutomationSun(unittest.TestCase):
    """ Test the sun automation. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()
        self.hass.config.components.append('sun')

        self.calls = []

        def record_call(service):
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_sunset_trigger(self):
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_SETTING: '02:00:00 16-09-2015',
        })

        trigger_time = datetime(2015, 9, 16, 2, tzinfo=dt_util.UTC)

        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'sun',
                    'event': 'sunset',
                },
                'action': {
                    'execute_service': 'test.automation',
                }
            }
        }))

        fire_time_changed(self.hass, trigger_time)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_sunrise_trigger(self):
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_RISING: '14:00:00 16-09-2015',
        })

        trigger_time = datetime(2015, 9, 16, 14, tzinfo=dt_util.UTC)

        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'sun',
                    'event': 'sunrise',
                },
                'action': {
                    'execute_service': 'test.automation',
                }
            }
        }))

        fire_time_changed(self.hass, trigger_time)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_sunset_trigger_with_offset(self):
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_SETTING: '02:00:00 16-09-2015',
        })

        trigger_time = datetime(2015, 9, 16, 2, 30, tzinfo=dt_util.UTC)

        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'sun',
                    'event': 'sunset',
                    'offset': '0:30:00'
                },
                'action': {
                    'execute_service': 'test.automation',
                }
            }
        }))

        fire_time_changed(self.hass, trigger_time)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_sunrise_trigger_with_offset(self):
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_RISING: '14:00:00 16-09-2015',
        })

        trigger_time = datetime(2015, 9, 16, 13, 30, tzinfo=dt_util.UTC)

        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'sun',
                    'event': 'sunrise',
                    'offset': '-0:30:00'
                },
                'action': {
                    'execute_service': 'test.automation',
                }
            }
        }))

        fire_time_changed(self.hass, trigger_time)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
