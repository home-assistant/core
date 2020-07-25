"""Support for Calendar."""
from abc import ABC
import logging
from typing import Dict, List, Optional

from homeassistant.helpers.entity import Entity
from homeassistant.util import dt

from .const import ATTR_NOW, ATTR_SCHEDULE, STATE_BUSY, STATE_FREE

_LOGGER = logging.getLogger(__name__)


class CalendarEvent(ABC):
    """Calendar Event object"""

    id = None
    title = None
    description = None
    location = None
    start = None
    end = None
    status = None
    organizer = None
    creator = None
    created = None
    updated = None
    ical_uid = None
    url = None


class CalendarEntity(Entity):
    """An entity representing a calendar."""

    def __init__(self, data):
        """Initialize Calendar Entity"""
        self._data = data
        self._state = None
        self._events = []
        self.now = []

    @property
    def state(self):
        """Return the state of the calendar."""
        return self._state

    @property
    def next_event(self) -> Dict:
        """Return the next upcoming event."""
        for event in self._events:
            if dt.now() < event.start:
                return vars(event)
        return None

    @property
    def events(self) -> List:
        """Return a list of upcoming events."""
        events = []
        for event in self._events:
            events.append(vars(event))
        return events

    @property
    def schedule(self) -> List:
        """Return a schedule of upcoming events."""
        schedule = []
        for event in self._events:
            schedule.append(vars(event))
        return schedule

    @property
    def capability_attributes(self) -> Dict:
        """Return capability attributes."""
        return {}

    @property
    def state_attributes(self):
        """Return the state attributes."""
        data = {ATTR_NOW: self.now, ATTR_SCHEDULE: self.schedule}

        return {key: val for key, val in data.items() if val is not None}

    # async def async_update(self):
    def update(self):
        """Update Calendar Entity"""
        self._state = STATE_FREE
        self.now = []

        if self._events is None:
            return True

        for event in self._events:
            if event.start is None or event.end is None:
                continue

            utc_start = dt.as_utc(event.start.replace(year=dt.now().year))
            utc_end = dt.as_utc(event.start.replace(year=dt.now().year))

            if utc_start <= dt.now() < utc_end:
                self._state = STATE_BUSY
                self.now.append(vars(event))

        return True
