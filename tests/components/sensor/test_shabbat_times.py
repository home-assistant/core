"""The tests for the Shabbat Times sensor platform."""
from collections import namedtuple
from datetime import timedelta
from datetime import datetime as dt
from unittest.mock import patch

import pytest
import requests_mock

from homeassistant.core import State
from homeassistant.helpers.restore_state import DATA_RESTORE_CACHE
from homeassistant.util.async_ import run_coroutine_threadsafe
from homeassistant.util.dt import get_time_zone, set_default_time_zone
from homeassistant.setup import setup_component
from homeassistant.components.sensor.shabbat_times import (
    ShabbatTimes, ShabbatTimesFetcher, ShabbatTimesParser,
    CANDLE_LIGHT_DEFAULT, HAVDALAH_DEFAULT)
from tests.common import get_test_home_assistant, load_fixture

_LatLng = namedtuple('_LatLng', ['lat', 'lng'])

NYC_LATLNG = _LatLng(40.7128, -74.0060)
JERUSALEM_LATLNG = _LatLng(31.778, 35.235)

BASE_URL = ("http://www.hebcal.com/hebcal/?v=1&cfg=json&maj=on&"
            "min=on&mod=off&nx=off&s=on&year=%d&month=%d&ss=off"
            "&mf=off&c=on&geo=pos&latitude=%f&longitude=%f&"
            "tzid=%s&b=%d&m=%d&i=%s")


def nyc_url(month, year):
    """Generate a Hebcal URL for NYC."""
    return BASE_URL % (month, year, NYC_LATLNG.lat, NYC_LATLNG.lng,
                       'America/New_York', 18, 53, 'off')


def jlem_url(month, year):
    """Generate a Hebcal URL for Jerusalem."""
    return BASE_URL % (month, year, JERUSALEM_LATLNG.lat,
                       JERUSALEM_LATLNG.lng, 'Asia/Jerusalem', 18, 53, 'on')


def make_nyc_test_params(dtime, results):
    """Make test params for NYC."""
    return (dtime, CANDLE_LIGHT_DEFAULT, HAVDALAH_DEFAULT, True,
            'America/New_York', NYC_LATLNG.lat, NYC_LATLNG.lng, results)


def make_jerusalem_test_params(dtime, results):
    """Make test params for Jerusalem."""
    return (dtime, CANDLE_LIGHT_DEFAULT, HAVDALAH_DEFAULT, False,
            'Asia/Jerusalem', JERUSALEM_LATLNG.lat, JERUSALEM_LATLNG.lng,
            results)


def get_requests_mocker():
    """Return a requests_mocker pointing to the correct fixtures."""
    mocker = requests_mock.Mocker()
    mocker.get(nyc_url(2018, 0),
               text=load_fixture('shabbat_times-ny-all_2018.json'))
    mocker.get(nyc_url(2018, 8),
               text=load_fixture('shabbat_times-ny-august_2018.json'))
    mocker.get(nyc_url(2018, 9),
               text=load_fixture('shabbat_times-ny-september_2018.json'))
    mocker.get(nyc_url(2018, 10),
               text=load_fixture('shabbat_times-ny-october_2018.json'))
    mocker.get(nyc_url(2018, 11),
               text=load_fixture('shabbat_times-ny-november_2018.json'))
    mocker.get(nyc_url(2018, 12),
               text=load_fixture('shabbat_times-ny-december_2018.json'))
    mocker.get(nyc_url(2019, 1),
               text=load_fixture('shabbat_times-ny-january_2019.json'))
    mocker.get(jlem_url(2018, 8),
               text=load_fixture('shabbat_times-jlem-august_2018.json'))
    mocker.get(jlem_url(2018, 9),
               text=load_fixture('shabbat_times-jlem-september_2018.json'))
    mocker.get(jlem_url(2018, 10),
               text=load_fixture('shabbat_times-jlem-october_2018.json'))
    return mocker


