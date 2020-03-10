"""Support for tracking the moon phases."""
from datetime import timedelta
import logging

from astral import Astral
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Moon"

STATE_FIRST_QUARTER = "first_quarter"
STATE_FULL_MOON = "full_moon"
STATE_LAST_QUARTER = "last_quarter"
STATE_NEW_MOON = "new_moon"
STATE_WANING_CRESCENT = "waning_crescent"
STATE_WANING_GIBBOUS = "waning_gibbous"
STATE_WAXING_GIBBOUS = "waxing_gibbous"
STATE_WAXING_CRESCENT = "waxing_crescent"

STATE_ATTR_NEXT_NEW_MOON = "next_new_moon"
STATE_ATTR_NEXT_FULL_MOON = "next_full_moon"

MOON_ICONS = {
    STATE_FIRST_QUARTER: "mdi:moon-first-quarter",
    STATE_FULL_MOON: "mdi:moon-full",
    STATE_LAST_QUARTER: "mdi:moon-last-quarter",
    STATE_NEW_MOON: "mdi:moon-new",
    STATE_WANING_CRESCENT: "mdi:moon-waning-crescent",
    STATE_WANING_GIBBOUS: "mdi:moon-waning-gibbous",
    STATE_WAXING_CRESCENT: "mdi:moon-waxing-crescent",
    STATE_WAXING_GIBBOUS: "mdi:moon-waxing-gibbous",
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Moon sensor."""
    name = config.get(CONF_NAME)

    async_add_entities([MoonSensor(name)], True)


class MoonSensor(Entity):
    """Representation of a Moon sensor."""

    def __init__(self, name):
        """Initialize the moon sensor."""
        self._name = name
        self._state = None
        self.next_new_moon = None
        self.next_full_moon = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._state == 0:
            return STATE_NEW_MOON
        if self._state < 7:
            return STATE_WAXING_CRESCENT
        if self._state == 7:
            return STATE_FIRST_QUARTER
        if self._state < 14:
            return STATE_WAXING_GIBBOUS
        if self._state == 14:
            return STATE_FULL_MOON
        if self._state < 21:
            return STATE_WANING_GIBBOUS
        if self._state == 21:
            return STATE_LAST_QUARTER
        return STATE_WANING_CRESCENT

    @property
    def state_attributes(self):
        """Return the state attributes of the sun."""
        attrs = {}
        if self.next_new_moon is not None:
            attrs[STATE_ATTR_NEXT_NEW_MOON] = self.next_new_moon.isoformat()
        if self.next_full_moon is not None:
            attrs[STATE_ATTR_NEXT_FULL_MOON] = self.next_full_moon.isoformat()
        return attrs

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return MOON_ICONS.get(self.state)

    async def async_update(self):
        """Get the time and updates the states."""
        today = dt_util.as_local(dt_util.utcnow()).date()
        self._calculate_next_moon_dates()
        self._state = Astral().moon_phase(today)

    def _calculate_next_moon_dates(self):
        # if we already have dates that are in the future, skip the calculation
        today = dt_util.as_local(dt_util.utcnow()).date()
        if (
            self.next_new_moon is not None
            and self.next_full_moon is not None
            and self.next_new_moon > today
            and self.next_full_moon > today
        ):
            return

        # Astral doesn't provide the next dates, so let's iterate the
        # next 31 days (full moon phase lasts about 29,5 days)
        # to find the next new and full moon days
        a = Astral()
        end = today + timedelta(days=31)
        new_moon = None
        full_moon = None
        for i in range((end - today).days):
            day = today + timedelta(days=i)
            phase = round(a.moon_phase(date=day, rtype=float), 0)
            if phase == 0:
                new_moon = day
            if phase == 14:
                full_moon = day
            if new_moon is not None and full_moon is not None:
                break
        self.next_new_moon = new_moon
        self.next_full_moon = full_moon
