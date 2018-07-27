"""The tests for the google calendar component."""
# pylint: disable=protected-access
import logging
import unittest
from unittest.mock import patch, Mock

import pytest

import homeassistant.components.calendar as calendar_base
import homeassistant.components.calendar.google as calendar
import homeassistant.util.dt as dt_util
from homeassistant.const import CONF_PLATFORM, STATE_OFF, STATE_ON
from homeassistant.helpers.template import DATE_STR_FORMAT
from tests.common import get_test_home_assistant, MockDependency

TEST_PLATFORM = {calendar_base.DOMAIN: {CONF_PLATFORM: 'test'}}

_LOGGER = logging.getLogger(__name__)


class TestComponentsGoogleCalendar(unittest.TestCase):
    """Test the Google calendar."""

    hass = None  # HomeAssistant

    # pylint: disable=invalid-name
    def setUp(self):
        """Setup things to be run when tests are started."""
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

    @patch('homeassistant.components.calendar.google.GoogleCalendarData')
    def test_all_day_event(self, mock_next_event):
        """Test that we can create an event trigger on device."""
        week_from_today = dt_util.dt.date.today() \
            + dt_util.dt.timedelta(days=7)
        event = {
            'summary': 'Test All Day Event',
            'start': {
                'date': week_from_today.isoformat()
            },
            'end': {
                'date': (week_from_today + dt_util.dt.timedelta(days=1))
                .isoformat()
            },
            'location': 'Test Cases',
            'description': 'We\'re just testing that all day events get setup '
                           'correctly',
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

        mock_next_event.return_value.event = event

        device_name = 'Test All Day'

        cal = calendar.GoogleCalendarEventDevice(self.hass, None,
                                                 '', {'name': device_name})

        self.assertEqual(cal.name, device_name)

        self.assertEqual(cal.state, STATE_OFF)

        self.assertFalse(cal.offset_reached())

        self.assertEqual(cal.device_state_attributes, {
            'message': event['summary'],
            'all_day': True,
            'offset_reached': False,
            'start_time': '{} 00:00:00'.format(event['start']['date']),
            'end_time': '{} 00:00:00'.format(event['end']['date']),
            'location': event['location'],
            'description': event['description'],
        })

    @patch('homeassistant.components.calendar.google.GoogleCalendarData')
    def test_future_event(self, mock_next_event):
        """Test that we can create an event trigger on device."""
        one_hour_from_now = dt_util.now() \
            + dt_util.dt.timedelta(minutes=30)
        event = {
            'start': {
                'dateTime': one_hour_from_now.isoformat()
            },
            'end': {
                'dateTime': (one_hour_from_now
                             + dt_util.dt.timedelta(minutes=60))
                .isoformat()
            },
            'summary': 'Test Event in 30 minutes',
            'reminders': {'useDefault': True},
            'id': 'aioehgni435lihje',
            'status': 'confirmed',
            'updated': '2016-11-05T15:52:07.329Z',
            'organizer': {
                'email': 'uvrttabwegnui4gtia3vyqb@import.calendar.google.com',
                'displayName': 'Organizer Name',
                'self': True,
            },
            'created': '2016-11-05T15:52:07.000Z',
            'iCalUID': 'dsfohuygtfvgbhnuju@google.com',
            'sequence': 0,
            'creator': {
                'email': 'uvrttabwegnui4gtia3vyqb@import.calendar.google.com',
                'displayName': 'Organizer Name',
            },
            'etag': '"2956722254658000"',
            'kind': 'calendar#event',
            'htmlLink': 'https://www.google.com/calendar/event?eid=*******',
        }
        mock_next_event.return_value.event = event

        device_name = 'Test Future Event'
        device_id = 'test_future_event'

        cal = calendar.GoogleCalendarEventDevice(self.hass, None, device_id,
                                                 {'name': device_name})

        self.assertEqual(cal.name, device_name)

        self.assertEqual(cal.state, STATE_OFF)

        self.assertFalse(cal.offset_reached())

        self.assertEqual(cal.device_state_attributes, {
            'message': event['summary'],
            'all_day': False,
            'offset_reached': False,
            'start_time': one_hour_from_now.strftime(DATE_STR_FORMAT),
            'end_time':
                (one_hour_from_now + dt_util.dt.timedelta(minutes=60))
                .strftime(DATE_STR_FORMAT),
            'location': '',
            'description': '',
        })

    @patch('homeassistant.components.calendar.google.GoogleCalendarData')
    def test_in_progress_event(self, mock_next_event):
        """Test that we can create an event trigger on device."""
        middle_of_event = dt_util.now() \
            - dt_util.dt.timedelta(minutes=30)
        event = {
            'start': {
                'dateTime': middle_of_event.isoformat()
            },
            'end': {
                'dateTime': (middle_of_event + dt_util.dt
                             .timedelta(minutes=60))
                .isoformat()
            },
            'summary': 'Test Event in Progress',
            'reminders': {'useDefault': True},
            'id': 'aioehgni435lihje',
            'status': 'confirmed',
            'updated': '2016-11-05T15:52:07.329Z',
            'organizer': {
                'email': 'uvrttabwegnui4gtia3vyqb@import.calendar.google.com',
                'displayName': 'Organizer Name',
                'self': True,
            },
            'created': '2016-11-05T15:52:07.000Z',
            'iCalUID': 'dsfohuygtfvgbhnuju@google.com',
            'sequence': 0,
            'creator': {
                'email': 'uvrttabwegnui4gtia3vyqb@import.calendar.google.com',
                'displayName': 'Organizer Name',
            },
            'etag': '"2956722254658000"',
            'kind': 'calendar#event',
            'htmlLink': 'https://www.google.com/calendar/event?eid=*******',
        }

        mock_next_event.return_value.event = event

        device_name = 'Test Event in Progress'
        device_id = 'test_event_in_progress'

        cal = calendar.GoogleCalendarEventDevice(self.hass, None, device_id,
                                                 {'name': device_name})

        self.assertEqual(cal.name, device_name)

        self.assertEqual(cal.state, STATE_ON)

        self.assertFalse(cal.offset_reached())

        self.assertEqual(cal.device_state_attributes, {
            'message': event['summary'],
            'all_day': False,
            'offset_reached': False,
            'start_time': middle_of_event.strftime(DATE_STR_FORMAT),
            'end_time':
                (middle_of_event + dt_util.dt.timedelta(minutes=60))
                .strftime(DATE_STR_FORMAT),
            'location': '',
            'description': '',
        })

    @patch('homeassistant.components.calendar.google.GoogleCalendarData')
    def test_offset_in_progress_event(self, mock_next_event):
        """Test that we can create an event trigger on device."""
        middle_of_event = dt_util.now() \
            + dt_util.dt.timedelta(minutes=14)
        event_summary = 'Test Event in Progress'
        event = {
            'start': {
                'dateTime': middle_of_event.isoformat()
            },
            'end': {
                'dateTime': (middle_of_event + dt_util.dt
                             .timedelta(minutes=60))
                .isoformat()
            },
            'summary': '{} !!-15'.format(event_summary),
            'reminders': {'useDefault': True},
            'id': 'aioehgni435lihje',
            'status': 'confirmed',
            'updated': '2016-11-05T15:52:07.329Z',
            'organizer': {
                'email': 'uvrttabwegnui4gtia3vyqb@import.calendar.google.com',
                'displayName': 'Organizer Name',
                'self': True,
            },
            'created': '2016-11-05T15:52:07.000Z',
            'iCalUID': 'dsfohuygtfvgbhnuju@google.com',
            'sequence': 0,
            'creator': {
                'email': 'uvrttabwegnui4gtia3vyqb@import.calendar.google.com',
                'displayName': 'Organizer Name',
            },
            'etag': '"2956722254658000"',
            'kind': 'calendar#event',
            'htmlLink': 'https://www.google.com/calendar/event?eid=*******',
        }

        mock_next_event.return_value.event = event

        device_name = 'Test Event in Progress'
        device_id = 'test_event_in_progress'

        cal = calendar.GoogleCalendarEventDevice(self.hass, None, device_id,
                                                 {'name': device_name})

        self.assertEqual(cal.name, device_name)

        self.assertEqual(cal.state, STATE_OFF)

        self.assertTrue(cal.offset_reached())

        self.assertEqual(cal.device_state_attributes, {
            'message': event_summary,
            'all_day': False,
            'offset_reached': True,
            'start_time': middle_of_event.strftime(DATE_STR_FORMAT),
            'end_time':
                (middle_of_event + dt_util.dt.timedelta(minutes=60))
                .strftime(DATE_STR_FORMAT),
            'location': '',
            'description': '',
        })

    @pytest.mark.skip
    @patch('homeassistant.components.calendar.google.GoogleCalendarData')
    def test_all_day_offset_in_progress_event(self, mock_next_event):
        """Test that we can create an event trigger on device."""
        tomorrow = dt_util.dt.date.today() \
            + dt_util.dt.timedelta(days=1)

        event_summary = 'Test All Day Event Offset In Progress'
        event = {
            'summary': '{} !!-25:0'.format(event_summary),
            'start': {
                'date': tomorrow.isoformat()
            },
            'end': {
                'date': (tomorrow + dt_util.dt.timedelta(days=1))
                .isoformat()
            },
            'location': 'Test Cases',
            'description': 'We\'re just testing that all day events get setup '
                           'correctly',
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

        mock_next_event.return_value.event = event

        device_name = 'Test All Day Offset In Progress'
        device_id = 'test_all_day_offset_in_progress'

        cal = calendar.GoogleCalendarEventDevice(self.hass, None, device_id,
                                                 {'name': device_name})

        self.assertEqual(cal.name, device_name)

        self.assertEqual(cal.state, STATE_OFF)

        self.assertTrue(cal.offset_reached())

        self.assertEqual(cal.device_state_attributes, {
            'message': event_summary,
            'all_day': True,
            'offset_reached': True,
            'start_time': '{} 06:00:00'.format(event['start']['date']),
            'end_time': '{} 06:00:00'.format(event['end']['date']),
            'location': event['location'],
            'description': event['description'],
        })

    @patch('homeassistant.components.calendar.google.GoogleCalendarData')
    def test_all_day_offset_event(self, mock_next_event):
        """Test that we can create an event trigger on device."""
        tomorrow = dt_util.dt.date.today() \
            + dt_util.dt.timedelta(days=2)

        offset_hours = (1 + dt_util.now().hour)
        event_summary = 'Test All Day Event Offset'
        event = {
            'summary': '{} !!-{}:0'.format(event_summary, offset_hours),
            'start': {
                'date': tomorrow.isoformat()
            },
            'end': {
                'date': (tomorrow + dt_util.dt.timedelta(days=1))
                .isoformat()
            },
            'location': 'Test Cases',
            'description': 'We\'re just testing that all day events get setup '
                           'correctly',
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

        mock_next_event.return_value.event = event

        device_name = 'Test All Day Offset'
        device_id = 'test_all_day_offset'

        cal = calendar.GoogleCalendarEventDevice(self.hass, None, device_id,
                                                 {'name': device_name})

        self.assertEqual(cal.name, device_name)

        self.assertEqual(cal.state, STATE_OFF)

        self.assertFalse(cal.offset_reached())

        self.assertEqual(cal.device_state_attributes, {
            'message': event_summary,
            'all_day': True,
            'offset_reached': False,
            'start_time': '{} 00:00:00'.format(event['start']['date']),
            'end_time': '{} 00:00:00'.format(event['end']['date']),
            'location': event['location'],
            'description': event['description'],
        })

    @MockDependency("httplib2")
    def test_update_false(self, mock_httplib2):
        """Test that the update returns False upon Error."""
        mock_service = Mock()
        mock_service.get = Mock(
            side_effect=mock_httplib2.ServerNotFoundError("unit test"))

        cal = calendar.GoogleCalendarEventDevice(self.hass, mock_service, None,
                                                 {'name': "test"})
        result = cal.data.update()

        self.assertFalse(result)
