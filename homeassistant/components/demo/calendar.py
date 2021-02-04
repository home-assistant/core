"""Demo platform that has two fake binary sensors."""
import copy

from homeassistant.components.calendar import CalendarEventDevice, get_date
import homeassistant.util.dt as dt_util


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Demo Calendar platform."""
    calendar_data_future = DemoGoogleCalendarDataFuture()
    calendar_data_current = DemoGoogleCalendarDataCurrent()
    add_entities(
        [
            DemoGoogleCalendar(hass, calendar_data_future, "Calendar 1"),
            DemoGoogleCalendar(hass, calendar_data_current, "Calendar 2"),
        ]
    )


class DemoGoogleCalendarData:
    """Representation of a Demo Calendar element."""

    event = None

    async def async_get_events(self, hass, start_date, end_date):
        """Get all events in a specific time frame."""
        event = copy.copy(self.event)
        event["title"] = event["summary"]
        event["start"] = get_date(event["start"]).isoformat()
        event["end"] = get_date(event["end"]).isoformat()
        return [event]


class DemoGoogleCalendarDataFuture(DemoGoogleCalendarData):
    """Representation of a Demo Calendar for a future event."""

    def __init__(self):
        """Set the event to a future event."""
        one_hour_from_now = dt_util.now() + dt_util.dt.timedelta(minutes=30)
        self.event = {
            "start": {"dateTime": one_hour_from_now.isoformat()},
            "end": {
                "dateTime": (
                    one_hour_from_now + dt_util.dt.timedelta(minutes=60)
                ).isoformat()
            },
            "summary": "Future Event",
        }


class DemoGoogleCalendarDataCurrent(DemoGoogleCalendarData):
    """Representation of a Demo Calendar for a current event."""

    def __init__(self):
        """Set the event data."""
        middle_of_event = dt_util.now() - dt_util.dt.timedelta(minutes=30)
        self.event = {
            "start": {"dateTime": middle_of_event.isoformat()},
            "end": {
                "dateTime": (
                    middle_of_event + dt_util.dt.timedelta(minutes=60)
                ).isoformat()
            },
            "summary": "Current Event",
        }


class DemoGoogleCalendar(CalendarEventDevice):
    """Representation of a Demo Calendar element."""

    def __init__(self, hass, calendar_data, name):
        """Initialize demo calendar."""
        self.data = calendar_data
        self._name = name

    @property
    def event(self):
        """Return the next upcoming event."""
        return self.data.event

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    async def async_get_events(self, hass, start_date, end_date):
        """Return calendar events within a datetime range."""
        return await self.data.async_get_events(hass, start_date, end_date)
