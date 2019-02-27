"""The tests for the google calendar component."""
# pylint: disable=protected-access
import copy
import unittest
from unittest.mock import patch, Mock

import homeassistant.components.calendar as calendar_base
from homeassistant.components.google import calendar
import homeassistant.util.dt as dt_util
from homeassistant.const import CONF_PLATFORM, STATE_OFF, STATE_ON
from tests.common import get_test_home_assistant, MockDependency

TEST_PLATFORM = {calendar_base.DOMAIN: {CONF_PLATFORM: 'test'}}

TEST_EVENT = {
    'summary': 'Test Event',
    'start': {
    },
    'end': {
    },
    'location': 'Test Cases',
    'description': 'test event',
    'kind': 'calendar#event',
    'created': '2016-06-23T16:37:57.000Z',
    'transparency': 'transparent',
    'updated': '2016-06-24T01:57:21.045Z',
    'reminders': {'useDefault': True},
    'organizer': {
        'email': 'uvrttabwegnui4gtia3vyqb@import.calendar.google.com',
        'displayName': 'Organizer Name',
        'self': True
    },
    'sequence': 0,
    'creator': {
        'email': 'uvrttabwegnui4gtia3vyqb@import.calendar.google.com',
        'displayName': 'Organizer Name',
        'self': True
    },
    'id': '_c8rinwq863h45qnucyoi43ny8',
    'etag': '"2933466882090000"',
    'htmlLink': 'https://www.google.com/calendar/event?eid=*******',
    'iCalUID': 'cydrevtfuybguinhomj@google.com',
    'status': 'confirmed'
}


class TestComponentsGoogleCalendar(unittest.TestCase):
    """Test the Google calendar."""

    hass = None  # HomeAssistant

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.http = Mock()

        # Set our timezone to CST/Regina so we can check calculations
        # This keeps UTC-6 all year round
        dt_util.set_default_time_zone(dt_util.get_time_zone('America/Regina'))

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        dt_util.set_default_time_zone(dt_util.get_time_zone('UTC'))

        self.hass.stop()

    @patch('homeassistant.components.google.calendar.GoogleCalendarData')
    def test_all_day_event(self, mock_next_event):
        """Test an all day event."""
        week_from_today = dt_util.dt.date.today() \
            + dt_util.dt.timedelta(days=7)

        event = copy.deepcopy(TEST_EVENT)
        event['start']['date'] = week_from_today.isoformat()
        event['end']['date'] = (week_from_today
                                + dt_util.dt.timedelta(days=1)).isoformat()

        mock_next_event.return_value.event = event
        device_name = 'Test All Day'

        cal = calendar.GoogleCalendarEventDevice(self.hass, None,
                                                 '', {'name': device_name})

        assert cal.name == device_name
        assert cal.state == STATE_OFF
        assert cal.device_state_attributes['all_day']

    @patch('homeassistant.components.google.calendar.GoogleCalendarData')
    def test_future_event(self, mock_next_event):
        """Test future event with off state."""
        one_hour_from_now = dt_util.now() \
            + dt_util.dt.timedelta(minutes=30)

        hour_delta = dt_util.dt.timedelta(minutes=60)

        event = copy.deepcopy(TEST_EVENT)
        event['start']['dateTime'] = one_hour_from_now.isoformat()
        event['end']['dateTime'] = (one_hour_from_now
                                    + hour_delta).isoformat()

        mock_next_event.return_value.event = event
        device_name = 'Test Future Event'
        device_id = 'test_future_event'

        cal = calendar.GoogleCalendarEventDevice(self.hass, None, device_id,
                                                 {'name': device_name})

        assert cal.name == device_name
        assert cal.state == STATE_OFF
        assert not cal.device_state_attributes['all_day']

    @patch('homeassistant.components.google.calendar.GoogleCalendarData')
    def test_in_progress_event(self, mock_next_event):
        """Test an ongoing event with on state."""
        middle_of_event = dt_util.now() \
            - dt_util.dt.timedelta(minutes=30)

        hour_delta = dt_util.dt.timedelta(minutes=60)

        event = copy.deepcopy(TEST_EVENT)
        event['start']['dateTime'] = middle_of_event.isoformat()
        event['end']['dateTime'] = (middle_of_event
                                    + hour_delta).isoformat()

        mock_next_event.return_value.event = event

        device_name = 'Test Event in Progress'
        device_id = 'test_event_in_progress'

        cal = calendar.GoogleCalendarEventDevice(self.hass, None, device_id,
                                                 {'name': device_name})

        assert cal.name == device_name
        assert cal.state == STATE_ON

    @MockDependency("httplib2")
    def test_update_false(self, mock_httplib2):
        """Test that the update returns False upon Error."""
        mock_service = Mock()
        mock_service.get = Mock(
            side_effect=mock_httplib2.ServerNotFoundError("unit test"))

        cal = calendar.GoogleCalendarEventDevice(self.hass, mock_service, None,
                                                 {'name': "test"})
        result = cal.data.update()

        assert not result
