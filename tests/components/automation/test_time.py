"""The tests for the time automation."""
from datetime import timedelta
import unittest
from unittest.mock import patch

from homeassistant.bootstrap import _setup_component
import homeassistant.util.dt as dt_util
import homeassistant.components.automation as automation

from tests.common import fire_time_changed, get_test_home_assistant


class TestAutomationTime(unittest.TestCase):
    """Test the event automation."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.components.append('group')
        self.calls = []

        def record_call(service):
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_if_fires_when_hour_matches(self):
        """Test for firing if hour is matching."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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

        automation.turn_off(self.hass)
        self.hass.block_till_done()

        fire_time_changed(self.hass, dt_util.utcnow().replace(hour=0))
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_when_minute_matches(self):
        """Test for firing if minutes are matching."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        assert _setup_component(self.hass, automation.DOMAIN, {
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

    def test_if_fires_using_after(self):
        """Test for firing after."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'time',
                    'after': '5:00:00',
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
        assert not _setup_component(self.hass, automation.DOMAIN, {
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

    def test_if_not_fires_using_wrong_after(self):
        """YAML translates time values to total seconds.

        This should break the before rule.
        """
        assert not _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'time',
                    'after': 3605,
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
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event'
                },
                'condition': {
                    'platform': 'time',
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
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event'
                },
                'condition': {
                    'platform': 'time',
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
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event'
                },
                'condition': {
                    'platform': 'time',
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
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event'
                },
                'condition': {
                    'platform': 'time',
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
