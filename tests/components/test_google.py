"""The tests for the Google Calendar component."""
import logging
import unittest
from unittest.mock import patch

import homeassistant.components.google as google
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant

_LOGGER = logging.getLogger(__name__)


class TestGoogle(unittest.TestCase):
    """Test the Google component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @patch('homeassistant.components.google.do_authentication')
    def test_setup_component(self, mock_do_auth):
        """Test setup component."""
        config = {
            'google': {
                'client_id': 'id',
                'client_secret': 'secret',
            }
        }

        self.assertTrue(setup_component(self.hass, 'google', config))

    def test_get_calendar_info(self):
        """Test getting the calendar info."""
        calendar = {
            'id': 'qwertyuiopasdfghjklzxcvbnm@import.calendar.google.com',
            'etag': '"3584134138943410"',
            'timeZone': 'UTC',
            'accessRole': 'reader',
            'foregroundColor': '#000000',
            'selected': True,
            'kind': 'calendar#calendarListEntry',
            'backgroundColor': '#16a765',
            'description': 'Test Calendar',
            'summary': 'We are, we are, a... Test Calendar',
            'colorId': '8',
            'defaultReminders': [],
            'track': True
        }

        calendar_info = google.get_calendar_info(self.hass, calendar)
        self.assertEqual(calendar_info, {
            'cal_id': 'qwertyuiopasdfghjklzxcvbnm@import.calendar.google.com',
            'entities': [{
                'device_id': 'we_are_we_are_a_test_calendar',
                'name': 'We are, we are, a... Test Calendar',
                'track': True,
                'ignore_availability': True,
            }]
        })

    def test_found_calendar(self):
        """Test when a calendar is found."""
        # calendar = {
        #     'id': 'qwertyuiopasdfghjklzxcvbnm@import.calendar.google.com',
        #     'etag': '"3584134138943410"',
        #     'timeZone': 'UTC',
        #     'accessRole': 'reader',
        #     'foregroundColor': '#000000',
        #     'selected': True,
        #     'kind': 'calendar#calendarListEntry',
        #     'backgroundColor': '#16a765',
        #     'description': 'Test Calendar',
        #     'summary': 'We are, we are, a... Test Calendar',
        #     'colorId': '8',
        #     'defaultReminders': [],
        #     'track': True
        # }

        # self.assertIsInstance(self.hass.data[google.DATA_INDEX], dict)
        # self.assertEqual(self.hass.data[google.DATA_INDEX], {})

        calendar_service = google.GoogleCalendarService(
            self.hass.config.path(google.TOKEN_FILE))
        self.assertTrue(google.setup_services(self.hass, True,
                                              calendar_service))
        # self.hass.services.call('google', 'found_calendar', calendar,
        #                         blocking=True)

        # TODO: Fix this
        # self.assertTrue(self.hass.data[google.DATA_INDEX]
        #   # .get(calendar['id'], None) is not None)
