"""
Support for Google Calendar Search binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.google_calendar/
"""
# pylint: disable=import-error
import logging
from homeassistant.components.calendar import CalendarEventDevice


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'google'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

CONF_NAME = 'name'
CONF_TRACK = 'track'
CONF_SEARCH = 'search'
CONF_OFFSET = 'offset'

DEFAULT_CONF_TRACK_NEW = True
DEFAULT_CONF_OFFSET = '#-'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the calendar platform for event devices."""
    if discovery_info is None:
        return

    add_devices([GoogleCalendarEventDevice(hass,
                                           discovery_info['cal_id'], data)
                 for data in discovery_info['entities'] if data['track']])


# pylint: disable=too-many-instance-attributes
class GoogleCalendarEventDevice(CalendarEventDevice):
    """A calendar event device."""

    def get_next_event(self):
        """Return the next event dict or None."""
        from homeassistant.components.google import get_next_event
        event = get_next_event(self.hass, self._calendar, self.search)
        return event
