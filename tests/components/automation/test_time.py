"""The tests for the time automation."""
from datetime import timedelta
import unittest
from unittest.mock import patch

from homeassistant.core import callback
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util
import homeassistant.components.automation as automation

from tests.common import (
    fire_time_changed, get_test_home_assistant, assert_setup_component,
    mock_component)
from tests.components.automation import common


# pylint: disable=invalid-name
class TestAutomationTime(unittest.TestCase):
    """Test the event automation."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_component(self.hass, 'group')
        self.calls = []

        @callback
        def record_call(service):
            """Record calls."""
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_if_fires_when_hour_matches(self):
        """Test for firing if hour is matching."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'time',
                    'hours': 0,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        fire_time_changed(self.hass, dt_util.utcnow().replace(hour=0))
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

        common.turn_off(self.hass)
        self.hass.block_till_done()

        fire_time_changed(self.hass, dt_util.utcnow().replace(hour=0))
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_when_minute_matches(self):
        """Test for firing if minutes are matching."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'time',
                    'minutes': 0,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        fire_time_changed(self.hass, dt_util.utcnow().replace(minute=0))

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_when_second_matches(self):
        """Test for firing if seconds are matching."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'time',
                    'seconds': 0,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        fire_time_changed(self.hass, dt_util.utcnow().replace(second=0))

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_when_all_matches(self):
        """Test for firing if everything matches."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'time',
                    'hours': 1,
                    'minutes': 2,
                    'seconds': 3,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        fire_time_changed(self.hass, dt_util.utcnow().replace(
            hour=1, minute=2, second=3))

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_periodic_seconds(self):
        """Test for firing periodically every second."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'time',
                    'seconds': "/2",
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        fire_time_changed(self.hass, dt_util.utcnow().replace(
            hour=0, minute=0, second=2))

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_periodic_minutes(self):
        """Test for firing periodically every minute."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'time',
                    'minutes': "/2",
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        fire_time_changed(self.hass, dt_util.utcnow().replace(
            hour=0, minute=2, second=0))

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_periodic_hours(self):
        """Test for firing periodically every hour."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'time',
                    'hours': "/2",
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        fire_time_changed(self.hass, dt_util.utcnow().replace(
            hour=2, minute=0, second=0))

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_using_at(self):
        """Test for firing at."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'time',
                    'at': '5:00:00',
                },
                'action': {
                    'service': 'test.automation',
                    'data_template': {
                        'some': '{{ trigger.platform }} - '
                                '{{ trigger.now.hour }}'
                    },
                }
            }
        })

        fire_time_changed(self.hass, dt_util.utcnow().replace(
            hour=5, minute=0, second=0))

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('time - 5', self.calls[0].data['some'])

    def test_if_not_working_if_no_values_in_conf_provided(self):
        """Test for failure if no configuration."""
        with assert_setup_component(0):
            assert setup_component(self.hass, automation.DOMAIN, {
                automation.DOMAIN: {
                    'trigger': {
                        'platform': 'time',
                    },
                    'action': {
                        'service': 'test.automation'
                    }
                }
            })

        fire_time_changed(self.hass, dt_util.utcnow().replace(
            hour=5, minute=0, second=0))

        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_not_fires_using_wrong_at(self):
        """YAML translates time values to total seconds.

        This should break the before rule.
        """
        with assert_setup_component(0):
            assert setup_component(self.hass, automation.DOMAIN, {
                automation.DOMAIN: {
                    'trigger': {
                        'platform': 'time',
                        'at': 3605,
                        # Total seconds. Hour = 3600 second
                    },
                    'action': {
                        'service': 'test.automation'
                    }
                }
            })

        fire_time_changed(self.hass, dt_util.utcnow().replace(
            hour=1, minute=0, second=5))

        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_action_before(self):
        """Test for if action before."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event'
                },
                'condition': {
                    'condition': 'time',
                    'before': '10:00',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        before_10 = dt_util.now().replace(hour=8)
        after_10 = dt_util.now().replace(hour=14)

        with patch('homeassistant.helpers.condition.dt_util.now',
                   return_value=before_10):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))

        with patch('homeassistant.helpers.condition.dt_util.now',
                   return_value=after_10):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))

    def test_if_action_after(self):
        """Test for if action after."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event'
                },
                'condition': {
                    'condition': 'time',
                    'after': '10:00',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        before_10 = dt_util.now().replace(hour=8)
        after_10 = dt_util.now().replace(hour=14)

        with patch('homeassistant.helpers.condition.dt_util.now',
                   return_value=before_10):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()

        self.assertEqual(0, len(self.calls))

        with patch('homeassistant.helpers.condition.dt_util.now',
                   return_value=after_10):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))

    def test_if_action_one_weekday(self):
        """Test for if action with one weekday."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event'
                },
                'condition': {
                    'condition': 'time',
                    'weekday': 'mon',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        days_past_monday = dt_util.now().weekday()
        monday = dt_util.now() - timedelta(days=days_past_monday)
        tuesday = monday + timedelta(days=1)

        with patch('homeassistant.helpers.condition.dt_util.now',
                   return_value=monday):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))

        with patch('homeassistant.helpers.condition.dt_util.now',
                   return_value=tuesday):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))

    def test_if_action_list_weekday(self):
        """Test for action with a list of weekdays."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event'
                },
                'condition': {
                    'condition': 'time',
                    'weekday': ['mon', 'tue'],
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        days_past_monday = dt_util.now().weekday()
        monday = dt_util.now() - timedelta(days=days_past_monday)
        tuesday = monday + timedelta(days=1)
        wednesday = tuesday + timedelta(days=1)

        with patch('homeassistant.helpers.condition.dt_util.now',
                   return_value=monday):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))

        with patch('homeassistant.helpers.condition.dt_util.now',
                   return_value=tuesday):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()

        self.assertEqual(2, len(self.calls))

        with patch('homeassistant.helpers.condition.dt_util.now',
                   return_value=wednesday):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()

        self.assertEqual(2, len(self.calls))
