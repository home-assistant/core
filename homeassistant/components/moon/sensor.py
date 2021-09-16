"""Support for tracking the moon phases."""
from skyfield import almanac
import skyfield.api
from skyfield.api import Loader
import voluptuous as vol
import datetime as dt
import pytz

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_NAME,
    EVENT_CORE_CONFIG_UPDATE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import event
import homeassistant.util.dt as dt_util
from homeassistant.core import callback

import logging

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

STATE_ATTR_NEXT_RISING = "next_rising"
STATE_ATTR_NEXT_SETTING = "next_setting"
STATE_ATTR_NEXT_TRANSIT = "next_transit"
STATE_ATTR_NEXT_ANTITRANSIT = "next_antitransit"
STATE_ATTR_ALTITUDE = "altitude"
STATE_ATTR_AZIMUTH = "azimuth"
STATE_ATTR_RISING = "rising"
STATE_ATTR_ABOVE_HORIZON = "above_horizon"
STATE_ATTR_ILLUMINATION = "illumination"
STATE_ATTR_DISTANCE = "distance"

PHASE_LOOKUP = {
    (0, 0): STATE_WAXING_CRESCENT,
    (0, 1): STATE_FIRST_QUARTER,
    (1, 1): STATE_WAXING_GIBBOUS,
    (1, 2): STATE_FULL_MOON,
    (2, 2): STATE_WANING_GIBBOUS,
    (2, 3): STATE_LAST_QUARTER,
    (3, 3): STATE_WANING_CRESCENT,
    (3, 0): STATE_NEW_MOON,
}

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


