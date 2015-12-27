"""
tests.components.automation.test_sun
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests sun automation.
"""
from datetime import datetime
import unittest
from unittest.mock import patch

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

        now = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
        trigger_time = datetime(2015, 9, 16, 2, tzinfo=dt_util.UTC)

        with patch('homeassistant.components.automation.sun.dt_util.utcnow',
                   return_value=now):
            self.assertTrue(automation.setup(self.hass, {
                automation.DOMAIN: {
                    'trigger': {
                        'platform': 'sun',
                        'event': 'sunset',
                    },
                    'action': {
                        'service': 'test.automation',
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

        now = datetime(2015, 9, 13, 23, tzinfo=dt_util.UTC)
        trigger_time = datetime(2015, 9, 16, 14, tzinfo=dt_util.UTC)

        with patch('homeassistant.components.automation.sun.dt_util.utcnow',
                   return_value=now):
            self.assertTrue(automation.setup(self.hass, {
                automation.DOMAIN: {
                    'trigger': {
                        'platform': 'sun',
                        'event': 'sunrise',
                    },
                    'action': {
                        'service': 'test.automation',
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

        now = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
        trigger_time = datetime(2015, 9, 16, 2, 30, tzinfo=dt_util.UTC)

        with patch('homeassistant.components.automation.sun.dt_util.utcnow',
                   return_value=now):
            self.assertTrue(automation.setup(self.hass, {
                automation.DOMAIN: {
                    'trigger': {
                        'platform': 'sun',
                        'event': 'sunset',
                        'offset': '0:30:00'
                    },
                    'action': {
                        'service': 'test.automation',
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

        now = datetime(2015, 9, 13, 23, tzinfo=dt_util.UTC)
        trigger_time = datetime(2015, 9, 16, 13, 30, tzinfo=dt_util.UTC)

        with patch('homeassistant.components.automation.sun.dt_util.utcnow',
                   return_value=now):
            self.assertTrue(automation.setup(self.hass, {
                automation.DOMAIN: {
                    'trigger': {
                        'platform': 'sun',
                        'event': 'sunrise',
                        'offset': '-0:30:00'
                    },
                    'action': {
                        'service': 'test.automation',
                    }
                }
            }))

        fire_time_changed(self.hass, trigger_time)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_action_before(self):
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_RISING: '14:00:00 16-09-2015',
        })

        automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': {
                    'platform': 'sun',
                    'before': 'sunrise',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        now = datetime(2015, 9, 16, 15, tzinfo=dt_util.UTC)
        with patch('homeassistant.components.automation.sun.dt_util.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 10, tzinfo=dt_util.UTC)
        with patch('homeassistant.components.automation.sun.dt_util.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()
            self.assertEqual(1, len(self.calls))

    def test_if_action_after(self):
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_RISING: '14:00:00 16-09-2015',
        })

        automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': {
                    'platform': 'sun',
                    'after': 'sunrise',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        now = datetime(2015, 9, 16, 13, tzinfo=dt_util.UTC)
        with patch('homeassistant.components.automation.sun.dt_util.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 15, tzinfo=dt_util.UTC)
        with patch('homeassistant.components.automation.sun.dt_util.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()
            self.assertEqual(1, len(self.calls))

    def test_if_action_before_with_offset(self):
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_RISING: '14:00:00 16-09-2015',
        })

        automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': {
                    'platform': 'sun',
                    'before': 'sunrise',
                    'before_offset': '+1:00:00'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        now = datetime(2015, 9, 16, 15, 1, tzinfo=dt_util.UTC)
        with patch('homeassistant.components.automation.sun.dt_util.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 15, tzinfo=dt_util.UTC)
        with patch('homeassistant.components.automation.sun.dt_util.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()
            self.assertEqual(1, len(self.calls))

    def test_if_action_after_with_offset(self):
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_RISING: '14:00:00 16-09-2015',
        })

        automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': {
                    'platform': 'sun',
                    'after': 'sunrise',
                    'after_offset': '+1:00:00'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        now = datetime(2015, 9, 16, 14, 59, tzinfo=dt_util.UTC)
        with patch('homeassistant.components.automation.sun.dt_util.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 15, tzinfo=dt_util.UTC)
        with patch('homeassistant.components.automation.sun.dt_util.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()
            self.assertEqual(1, len(self.calls))

    def test_if_action_before_and_after_during(self):
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_RISING: '10:00:00 16-09-2015',
            sun.STATE_ATTR_NEXT_SETTING: '15:00:00 16-09-2015',
        })

        automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': {
                    'platform': 'sun',
                    'after': 'sunrise',
                    'before': 'sunset'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        now = datetime(2015, 9, 16, 9, 59, tzinfo=dt_util.UTC)
        with patch('homeassistant.components.automation.sun.dt_util.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 15, 1, tzinfo=dt_util.UTC)
        with patch('homeassistant.components.automation.sun.dt_util.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 12, tzinfo=dt_util.UTC)
        with patch('homeassistant.components.automation.sun.dt_util.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.pool.block_till_done()
            self.assertEqual(1, len(self.calls))
