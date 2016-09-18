"""The tests for the sun automation."""
from datetime import datetime
import unittest
from unittest.mock import patch

from homeassistant.bootstrap import _setup_component
from homeassistant.components import sun
import homeassistant.components.automation as automation
import homeassistant.util.dt as dt_util

from tests.common import fire_time_changed, get_test_home_assistant


class TestAutomationSun(unittest.TestCase):
    """Test the sun automation."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.components.append('group')
        self.hass.config.components.append('sun')

        self.calls = []

        def record_call(service):
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_sunset_trigger(self):
        """Test the sunset trigger."""
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_SETTING: '2015-09-16T02:00:00Z',
        })

        now = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
        trigger_time = datetime(2015, 9, 16, 2, tzinfo=dt_util.UTC)

        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            _setup_component(self.hass, automation.DOMAIN, {
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
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_RISING: '2015-09-16T14:00:00Z',
        })

        now = datetime(2015, 9, 13, 23, tzinfo=dt_util.UTC)
        trigger_time = datetime(2015, 9, 16, 14, tzinfo=dt_util.UTC)

        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            _setup_component(self.hass, automation.DOMAIN, {
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
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_SETTING: '2015-09-16T02:00:00Z',
        })

        now = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
        trigger_time = datetime(2015, 9, 16, 2, 30, tzinfo=dt_util.UTC)

        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            _setup_component(self.hass, automation.DOMAIN, {
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
        """Test the runrise trigger with offset."""
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_RISING: '2015-09-16T14:00:00Z',
        })

        now = datetime(2015, 9, 13, 23, tzinfo=dt_util.UTC)
        trigger_time = datetime(2015, 9, 16, 13, 30, tzinfo=dt_util.UTC)

        with patch('homeassistant.util.dt.utcnow',
                   return_value=now):
            _setup_component(self.hass, automation.DOMAIN, {
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
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_RISING: '2015-09-16T14:00:00Z',
        })

        _setup_component(self.hass, automation.DOMAIN, {
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
        with patch('homeassistant.util.dt.now',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 10, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.now',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(1, len(self.calls))

    def test_if_action_after(self):
        """Test if action was after."""
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_RISING: '2015-09-16T14:00:00Z',
        })

        _setup_component(self.hass, automation.DOMAIN, {
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
        with patch('homeassistant.util.dt.now',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 15, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.now',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(1, len(self.calls))

    def test_if_action_before_with_offset(self):
        """Test if action was before offset."""
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_RISING: '2015-09-16T14:00:00Z',
        })

        _setup_component(self.hass, automation.DOMAIN, {
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
        with patch('homeassistant.util.dt.now',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 15, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.now',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(1, len(self.calls))

    def test_if_action_after_with_offset(self):
        """Test if action was after offset."""
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_RISING: '2015-09-16T14:00:00Z',
        })

        _setup_component(self.hass, automation.DOMAIN, {
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
        with patch('homeassistant.util.dt.now',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 15, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.now',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(1, len(self.calls))

    def test_if_action_before_and_after_during(self):
        """Test if action was before and after during."""
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_RISING: '2015-09-16T10:00:00Z',
            sun.STATE_ATTR_NEXT_SETTING: '2015-09-16T15:00:00Z',
        })

        _setup_component(self.hass, automation.DOMAIN, {
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
        with patch('homeassistant.util.dt.now',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 15, 1, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.now',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(0, len(self.calls))

        now = datetime(2015, 9, 16, 12, tzinfo=dt_util.UTC)
        with patch('homeassistant.util.dt.now',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(1, len(self.calls))

    def test_if_action_after_different_tz(self):
        """Test if action was after in a different timezone."""
        import pytz

        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON, {
            sun.STATE_ATTR_NEXT_SETTING: '2015-09-16T17:30:00Z',
        })

        _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': {
                    'platform': 'sun',
                    'after': 'sunset',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        # Before
        now = datetime(2015, 9, 16, 17, tzinfo=pytz.timezone('US/Mountain'))
        with patch('homeassistant.util.dt.now',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(0, len(self.calls))

        # After
        now = datetime(2015, 9, 16, 18, tzinfo=pytz.timezone('US/Mountain'))
        with patch('homeassistant.util.dt.now',
                   return_value=now):
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(1, len(self.calls))
