"""The tests for the sun automation."""
from datetime import datetime

import unittest
from unittest.mock import patch

from homeassistant.core import callback
from homeassistant.setup import setup_component
from homeassistant.components import sun
import homeassistant.components.automation as automation
import homeassistant.util.dt as dt_util

from tests.common import (
    fire_time_changed, get_test_home_assistant, mock_component)


# pylint: disable=invalid-name
class TestAutomationSun(unittest.TestCase):
    """Test the sun automation."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_component(self.hass, 'group')
        setup_component(self.hass, sun.DOMAIN, {
            sun.DOMAIN: {sun.CONF_ELEVATION: 0}})

        self.calls = []

        @callback
        def record_call(service):
            """Call recorder."""
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_sunset_trigger(self):
        """Test the sunset trigger."""
        now = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
        trigger_time = datetime(2015, 9, 16, 2, tzinfo=dt_util.UTC)

        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            setup_component(self.hass, automation.DOMAIN, {
                automation.DOMAIN: {
                    'trigger': {
                        'platform': 'sun',
                        'event': 'sunset',
                    },
                    'action': {
                        'service': 'test.automation',
                    }
                }
            })

        automation.turn_off(self.hass)
        self.hass.block_till_done()

        fire_time_changed(self.hass, trigger_time)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            automation.turn_on(self.hass)
            self.hass.block_till_done()

        fire_time_changed(self.hass, trigger_time)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_sunrise_trigger(self):
        """Test the sunrise trigger."""
        now = datetime(2015, 9, 13, 23, tzinfo=dt_util.UTC)
        trigger_time = datetime(2015, 9, 16, 14, tzinfo=dt_util.UTC)

        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            setup_component(self.hass, automation.DOMAIN, {
                automation.DOMAIN: {
                    'trigger': {
                        'platform': 'sun',
                        'event': 'sunrise',
                    },
                    'action': {
                        'service': 'test.automation',
                    }
                }
            })

        fire_time_changed(self.hass, trigger_time)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_sunset_trigger_with_offset(self):
        """Test the sunset trigger with offset."""
        now = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
        trigger_time = datetime(2015, 9, 16, 2, 30, tzinfo=dt_util.UTC)

        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            setup_component(self.hass, automation.DOMAIN, {
                automation.DOMAIN: {
                    'trigger': {
                        'platform': 'sun',
                        'event': 'sunset',
                        'offset': '0:30:00'
                    },
                    'action': {
                        'service': 'test.automation',
                        'data_template': {
                            'some':
                            '{{ trigger.%s }}' % '}} - {{ trigger.'.join((
                                'platform', 'event', 'offset'))
                        },
                    }
                }
            })

        fire_time_changed(self.hass, trigger_time)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('sun - sunset - 0:30:00', self.calls[0].data['some'])

    def test_sunrise_trigger_with_offset(self):
        """Test the sunrise trigger with offset."""
        now = datetime(2015, 9, 13, 23, tzinfo=dt_util.UTC)
        trigger_time = datetime(2015, 9, 16, 13, 30, tzinfo=dt_util.UTC)

        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            setup_component(self.hass, automation.DOMAIN, {
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
            })

        fire_time_changed(self.hass, trigger_time)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_action_before(self):
        """Test if action was before."""
        setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': {
                    'condition': 'sun',
                    'before': 'sunrise',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        now = datetime(2015, 9, 16, 15, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 10, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(1, len(self.calls))

    def test_if_action_after(self):
        """Test if action was after."""
        setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': {
                    'condition': 'sun',
                    'after': 'sunrise',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        now = datetime(2015, 9, 16, 13, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 15, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(1, len(self.calls))

    def test_if_action_before_with_offset(self):
        """Test if action was before offset."""
        setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': {
                    'condition': 'sun',
                    'before': 'sunrise',
                    'before_offset': '+1:00:00'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        now = datetime(2015, 9, 16, 14, 32, 44, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 14, 32, 43, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(1, len(self.calls))

    def test_if_action_after_with_offset(self):
        """Test if action was after offset."""
        setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': {
                    'condition': 'sun',
                    'after': 'sunrise',
                    'after_offset': '+1:00:00'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        now = datetime(2015, 9, 16, 14, 32, 42, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 14, 32, 43, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(1, len(self.calls))

    def test_if_action_before_and_after_during(self):
        """Test if action was before and after during."""
        setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': {
                    'condition': 'sun',
                    'after': 'sunrise',
                    'before': 'sunset'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        now = datetime(2015, 9, 16, 13, 8, 51, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 17, 2, 25, 18, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 16, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(1, len(self.calls))