# The JPL ephemeris DE421 (covers 1900-2050).
JPL_EPHEMERIS_421 = "de421.bsp"
FOLDER = "skyfield-data"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Moon sensor."""
    name = config.get(CONF_NAME)

    async_add_entities([MoonSensor(hass, name)], True)


class MoonSensor(SensorEntity):
    """Representation of a Moon sensor."""

    def __init__(self, hass, name):
        """Initialize the moon sensor."""
        self.hass = hass
        self._name = name
        self._state = None

        load = Loader(hass.config.path(FOLDER))
        self._eph = load(JPL_EPHEMERIS_421)
        self._earth = self._eph["earth"]
        self._moon = self._eph["moon"]
        self._ts = skyfield.api.load.timescale()
        self._location = None
        self._latitude = None
        self._longitude = None
        self._elevation = None
        self.phase = None
        self.next_transit = None
        self.next_antitransit = None
        self.next_rising = None
        self.next_setting = None
        self.illumination = None
        self.altitude = 0
        self.azimuth = 0
        self.distance = 0

        # set a listener to update our location if config changes
        def update_location(_event, skip_reschedule=True):
            latitude = self.hass.config.latitude
            longitude = self.hass.config.longitude
            elevation = hass.config.elevation
            if (
                (self._latitude == latitude)
                and (self._longitude == longitude)
                and (self._elevation == elevation)
            ):
                return
            self._latitude = latitude
            self._longitude = longitude
            self._elevation = elevation
            self._location = skyfield.api.wgs84.latlon(
                latitude_degrees=latitude,
                longitude_degrees=longitude,
                elevation_m=elevation,
            )
            # force event times to be recalculated if location changed
            self.next_transit = None
            self.next_antitransit = None
            self.next_rising = None
            self.next_setting = None

            # Mark config related updates so that more and more timers won't be queued up
            self.update_events(now=None, skip_reschedule=skip_reschedule)

        update_location(None, skip_reschedule=False)
        self.hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, update_location)

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the entity."""
        return "moon__phase"

    @property
    def state(self):
        """Return the phase of the Moon."""
        return self.phase

    @property
    def state_attributes(self):
        """Return the state attributes of the Moon."""
        transit = None
        if (self.next_transit is not None) and (self.next_antitransit is not None):
            transit = self.next_transit < self.next_antitransit
        return {
            STATE_ATTR_NEXT_RISING: self.next_rising,
            STATE_ATTR_NEXT_SETTING: self.next_setting,
            STATE_ATTR_NEXT_TRANSIT: self.next_transit,
            STATE_ATTR_NEXT_ANTITRANSIT: self.next_antitransit,
            STATE_ATTR_ALTITUDE: self.altitude,
            STATE_ATTR_AZIMUTH: self.azimuth,
            STATE_ATTR_RISING: transit,
            STATE_ATTR_ABOVE_HORIZON: self.altitude >= 0,
            STATE_ATTR_ILLUMINATION: self.illumination,
            STATE_ATTR_DISTANCE: self.distance,
        }

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return MOON_ICONS.get(self.state)

    def _find_next_event(self, now, event_id, func):
        interval_start = self._ts.from_datetime(now)
        interval_end = self._ts.from_datetime(now + dt.timedelta(days=1))

        count = 0
        while count < 400:
            times, events = almanac.find_discrete(interval_start, interval_end, func)
            events = times[events == event_id]
            if len(events) > 0:
                return events[0].utc_datetime()
            now = now + dt.timedelta(days=1)
            interval_start = interval_end
            interval_end = self._ts.from_datetime(now + dt.timedelta(days=1))
            count += 1

    @callback
    def update_events(self, now=None, skip_reschedule=False):
        """Calculate upcoming celestial events related to the moon."""
        if now is None:
            now = dt_util.utcnow()

        # find the upper and lower transits of the moon from local observation
        func = almanac.meridian_transits(self._eph, self._moon, self._location)
        if (not self.next_transit) or (now >= self.next_transit):
            self.next_transit = self._find_next_event(now, 1, func)
        if (not self.next_antitransit) or (now >= self.next_antitransit):
            self.next_antitransit = self._find_next_event(now, 0, func)

        func = almanac.risings_and_settings(self._eph, self._moon, self._location)
        if (not self.next_rising) or (now >= self.next_rising):
            self.next_rising = self._find_next_event(now, 1, func)
        if (not self.next_setting) or (now >= self.next_setting):
            self.next_setting = self._find_next_event(now, 0, func)

        interval_start = self._ts.from_datetime(now)
        # calculate percent illumination
        self.illumination = "{:.1%}".format(
            almanac.fraction_illuminated(self._eph, "moon", interval_start)
        )

        mypos = self._earth + self._location
        altitude, azimuth, distance = (
            mypos.at(interval_start).observe(self._moon).apparent().altaz()
        )
        self.altitude = round(float(altitude.degrees), 2)
        self.azimuth = round(float(azimuth.degrees), 2)
        self.distance = "%0.2f km" % round(float(distance.km), 2)

        # calculate the current phase
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        next_midnight = midnight + dt.timedelta(days=1)
        interval_start = self._ts.from_datetime(midnight)
        interval_end = self._ts.from_datetime(next_midnight)
        # ph returns a number 0-3 representing the age of the moon's cycle.
        ph = almanac.moon_phases(self._eph)
        last_phase = ph(interval_start)
        next_phase = ph(interval_end)
        self.phase = PHASE_LOOKUP[(last_phase, next_phase)]

        if abs(self.altitude) <= 10:
            delta = dt.timedelta(minutes=2)
        elif self.altitude >= 0:
            delta = dt.timedelta(minutes=4)
        else:
            delta = dt.timedelta(minutes=10)

        next_update = now + delta

        for celestial_event in (
            self.next_rising,
            self.next_transit,
            self.next_setting,
            self.next_antitransit,
        ):
            # favor celestial events with a slight bias, in order to ensure that
            # we don't process two updates in rapid succession
            if celestial_event <= (now + delta * 1.25):
                next_update = celestial_event

        if skip_reschedule:
            _LOGGER.debug("Update was due to config change. Skipping future updates.")
        else:
            _LOGGER.debug("Next update: %s", next_update.isoformat())
            event.async_track_point_in_utc_time(
                self.hass, self.update_events, next_update
            )
