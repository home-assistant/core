"""
Sensor to retrieve Jewish ritual times for Shabbat & Yom Tov from Hebcal API.


"""
import asyncio
import datetime
import logging
import json
import requests
import voluptuous as vol
from collections import namedtuple
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_SCAN_INTERVAL, CONF_LONGITUDE, CONF_LATITUDE, CONF_NAME,
    CONF_TIME_ZONE)
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import async_get_last_state
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Shabbat Time"
HAVDALAH_MINUTES = 'havdalah_minutes_after_sundown'
CANDLE_LIGHT_MINUTES = 'candle_lighting_minutes_before_sunset'

HAVDALAH_DEFAULT = 53
CANDLE_LIGHT_DEFAULT = 18
SCAN_INTERVAL = datetime.timedelta(minutes=60)

SHABBAT_START = 'shabbat_start'
SHABBAT_END = 'shabbat_end'
LAST_UPDATE = 'last_update'
TITLE = 'title'
HEBREW_TITLE = 'hebrew_title'

SENSOR_ATTRIBUTES = [HAVDALAH_MINUTES, CANDLE_LIGHT_MINUTES,
                     SHABBAT_START, SHABBAT_END, LAST_UPDATE,
                     TITLE, HEBREW_TITLE]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Inclusive(CONF_LATITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.longitude,
    vol.Optional(CONF_TIME_ZONE): cv.time_zone,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(HAVDALAH_MINUTES, default=HAVDALAH_DEFAULT): int,
    vol.Optional(CANDLE_LIGHT_MINUTES, default=CANDLE_LIGHT_DEFAULT): int,
    vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period
})

UNKNOWN_START = datetime.datetime.min
UNKNOWN_END = datetime.datetime.max


async def async_setup_platform(hass, config, add_devices, discovery_info=None):
    havdalah = config.get(HAVDALAH_MINUTES)
    candle_light = config.get(CANDLE_LIGHT_MINUTES)
    name = config.get(CONF_NAME)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    timezone = config.get(CONF_TIME_ZONE, hass.config.time_zone)

    add_devices([ShabbatTimes(hass, latitude, longitude, timezone, name,
                              havdalah, candle_light)])

###
# Supporting components
###


# We model every Shabbat or Yom Tov as an interval. Based on how it falls out,
# the interval may be a closed interval, e.g. [CandleLighting, Havdalah],
# a half-open interval on the start side, e.g. (UNKNOWN, Havdalah],
# or a half-open interval on the end side, e.g. [CandleLighting, UNKNOWN).
#
# In each of these half-open interval cases, we need to request from Hebcal
# the month that precedes or follows the interval in question to fill in the
# UNKNOWNs.
ShabbatInterval = namedtuple('ShabbatInterval',
                             ['start_time', 'end_time',
                              'title', 'hebrew_title'])


def _parse_time(timestr, includes_timezone=True):
    """Parses a time string from Hebcal to datetime, maybe with timezone."""
    return datetime.datetime.strptime(
        timestr[0:-6] if includes_timezone else timestr,
        '%Y-%m-%dT%H:%M:%S')