class TestShabbatTimes():
    """Test the Shabbat Times sensor."""

    # pylint: disable=attribute-defined-outside-init
    # pylint: disable=no-self-use
    def setup_method(self, method):
        """Set up things to run when tests begin."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()
        # Reset the default timezone, so we don't affect other tests
        set_default_time_zone(get_time_zone('UTC'))

    def verify_sensor(self, sensor, state, expected_attrs):
        """Assert that sensor state matches expectation."""
        assert sensor.state == state
        actual_attrs = {
            key: value for key,
            value in sensor.device_state_attributes.items() if key in (
                'shabbat_start',
                'shabbat_end',
                'title',
                'hebrew_title')}
        assert expected_attrs == actual_attrs

    def assign_golden_interval(self, dtime, golden_intervals):
        """Find a corresponding golden interval for a datetime.

        Assumes the list is sorted (ascending) by start_time.
        """
        for golden_interval in golden_intervals:
            # Skip intervals in the past.
            if golden_interval.end_time < dtime:
                continue
            if golden_interval.end_time > dtime:
                return golden_interval
        raise ValueError("No corresponding golden interval for {}!".format(
            dtime))

    def test_shabbat_times_parser(self):
        """Test Shabbat Times parser, independent of HASS.

        There should always be a valid interval for every single value of
        'now'. This uses the entire 2018 calendar response as a golden set of
        values (with no need to fetch subsequent months).
        """
        with get_requests_mocker():
            fetcher = ShabbatTimesFetcher(NYC_LATLNG.lat, NYC_LATLNG.lng,
                                          "America/New_York", 18, 53, True)
            golden_intervals = fetcher.fetch_times(2018, 0)
            golden_intervals.sort(key=lambda intv: intv.start_time)
            parser = ShabbatTimesParser(fetcher)

            # Test values from August 1, 2018 through (exclusive) Jan 1, 2019.
            time_zone = get_time_zone("America/New_York")
            dtime = time_zone.localize(dt(2018, 8, 1, 22, 0))
            end = time_zone.localize(dt(2019, 1, 1, 0, 0))
            while dtime < end:
                golden_interval = self.assign_golden_interval(
                    dtime, golden_intervals)
                parsed_interval = parser.update(dtime)

                assert parsed_interval == golden_interval, \
                    "Interval mismatch! Expected {}, got {}".format(
                        golden_interval, parsed_interval)
                dtime = dtime + timedelta(1)
            return

    def test_shabbat_times_min_config(self):
        """Test minimum shabbat times configuration."""
        config = {
            'sensor': {
                'platform': 'shabbat_times'
            }
        }
        with requests_mock.Mocker():
            assert setup_component(self.hass, 'sensor', config)

    test_params = [
        make_nyc_test_params(
            dt(2018, 9, 1, 16, 0),
            {'shabbat_start': dt(2018, 8, 31, 19, 11),
             'shabbat_end': dt(2018, 9, 1, 20, 20),
             'title': 'Parashat Ki Tavo',
             'hebrew_title': 'פרשת כי־תבוא'}),
        make_nyc_test_params(
            dt(2018, 9, 1, 20, 21),
            {'shabbat_start': dt(2018, 9, 7, 18, 59),
             'shabbat_end': dt(2018, 9, 8, 20, 9),
             'title': 'Parashat Nitzavim',
             'hebrew_title': 'פרשת נצבים'}),
        make_nyc_test_params(
            dt(2018, 9, 7, 13, 1),
            {'shabbat_start': dt(2018, 9, 7, 18, 59),
             'shabbat_end': dt(2018, 9, 8, 20, 9),
             'title': 'Parashat Nitzavim',
             'hebrew_title': 'פרשת נצבים'}),
        make_nyc_test_params(
            dt(2018, 9, 8, 21, 25),
            {'shabbat_start': dt(2018, 9, 9, 18, 56),
             'shabbat_end': dt(2018, 9, 11, 20, 3),
             'title': 'Rosh Hashana 5779',
             'hebrew_title': 'ראש השנה 5779'}),
        make_nyc_test_params(
            dt(2018, 9, 9, 21, 25),
            {'shabbat_start': dt(2018, 9, 9, 18, 56),
             'shabbat_end': dt(2018, 9, 11, 20, 3),
             'title': 'Rosh Hashana 5779',
             'hebrew_title': 'ראש השנה 5779'}),
        make_nyc_test_params(
            dt(2018, 9, 10, 21, 25),
            {'shabbat_start': dt(2018, 9, 9, 18, 56),
             'shabbat_end': dt(2018, 9, 11, 20, 3),
             'title': 'Rosh Hashana 5779',
             'hebrew_title': 'ראש השנה 5779'}),
        make_nyc_test_params(
            dt(2018, 9, 28, 21, 25),
            {'shabbat_start': dt(2018, 9, 28, 18, 24),
             'shabbat_end': dt(2018, 9, 29, 19, 33),
             'title': "Sukkot VI (CH''M)",
             'hebrew_title': 'סוכות יום ו׳ (חול המועד)'}),
        make_nyc_test_params(
            dt(2018, 9, 29, 21, 25),
            {'shabbat_start': dt(2018, 9, 30, 18, 20),
             'shabbat_end': dt(2018, 10, 2, 19, 28),
             'title': 'Shmini Atzeret',
             'hebrew_title': 'שמיני עצרת'}),
        make_nyc_test_params(
            dt(2018, 10, 1, 21, 25),
            {'shabbat_start': dt(2018, 9, 30, 18, 20),
             'shabbat_end': dt(2018, 10, 2, 19, 28),
             'title': 'Shmini Atzeret',
             'hebrew_title': 'שמיני עצרת'}),
        make_jerusalem_test_params(
            dt(2018, 9, 29, 21, 25),
            {'shabbat_start': dt(2018, 9, 30, 18, 7),
             'shabbat_end': dt(2018, 10, 1, 19, 17),
             'title': 'Shmini Atzeret',
             'hebrew_title': 'שמיני עצרת'}),
        make_jerusalem_test_params(
            dt(2018, 10, 1, 21, 25),
            {'shabbat_start': dt(2018, 10, 5, 18, 1),
             'shabbat_end': dt(2018, 10, 6, 19, 10),
             'title': 'Parashat Bereshit',
             'hebrew_title': 'פרשת בראשית'}),
    ]

    test_ids = [
        "currently_first_shabbat",
        "after_first_shabbat",
        "friday_upcoming_shabbat",
        "upcoming_rosh_hashana",
        "currently_rosh_hashana",
        "second_day_rosh_hashana",
        "currently_shabbat_chol_hamoed",
        "upcoming_two_day_yomtov_in_diaspora",
        "currently_second_day_of_two_day_yomtov_in_diaspora",
        "upcoming_one_day_yom_tov_in_israel",
        "after_one_day_yom_tov_in_israel",
    ]

    @pytest.mark.parametrize(["now", "candle_lighting", "havdalah", "diaspora",
                              "tzname", "latitude", "longitude", "result"],
                             test_params, ids=test_ids)
    def test_shabbat_times_sensor(self, now, candle_lighting, havdalah,
                                  diaspora, tzname, latitude, longitude,
                                  result):
        """Test Shabbat Times sensor output."""
        time_zone = get_time_zone(tzname)
        set_default_time_zone(time_zone)
        test_time = time_zone.localize(now)
        result['shabbat_start'] = time_zone.localize(result['shabbat_start'])
        result['shabbat_end'] = time_zone.localize(result['shabbat_end'])
        self.hass.config.latitude = latitude
        self.hass.config.longitude = longitude
        sensor = ShabbatTimes(
            self.hass, latitude=latitude, longitude=longitude,
            timezone=time_zone, name="Shabbat Times", havdalah=havdalah,
            candle_light=candle_lighting, diaspora=diaspora)
        with patch('homeassistant.util.dt.now', return_value=test_time), \
                get_requests_mocker():
            run_coroutine_threadsafe(
                sensor.async_update(),
                self.hass.loop).result()
            self.verify_sensor(sensor, 'Updated', result)

    test_params = [
        # no_previous_state
        (dt(2018, 9, 1, 16, 0),
         {},
         True,
         {'shabbat_start': dt(2018, 8, 31, 19, 11),
          'shabbat_end': dt(2018, 9, 1, 20, 20),
          'title': 'Parashat Ki Tavo',
          'hebrew_title': 'פרשת כי־תבוא'}),
        # incomplete_previous_state
        (dt(2018, 9, 1, 16, 0),
         {'last_update': '2018-09-01T15:30:00-04:00',
          'candle_lighting_minutes_before_sunset': 20,
          'havdalah_minutes_after_sundown': 50,
          'shabbat_start': None,
          'shabbat_end': None,
          'title': 'Parashat Ki Tavo',
          'hebrew_title': 'פרשת כי־תבוא'},
         True,
         {'shabbat_start': dt(2018, 8, 31, 19, 11),
          'shabbat_end': dt(2018, 9, 1, 20, 20),
          'title': 'Parashat Ki Tavo',
          'hebrew_title': 'פרשת כי־תבוא'}),
        # previous_state_ends_before_now
        (dt(2018, 8, 25, 21, 0),
         {'last_update': '2018-08-25T15:30:00-04:00',
          'candle_lighting_minutes_before_sunset': 20,
          'havdalah_minutes_after_sundown': 50,
          'shabbat_start': '2018-08-24T19:22:00-04:00',
          'shabbat_end': '2018-08-25T20:31:00-04:00',
          'title': 'Parashat Ki Teitzei',
          'hebrew_title': 'פרשת כי־תצא'},
         True,
         {'shabbat_start': dt(2018, 8, 31, 19, 11),
          'shabbat_end': dt(2018, 9, 1, 20, 20),
          'title': 'Parashat Ki Tavo',
          'hebrew_title': 'פרשת כי־תבוא'}),

        # valid_previous_state
        (dt(2018, 9, 1, 16, 0),
         {'last_update': '2018-09-01T15:30:00-04:00',
          'candle_lighting_minutes_before_sunset': 20,
          'havdalah_minutes_after_sundown': 50,
          'shabbat_start': '2018-08-31T19:11:00-04:00',
          'shabbat_end': '2018-09-01T20:20:00-04:00',
          'title': 'Parashat Ki Tavo',
          'hebrew_title': 'פרשת כי־תבוא'},
         False,
         {'shabbat_start': dt(2018, 8, 31, 19, 11),
          'shabbat_end': dt(2018, 9, 1, 20, 20),
          'title': 'Parashat Ki Tavo',
          'hebrew_title': 'פרשת כי־תבוא'}),
    ]

    test_ids = [
        "no_previous_state",
        "incomplete_previous_state",
        "previous_state_ends_before_now",
        "valid_previous_state",
    ]

    @pytest.mark.parametrize(["now", "previous_state", "should_fetch",
                              "result"], test_params, ids=test_ids)
    def test_shabbat_times_async_readded(
            self, now, previous_state, should_fetch, result):
        """Test reading of prior Shabbat Times states."""
        time_zone = get_time_zone('America/New_York')
        set_default_time_zone(time_zone)
        test_time = time_zone.localize(now)
        result['shabbat_start'] = time_zone.localize(result['shabbat_start'])
        result['shabbat_end'] = time_zone.localize(result['shabbat_end'])
        self.hass.config.latitude = NYC_LATLNG.lat
        self.hass.config.longitude = NYC_LATLNG.lng
        self.hass.data[DATA_RESTORE_CACHE] = {
            'sensor.shabbat_times': State(
                'sensor.shabbat_times',
                state='Updated',
                attributes=previous_state)}
        sensor = ShabbatTimes(
            self.hass, latitude=NYC_LATLNG.lat, longitude=NYC_LATLNG.lng,
            timezone=time_zone, name="Shabbat Times", havdalah=HAVDALAH_DEFAULT,
            candle_light=CANDLE_LIGHT_DEFAULT, diaspora=True)
        sensor.entity_id = 'sensor.shabbat_times'
        with patch('homeassistant.util.dt.now', return_value=test_time), \
                requests_mock.Mocker() as requests_mocker:

            # Only set up mock to fetch if it's expected that the restore-state
            # did not work properly.
            if should_fetch:
                requests_mocker.get(nyc_url(2018, 8), text=load_fixture(
                    'shabbat_times-ny-august_2018.json'))
                requests_mocker.get(nyc_url(2018, 9), text=load_fixture(
                    'shabbat_times-ny-september_2018.json'))
            run_coroutine_threadsafe(
                sensor.async_added_to_hass(),
                self.hass.loop).result()
            self.verify_sensor(sensor, 'Updated', result)
