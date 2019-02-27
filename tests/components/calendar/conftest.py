"""Test fixture for calendar component."""
from datetime import timedelta, datetime
import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.calendar import DOMAIN


TODAY = datetime.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)
TOMORROW_AFTER = TODAY + timedelta(days=2)


class Calendar():
    """Fake calendar for websocket testing."""

    def __getattr__(self, key):
        """Get calendar events."""
        return [
            {
                'dt_start': YESTERDAY,
                'dt_end': TODAY,
            },
            {
                'dt_start': TODAY,
                'dt_end': TOMORROW,
            },
            {
                'dt_start': TOMORROW,
                'dt_end': TOMORROW_AFTER,
            }
        ]


class CalendarComponent():
    """Fake calendar component for websocket to search for entity."""

    def __init__(self):
        """Set a calendar entity on calendar component."""
        self.calendar = Calendar()

    def get_entity(self, entity_id):
        """Mock get entity to return real calendar or None."""
        if entity_id == 'calendar.real_calendar':
            return self.calendar
        return None


@pytest.fixture
async def calendar_setup(hass, hass_storage):
    """Calendar setup."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {
        'platform': 'calendar',
        'name': 'calendar_test',
        'webhook_id': 'calendar.real_calendar'
    }})

    hass.data[DOMAIN] = CalendarComponent()