class ShabbatTimesFetcher:
    """Utility class for fetching Shabbat/YomTov times from Hebcal."""

    def __init__(self, latitude, longitude, timezone, havdalah, candle_light):
        self._latitude = latitude
        self._longitude = longitude
        self._timezone = timezone
        self._havdalah = havdalah
        self._candle_light = candle_light
        self.error = None

    def _fetchHebcalResponse(self, year, month):
        """Fetches a JSON object from Hebcal for a given month+year.

        This relies on correct setting of parameters in the constructor, e.g.
        latlng.
        """
        hebcal_url = ("http://www.hebcal.com/hebcal/?v=1&cfg=json&maj=off&"
                      "min=off&mod=off&nx=off&s=on&year=%d&month=%d&ss=off"
                      "&mf=off&c=on&geo=pos&latitude=%f&longitude=%f&"
                      "tzid=%s&m=%d&s=off&i=off&b=%d") % (
            year, month, self._latitude, self._longitude,
            self._timezone, self._havdalah, self._candle_light)
        _LOGGER.debug(hebcal_url)
        hebcal_response = requests.get(hebcal_url)
        hebcal_json_input = hebcal_response.text
        return json.loads(hebcal_json_input)

    def fetchTimes(self, year, month):
        """Fetches JSON for times for year/month.

        Returns:
          A list of ShabbatIntervals for that month.
        """
        self.error = None
        hebcal_decoded = self._fetchHebcalResponse(year, month)
        intervals = []

        if 'error' in hebcal_decoded:
            self.error = hebcal_decoded['error']
            _LOGGER.error('Hebcal error: ' + hebcal_decoded['error'])
            return []

        def IsMajorHoliday(item):
            """Returns true if item is a major holiday."""
            return (item['category'] == 'holiday' and
                    (item.get('subcat', '') == 'major' or
                     item.get('yomtov', False) == True))

        cur_interval = []
        cur_title = ''
        cur_hebrew_title = ''
        # See description of intervals above for details.
        half_open_start = False

        # State machine for parsing entries in Hebcal response.
        for item in hebcal_decoded['items']:
            if (item['category'] == 'candles'):
                # Parse the candle-lighting attribute.
                cur_interval.append(_parse_time(item['date']))
            elif (cur_title == '' and
                  (cur_interval or 'yomtov' in item or
                   item['category'] == 'parashat') and
                  (IsMajorHoliday(item) or item['category'] == 'parashat')):
                # Parse the Shabbat or Yom Tov title attribute.
                # Conditions for setting title:
                # 1) Title has not yet been set (take the first of a multi-day
                #    yomtov)
                # 2a) There is a candlelighting interval in progress, OR
                # 2b) There is NO interval in progress, but the month starts
                #     with a parasha (i.e. Shabbat is the 1st of the month) or
                #     a Yom Tov.
                # 3) The title element is itself a major holiday or parasha (so
                #    exclude all minor holidays and CH"M but not CH"M Shabbat).
                cur_title = item['title']
                cur_hebrew_title = item['hebrew']
                if not cur_interval:
                    # We might have advance knowledge that the first of the
                    # month should be a half-open start. This accounts for the
                    # case e.g. Sep 30 Erev YT Day 1, Oct 1 night starts YT
                    # Day 2, end of YT Oct 2 night).
                    # If we don't set this, on Oct 1 midnight and on, the
                    # interval's start might be parsed as candlelighting on
                    # Oct 1 night.
                    # By forcing this here, we later set the start interval to
                    # be half-open.
                    half_open_start = True
            elif (item['category'] == 'havdalah'):
                # Parse the havdalah attribute.
                ret_date = _parse_time(item['date'])
                if cur_interval:
                    if half_open_start:
                        intervals.append(ShabbatInterval(
                            UNKNOWN_START, ret_date, 
                            cur_title, cur_hebrew_title))
                    else:
                        intervals.append(ShabbatInterval(
                            cur_interval[0], ret_date, 
                            cur_title, cur_hebrew_title))
                    cur_interval = []
                    cur_title = ''
                    cur_hebrew_title = ''
                    half_open_start = False
                else:
                    # This is leftover from the previous month.
                    intervals.append(ShabbatInterval(
                        UNKNOWN_START, ret_date, cur_title, cur_hebrew_title))
                    cur_title = ''
                    cur_hebrew_title = ''
                    half_open_start = False

        if cur_interval:
            # Leftover half-open interval.
            intervals.append(ShabbatInterval(
                cur_interval[0], UNKNOWN_END, cur_title, cur_hebrew_title))
        _LOGGER.debug("Shabbat intervals: " + str(intervals))
        return intervals


def _IsAdjacentHalfOpenInterval(half_open_interval, next_interval):
    """Returns true if the two intervals are adjacent and the first is half-open.

    If the first interval is a half-open interval on the end, and the second
    interval is the interval that immediately follows it, for example:
      Sep. 30 is Erev YomTov / start of Day 1,
      Oct 1 night starts YomTov Day 2,
      Oct 2 night is end of Yom Tov
    Then the two intervals might look something like:
      [Sep. 30 7:02pm, UNKNOWN_END)
      [Oct 1, 7:01pm, Oct 2 7:00pm]
    This function returns true if this scenario arises so we can merge the
    intervals and simply form [Sep. 30 7:02pm, Oct 2 7:00pm].
    """
    return (half_open_interval.end_time == UNKNOWN_END and
            next_interval.start_time != UNKNOWN_START and
            (next_interval.start_time
             - half_open_interval.start_time).days == 1)


