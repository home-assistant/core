"""The tests for the time automation."""
import unittest
from unittest.mock import patch

from homeassistant.core import callback
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.dt import parse_datetime
import homeassistant.components.automation as automation

from tests.common import (
    fire_time_changed, get_test_home_assistant, mock_component)

PATCH_DATETIME = parse_datetime('2018-04-01T11:30:00-04:00')


# pylint: disable=invalid-name
class TestAutomationSchedule(unittest.TestCase):
    """Test the event automation."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        # Switch timezone to New York so we make sure things work as expected
        self.DEFAULT_TIME_ZONE = dt_util.DEFAULT_TIME_ZONE
        self.new_tz = dt_util.get_time_zone('America/New_York')
        assert self.new_tz is not None
        dt_util.set_default_time_zone(self.new_tz)

        mock_component(self.hass, 'group')
        self.calls = []

        @callback
        def record_call(service):
            """Helper to record calls."""
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):
        """Stop everything that was started."""
        dt_util.set_default_time_zone(self.DEFAULT_TIME_ZONE)
        self.hass.stop()

    @patch('homeassistant.util.dt.now', return_value=PATCH_DATETIME)
    def test_schedule_basics(self, _):
        """Test basic operation."""
        setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'schedule',
                    'schedule': 'Mon-Sun: 11:00, 12:00'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        # Although we set up at 11:30 it shouldn't have fired the 11:00 job
        self.assertEqual(0, len(self.calls))

        # Moving to 12:30 should trigger the 12:00 job
        fire_time_changed(self.hass, parse_datetime('2018-04-01T12:30-04:00'))
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

        # Moving to 01:00 the next day shouldn't trigger anything
        fire_time_changed(self.hass, parse_datetime('2018-04-02T01:00-04:00'))
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

        # Moving to 12:30 then should trigger both jobs
        fire_time_changed(self.hass, parse_datetime('2018-04-02T12:30-04:00'))
        self.hass.block_till_done()
        self.assertEqual(3, len(self.calls))

    @patch('homeassistant.util.dt.now', return_value=PATCH_DATETIME)
    def test_midnight_edge_case(self, _):
        """Ensure events at midnight work as we do special things then."""
        setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'schedule',
                    'schedule': 'Mon-Sun: 00:00'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.assertEqual(0, len(self.calls))

        # Moving to the next day should fire the job
        fire_time_changed(self.hass, parse_datetime('2018-04-02T01:00-04:00'))
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    @patch('homeassistant.util.dt.now', return_value=PATCH_DATETIME)
    def test_data_passed_to_action_context(self, _):
        """Test  the data available for actions."""
        setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'schedule',
                    'schedule': 'Mon-Sun: 11:00=a, 12:00=b'
                },
                'action': {
                    'service': 'test.automation',
                    'data_template': {
                        'some': '{{ trigger.platform }} - '
                                '{{ trigger.now }} = '
                                '{{ trigger.schedule_state }}'
                    },
                }
            }
        })

        # Although we set up at 11:30 it shouldn't have fired the 11:00 job
        self.assertEqual(0, len(self.calls))

        fire_time_changed(self.hass, parse_datetime('2018-04-01T12:30-04:00'))
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('schedule - 2018-04-01 12:30:00-04:00 = b',
                         self.calls[0].data['some'])
