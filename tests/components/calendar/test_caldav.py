"""The tests for the webdav calendar component."""
# pylint: disable=protected-access
import datetime
import logging
import unittest
from unittest.mock import (patch, Mock, MagicMock)

import homeassistant.components.calendar as calendar_base
import homeassistant.components.calendar.caldav as caldav
from caldav.objects import Event
from homeassistant.const import CONF_PLATFORM, STATE_OFF, STATE_ON
from homeassistant.util import dt
from tests.common import get_test_home_assistant

TEST_PLATFORM = {calendar_base.DOMAIN: {CONF_PLATFORM: 'test'}}

_LOGGER = logging.getLogger(__name__)


DEVICE_DATA = {
    "name": "Private Calendar",
    "device_id": "Private Calendar",
}

EVENTS = [
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:1
DTSTAMP:20171125T000000Z
DTSTART:20171127T170000Z
DTEND:20171127T180000Z
SUMMARY:This is a normal event
LOCATION:Hamburg
DESCRIPTION:Surprisingly rainy
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Dynamics.//CalDAV Client//EN
BEGIN:VEVENT
UID:2
DTSTAMP:20171125T000000Z
DTSTART:20171127T100000Z
DTEND:20171127T110000Z
SUMMARY:This is an offset event !!-02:00
LOCATION:Hamburg
DESCRIPTION:Surprisingly shiny
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:3
DTSTAMP:20171125T000000Z
DTSTART:20171127
DTEND:20171128
SUMMARY:This is an all day event
LOCATION:Hamburg
DESCRIPTION:What a beautiful day
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:4
DTSTAMP:20171125T000000Z
DTSTART:20171127
SUMMARY:This is an event without dtend or duration
LOCATION:Hamburg
DESCRIPTION:What an endless day
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:5
DTSTAMP:20171125T000000Z
DTSTART:20171127
DURATION:PT1H
SUMMARY:This is an event with duration
LOCATION:Hamburg
DESCRIPTION:What a day
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:6
DTSTAMP:20171125T000000Z
DTSTART:20171127T100000Z
DURATION:PT1H
SUMMARY:This is an event with duration
LOCATION:Hamburg
DESCRIPTION:What a day
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:7
DTSTART;TZID=America/Los_Angeles:20171127T083000
DTSTAMP:20180301T020053Z
DTEND;TZID=America/Los_Angeles:20171127T093000
SUMMARY:Enjoy the sun
LOCATION:San Francisco
DESCRIPTION:Sunny day
END:VEVENT
END:VCALENDAR
"""

]


def _local_datetime(hours, minutes):
    """Build a datetime object for testing in the correct timezone."""
    return dt.as_local(datetime.datetime(2017, 11, 27, hours, minutes, 0))


def _mocked_dav_client(*args, **kwargs):
    """Mock requests.get invocations."""
    calendars = [
        _mock_calendar("First"),
        _mock_calendar("Second")
    ]
    principal = Mock()
    principal.calendars = MagicMock(return_value=calendars)

    client = Mock()
    client.principal = MagicMock(return_value=principal)
    return client


def _mock_calendar(name):
    events = []
    for idx, event in enumerate(EVENTS):
        events.append(Event(None, "%d.ics" % idx, event, None, str(idx)))

    calendar = Mock()
    calendar.date_search = MagicMock(return_value=events)
    calendar.name = name
    return calendar


class TestComponentsWebDavCalendar(unittest.TestCase):
    """Test the WebDav calendar."""

    hass = None  # HomeAssistant

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.http = Mock()
        self.calendar = _mock_calendar("Private")

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('caldav.DAVClient', side_effect=_mocked_dav_client)
    def test_setup_component(self, req_mock):
        """Test setup component with calendars."""
        def _add_device(devices):
            assert len(devices) == 2
            assert devices[0].name == "First"
            assert devices[0].dev_id == "First"
            self.assertFalse(devices[0].data.include_all_day)
            assert devices[1].name == "Second"
            assert devices[1].dev_id == "Second"
            self.assertFalse(devices[1].data.include_all_day)

        caldav.setup_platform(self.hass,
                              {
                                  "url": "http://test.local",
                                  "custom_calendars": []
                              },
                              _add_device)

    @patch('caldav.DAVClient', side_effect=_mocked_dav_client)
    def test_setup_component_with_no_calendar_matching(self, req_mock):
        """Test setup component with wrong calendar."""
        def _add_device(devices):
            assert not devices

        caldav.setup_platform(self.hass,
                              {
                                  "url": "http://test.local",
                                  "calendars": ["none"],
                                  "custom_calendars": []
                              },
                              _add_device)

    @patch('caldav.DAVClient', side_effect=_mocked_dav_client)
    def test_setup_component_with_a_calendar_match(self, req_mock):
        """Test setup component with right calendar."""
        def _add_device(devices):
            assert len(devices) == 1
            assert devices[0].name == "Second"

        caldav.setup_platform(self.hass,
                              {
                                  "url": "http://test.local",
                                  "calendars": ["Second"],
                                  "custom_calendars": []
                              },
                              _add_device)

    @patch('caldav.DAVClient', side_effect=_mocked_dav_client)
    def test_setup_component_with_one_custom_calendar(self, req_mock):
        """Test setup component with custom calendars."""
        def _add_device(devices):
            assert len(devices) == 1
            assert devices[0].name == "HomeOffice"
            assert devices[0].dev_id == "Second HomeOffice"
            self.assertTrue(devices[0].data.include_all_day)

        caldav.setup_platform(self.hass,
                              {
                                  "url": "http://test.local",
                                  "custom_calendars": [
                                      {
                                          "name": "HomeOffice",
                                          "calendar": "Second",
                                          "filter": "HomeOffice"
                                      }]
                              },
                              _add_device)

    @patch('homeassistant.util.dt.now', return_value=_local_datetime(17, 45))
    def test_ongoing_event(self, mock_now):
        """Test that the ongoing event is returned."""
        cal = caldav.WebDavCalendarEventDevice(self.hass,
                                               DEVICE_DATA,
                                               self.calendar)

        self.assertEqual(cal.name, DEVICE_DATA["name"])
        self.assertEqual(cal.state, STATE_ON)
        self.assertEqual(cal.device_state_attributes, {
            "message": "This is a normal event",
            "all_day": False,
            "offset_reached": False,
            "start_time": "2017-11-27 17:00:00",
            "end_time": "2017-11-27 18:00:00",
            "location": "Hamburg",
            "description": "Surprisingly rainy",
        })

    @patch('homeassistant.util.dt.now', return_value=_local_datetime(17, 30))
    def test_just_ended_event(self, mock_now):
        """Test that the next ongoing event is returned."""
        cal = caldav.WebDavCalendarEventDevice(self.hass,
                                               DEVICE_DATA,
                                               self.calendar)

        self.assertEqual(cal.name, DEVICE_DATA["name"])
        self.assertEqual(cal.state, STATE_ON)
        self.assertEqual(cal.device_state_attributes, {
            "message": "This is a normal event",
            "all_day": False,
            "offset_reached": False,
            "start_time": "2017-11-27 17:00:00",
            "end_time": "2017-11-27 18:00:00",
            "location": "Hamburg",
            "description": "Surprisingly rainy",
        })

    @patch('homeassistant.util.dt.now', return_value=_local_datetime(17, 00))
    def test_ongoing_event_different_tz(self, mock_now):
        """Test that the ongoing event with another timezone is returned."""
        cal = caldav.WebDavCalendarEventDevice(self.hass,
                                               DEVICE_DATA,
                                               self.calendar)

        self.assertEqual(cal.name, DEVICE_DATA["name"])
        self.assertEqual(cal.state, STATE_ON)
        self.assertEqual(cal.device_state_attributes, {
            "message": "Enjoy the sun",
            "all_day": False,
            "offset_reached": False,
            "start_time": "2017-11-27 16:30:00",
            "description": "Sunny day",
            "end_time": "2017-11-27 17:30:00",
            "location": "San Francisco",
        })

    @patch('homeassistant.util.dt.now', return_value=_local_datetime(8, 30))
    def test_ongoing_event_with_offset(self, mock_now):
        """Test that the offset is taken into account."""
        cal = caldav.WebDavCalendarEventDevice(self.hass,
                                               DEVICE_DATA,
                                               self.calendar)

        self.assertEqual(cal.state, STATE_OFF)
        self.assertEqual(cal.device_state_attributes, {
            "message": "This is an offset event",
            "all_day": False,
            "offset_reached": True,
            "start_time": "2017-11-27 10:00:00",
            "end_time": "2017-11-27 11:00:00",
            "location": "Hamburg",
            "description": "Surprisingly shiny",
        })

    @patch('homeassistant.util.dt.now', return_value=_local_datetime(12, 00))
    def test_matching_filter(self, mock_now):
        """Test that the matching event is returned."""
        cal = caldav.WebDavCalendarEventDevice(self.hass,
                                               DEVICE_DATA,
                                               self.calendar,
                                               False,
                                               "This is a normal event")

        self.assertEqual(cal.state, STATE_OFF)
        self.assertFalse(cal.offset_reached())
        self.assertEqual(cal.device_state_attributes, {
            "message": "This is a normal event",
            "all_day": False,
            "offset_reached": False,
            "start_time": "2017-11-27 17:00:00",
            "end_time": "2017-11-27 18:00:00",
            "location": "Hamburg",
            "description": "Surprisingly rainy",
        })

    @patch('homeassistant.util.dt.now', return_value=_local_datetime(12, 00))
    def test_matching_filter_real_regexp(self, mock_now):
        """Test that the event matching the regexp is returned."""
        cal = caldav.WebDavCalendarEventDevice(self.hass,
                                               DEVICE_DATA,
                                               self.calendar,
                                               False,
                                               "^This.*event")

        self.assertEqual(cal.state, STATE_OFF)
        self.assertFalse(cal.offset_reached())
        self.assertEqual(cal.device_state_attributes, {
            "message": "This is a normal event",
            "all_day": False,
            "offset_reached": False,
            "start_time": "2017-11-27 17:00:00",
            "end_time": "2017-11-27 18:00:00",
            "location": "Hamburg",
            "description": "Surprisingly rainy",
        })

    @patch('homeassistant.util.dt.now', return_value=_local_datetime(20, 00))
    def test_filter_matching_past_event(self, mock_now):
        """Test that the matching past event is not returned."""
        cal = caldav.WebDavCalendarEventDevice(self.hass,
                                               DEVICE_DATA,
                                               self.calendar,
                                               False,
                                               "This is a normal event")

        self.assertEqual(cal.data.event, None)

    @patch('homeassistant.util.dt.now', return_value=_local_datetime(12, 00))
    def test_no_result_with_filtering(self, mock_now):
        """Test that nothing is returned since nothing matches."""
        cal = caldav.WebDavCalendarEventDevice(self.hass,
                                               DEVICE_DATA,
                                               self.calendar,
                                               False,
                                               "This is a non-existing event")

        self.assertEqual(cal.data.event, None)

    @patch('homeassistant.util.dt.now', return_value=_local_datetime(17, 30))
    def test_all_day_event_returned(self, mock_now):
        """Test that the event lasting the whole day is returned."""
        cal = caldav.WebDavCalendarEventDevice(self.hass,
                                               DEVICE_DATA,
                                               self.calendar,
                                               True)

        self.assertEqual(cal.name, DEVICE_DATA["name"])
        self.assertEqual(cal.state, STATE_ON)
        self.assertEqual(cal.device_state_attributes, {
            "message": "This is an all day event",
            "all_day": True,
            "offset_reached": False,
            "start_time": "2017-11-27 00:00:00",
            "end_time": "2017-11-28 00:00:00",
            "location": "Hamburg",
            "description": "What a beautiful day",
        })