class ShabbatTimesParser:
    """Utility class for parsing fetched HebCal Shabbat/YomTov times."""

    def __init__(self, fetcher):
        """Initialize the parser with an already-constructed fetcher."""
        self._fetcher = fetcher
        self.error = None

    def update(self, now):
        """Find the upcoming or current (i.e. in-progress) Shabbat or Yom Tov.

        Returns a ShabbatInterval corresponding to the most relevant Shabbat
        or Yom Tov with respect to the 'now' parameter, or None if error.
        """
        _LOGGER.info("Updating Shabbat Times (now=" + str(now) + ")")
        self.error = None
        assert now
        today = datetime.datetime(now.year, now.month, now.day)
        if (today.weekday() == 5):
                # Back up the Friday in case it's still currently Shabbat.
            friday = today + datetime.timedelta(-1)
        else:
            friday = today + datetime.timedelta((4-today.weekday()) % 7)

        saturday = friday + datetime.timedelta(+1)

        # Retrieve parsed times for the month & year of the upcoming Friday.
        # TODO: Add a unit test to see if YT is Tues/Wed/Thurs at end of month,
        # and Friday is in the next month, and ensure this case works.
        intervals = self._fetcher.fetchTimes(friday.year, friday.month)
        if not intervals:
            self.error = 'Could not retrieve intervals.'
            _LOGGER.error(self.error)
            return None

        # If it's Motzei Shabbat, and there are no Shabbatot left in the month,
        # we need to advance the month and try again.
        # This only happens on Motzei Shabbat because of the line above where we
        # back up to the preceding Friday.
        if intervals[-1].end_time < now:
            _LOGGER.debug('Last monthly Motzei Shabbat; advancing times')
            friday = friday + datetime.timedelta(+7)
            saturday = friday + datetime.timedelta(+1)
            _LOGGER.debug(friday)
            intervals = self._fetcher.fetchTimes(friday.year, friday.month)
            if not intervals:
                _LOGGER.error('Could not retrieve next intervals!')
                return None

        # TODO: Need to add case for if it's currently Shabbat and the 1st of
        # month (prev_intervals) -- Aug/Sep/Oct 2018 good test case
        # If the last interval is an open interval (i.e. last day of month is
        # a Friday)...
        if intervals[-1].end_time == UNKNOWN_END:
            # ...fetch the next month to complete the interval
            next_year = friday.year + (1 if friday.month == 12 else 0)
            # Mod 13 to allow month 12 to appear. Good test case: Nov./Dec. 2018
            next_month = ((friday.month + 1) % 13)
            _LOGGER.debug(
                'Current month ends with open interval; '
                'retrieving next month (%04d-%02d)' % (next_year, next_month))
            next_intervals = self._fetcher.fetchTimes(next_year, next_month)
            if not next_intervals:
                _LOGGER.error('Could not retrieve next intervals!')
                return None
            # If the start of the next month is a half-open interval, OR it
            # appears to be a complete interval, though with a start_time
            # adjacent to the current month's half-open start time
            # (e.g. Sep 30 Erev YT Day 1, Oct 1 night starts YT Day 2,
            # end Oct 2) then it is considered to be a valid completion.
            if (next_intervals[0].start_time != UNKNOWN_START and
                    not _IsAdjacentHalfOpenInterval(
                    intervals[-1], next_intervals[0])):
                _LOGGER.error(
                    "Current month ends with open interval; "
                    "next month did not begin with open interval!")
                self.error = 'INTERVAL_ERROR'
                return None
            intervals[-1] = ShabbatInterval(
                intervals[-1].start_time, next_intervals[0].end_time,
                intervals[-1].title or next_intervals[0].title,
                intervals[-1].hebrew_title or next_intervals[0].hebrew_title)
            # Tack on the remaining intervals after stitching together the open
            # intervals. This handles the case of Motzei Shabbat AFTER the
            # stitched interval, when Shabbat ends on the 1st of the month
            # (e.g. 8/31->9/1@8pm; update for shabbat times at 10pm)
            intervals.extend(next_intervals[1:])

        if intervals[0].start_time == UNKNOWN_START:
            year = friday.year
            month = friday.month
            if friday.month == 0:
                month = 12
                year -= 1
            else:
                month -= 1
            _LOGGER.debug(
                'Current month starts with open interval; '
                'fetching previous month')
            prev_intervals = self._fetcher.fetchTimes(year, month)
            # _LOGGER.debug(prev_intervals)
            if not prev_intervals:
                _LOGGER.error('Could not retrieve previous intervals!')
                return None
            if prev_intervals[-1].end_time != UNKNOWN_END:
                _LOGGER.error(
                    "Current month starts with open interval; "
                    "previous month did not end with open interval!")
                self.error = 'INTERVAL_ERROR'
                return None
            intervals[0] = ShabbatInterval(
                prev_intervals[-1].start_time,
                intervals[0].end_time,
                prev_intervals[-1].title or intervals[0].title,
                prev_intervals[-1].hebrew_title or intervals[0].hebrew_title)

        # Sort intervals by start time.
        intervals.sort(key=lambda x: x.start_time)

        # Find first interval after "now".
        for interval in intervals:
            # Skip intervals in the past.
            if interval.end_time < now:
                continue
            # If interval start is greater than today, 
            # OR interval start is <= today but end time is > today 
            # (i.e. it is currently shabbat), pick that interval.
            if (interval.start_time > now or 
                (interval.start_time <= now and interval.end_time > now)):
                _LOGGER.info('Setting Shabbat times to ' + str(interval))
                return interval
        self.error = 'Unknown Error'
        return None

###
# Actual Sensor class for ShabbatTimes
###


class ShabbatTimes(Entity):

    def __init__(self, hass, latitude, longitude, timezone, name,
                 havdalah, candle_light):
        self._hass = hass
        self._latitude = latitude
        self._longitude = longitude
        self._timezone = timezone
        self._name = "Shabbat Times " + name
        self._havdalah = havdalah
        self._candle_light = candle_light
        self._state = 'Awaiting Update'
        self._shabbat_start = None
        self._shabbat_end = None
        self._last_update = None
        self._title = None
        self._hebrew_title = None

    async def async_added_to_hass(self):
        """ Restore original state."""
        old_state = await async_get_last_state(self.hass, self.entity_id)
        _LOGGER.debug('Old state: ' + str(old_state))
        if (not old_state or
            old_state.attributes[LAST_UPDATE] is None or
            old_state.attributes[SHABBAT_START] is None or
                old_state.attributes[SHABBAT_END] is None):
            await self.async_update()
            return

        old_shabbat_end = _parse_time(old_state.attributes[SHABBAT_END], False)
        if old_shabbat_end < datetime.datetime.now():
            _LOGGER.error(
                "Current time is newer than shabbat end time. Updating.")
            await self.async_update()
            return

        params = {key: old_state.attributes[key] for key in SENSOR_ATTRIBUTES
                  if key in old_state.attributes}
        self._state = old_state.state
        self._havdalah = params[HAVDALAH_MINUTES]
        self._candle_light = params[CANDLE_LIGHT_MINUTES]
        self._shabbat_start = params[SHABBAT_START]
        self._shabbat_end = params[SHABBAT_END]
        self._last_update = params[LAST_UPDATE]
        self._title = params[TITLE]
        self._hebrew_title = params[HEBREW_TITLE]
        _LOGGER.debug('New state: ' + str(self.device_state_attributes()))

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def device_state_attributes(self):
        return{
            SHABBAT_START: self._shabbat_start,
            SHABBAT_END: self._shabbat_end,
            HAVDALAH_MINUTES: self._havdalah,
            CANDLE_LIGHT_MINUTES: self._candle_light,
            LAST_UPDATE: self._last_update,
            TITLE: self._title,
            HEBREW_TITLE: self._hebrew_title,
        }

    @Throttle(SCAN_INTERVAL)
    async def async_update(self):
        self._state = 'Working'
        self._shabbat_start = None
        self._shabbat_end = None
        self._title = None

        fetcher = ShabbatTimesFetcher(
            self._latitude, self._longitude, self._timezone, self._havdalah,
            self._candle_light)
        parser = ShabbatTimesParser(fetcher)
        now = datetime.datetime.now()
        current_interval = parser.update(now)
        if current_interval is None:
            _LOGGER.error('Could not parse Shabbat Times!')
            if parser.error:
                self._state = parser.error
            else:
                self._state = 'Error'
        else:
            # Valid interval.
            self._shabbat_start = current_interval.start_time
            self._shabbat_end = current_interval.end_time
            self._title = current_interval.title
            self._hebrew_title = current_interval.hebrew_title
            _LOGGER.info('Setting Shabbat times to ' + str(current_interval))
            self._state = 'Updated'
            self._last_update = now
