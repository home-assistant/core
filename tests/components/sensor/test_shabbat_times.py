"""The tests for the Jewish calendar sensor platform."""
from datetime import time
from datetime import datetime as dt
from unittest.mock import patch

import pytest
import requests_mock

from homeassistant.util.async_ import run_coroutine_threadsafe
from homeassistant.util.dt import get_time_zone, set_default_time_zone
from homeassistant.setup import setup_component
import homeassistant.components.sensor.shabbat_times
from tests.common import get_test_home_assistant, load_fixture

NYC_LATLNG = (40.7128, -74.0060)
JERUSALEM_LATLNG = (31.778, 35.235)

class FakeFetcher(shabbat_times.ShabbatTimesFetcher):
  def __init__(self):
    self._cache = {
     'nyc': {
        (2018, 8): load_fixture('shabbat_times-ny-august_2018.json'),
        (2018, 9): load_fixture('shabbat_times-ny-september_2018.json'),
        (2018, 10): load_fixture('shabbat_times-ny-october_2018.json'),
        (2018, 11): load_fixture('shabbat_times-ny-november_2018.json'),
        (2018, 12): load_fixture('shabbat_times-ny-december_2018.json'),
        (2019, 1): load_fixture('shabbat_times-ny-january_2019.json'),
        (2018, 0): load_fixture('shabbat_times-ny-all_2018.json'),
      },
      'jlem': {
        (2018, 8): load_fixture('shabbat_times-jlem-august_2018.json'),
        (2018, 9): load_fixture('shabbat_times-jlem-september_2018.json'),
        (2018, 10): load_fixture('shabbat_times-jlem-october_2018.json'),
      }
    }
 
  def _fetch_hebcal_response(self, year, month):
    if self._latitude == JERUSALEM_LATLNG[0] and self._longitude == JERUSALEM_LATLNG[1]:
      city = 'jlem'
    else:
      city = 'nyc'
    assert self._cache[city]
    if (year, month) in self._cache[city]:
      return self._cache[city][(year, month)]
    return None

class TestShabbatTimes():
    """Test the Shabbat Times sensor."""

    def setup_method(self, method):
        """Set up things to run when tests begin."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()
        # Reset the default timezone, so we don't affect other tests
        set_default_time_zone(get_time_zone('UTC'))
        
    def assign_golden_interval(self, d, golden_intervals):
      """Finds a corresponding golden interval for a datetime.

      Assumes the list is sorted by start_time.
      """
      for golden_interval in golden_intervals:
        # Skip intervals in the past.
        if golden_interval.end_time < d:
          continue
        if (golden_interval.start_time > d or 
            (golden_interval.start_time <= d and golden_interval.end_time > d)):
          return golden_interval      
      raise ValueError("No corresponding golden interval for {}!".format(d))

    def test_shabbat_times_parser(self):
      """Test Shabbat Times parser, independent of HASS.
      
      There should always be a valid interval for every single value of 'now'.
      This uses the entire 2018 calendar response as a golden set of values 
      (with no need to fetch subsequent months).
      """
      fetcher = FakeFetcher()
      golden_intervals = fetcher.fetch_times(2018, 0)
      golden_intervals.sort(key=lambda intv: intv.start_time)
      parser = shabbat_times.ShabbatTimesParser(fetcher)
      
      # Test values from August 1, 2018 through (exclusive) Jan 1, 2019.
      d = datetime.datetime(2018, 8, 1, 22, 0)
      end = datetime.datetime(2019, 1, 1)
      golden_intervals = {}
      while d < end:
        golden_interval = self.assign_golden_interval(d, golden_intervals)
        parsed_interval = parser.update(d)
        
        assert parsed_interval != golden_interval, \
          "Interval mismatch! Expected {}, got {}".format(
            golden_interval, parsed_interval)
        d = d + datetime.timedelta(1)
      return


    def test_shabbat_times_min_config(self):
        """Test minimum shabbat times configuration."""
        config = {
            'sensor': {
                'platform': 'shabbat_times'
            }
        }
        assert setup_component(self.hass, 'sensor', config)

    test_params = [
        (dt(2018, 9, 1, 16, 0), 18, 53, True, 'America/New_York', 40.7128, -74.0060, 
         {'shabbat_start': dt(2018, 8, 31, 19, 11), 'shabbat_end': dt(2018, 9, 1, 20, 20),
          'title': 'Parashat Ki Tavo', 'hebrew_title': 'פרשת כי־תבוא'}),
        (dt(2018, 9, 1, 20, 21), 18, 53, True, 'America/New_York', 40.7128, -74.0060, 
         {'shabbat_start': dt(2018, 9, 7, 18, 59), 'shabbat_end': dt(2018, 9, 8, 20, 9),
          'title': 'Parashat Nitzavim', 'hebrew_title': 'פרשת נצבים'}),
        (dt(2018, 9, 7, 13, 1), 18, 53, True, 'America/New_York', 40.7128, -74.0060, 
         {'shabbat_start': dt(2018, 9, 7, 18, 59), 'shabbat_end': dt(2018, 9, 8, 20, 9),
          'title': 'Parashat Nitzavim', 'hebrew_title': 'פרשת נצבים'}),
        (dt(2018, 9, 8, 21, 25), 18, 53, True, 'America/New_York', 40.7128, -74.0060, 
         {'shabbat_start': dt(2018, 9, 9, 18, 56), 'shabbat_end': dt(2018, 9, 11, 20, 3),
          'title': 'Rosh Hashana 5779', 'hebrew_title': 'ראש השנה 5779'}),
        (dt(2018, 9, 9, 21, 25), 18, 53, True, 'America/New_York', 40.7128, -74.0060, 
         {'shabbat_start': dt(2018, 9, 9, 18, 56), 'shabbat_end': dt(2018, 9, 11, 20, 3),
          'title': 'Rosh Hashana 5779', 'hebrew_title': 'ראש השנה 5779'}),
        (dt(2018, 9, 10, 21, 25), 18, 53, True, 'America/New_York', 40.7128, -74.0060, 
         {'shabbat_start': dt(2018, 9, 9, 18, 56), 'shabbat_end': dt(2018, 9, 11, 20, 3),
          'title': 'Rosh Hashana 5779', 'hebrew_title': 'ראש השנה 5779'}),
        (dt(2018, 9, 28, 21, 25), 18, 53, True, 'America/New_York', 40.7128, -74.0060, 
         {'shabbat_start': dt(2018, 9, 28, 18, 24), 'shabbat_end': dt(2018, 9, 29, 19, 33),
          'title': "Sukkot VI (CH''M)", 
          'hebrew_title': 'סוכות יום ו׳ (חול המועד)'}),
        (dt(2018, 9, 29, 21, 25), 18, 53, True, 'America/New_York', 40.7128, -74.0060, 
         {'shabbat_start': dt(2018, 9, 30, 18, 20), 'shabbat_end': dt(2018, 10, 2, 19, 28),
          'title': 'Shmini Atzeret', 'hebrew_title': 'שמיני עצרת'}),
        (dt(2018, 10, 1, 21, 25), 18, 53, True, 'America/New_York', 40.7128, -74.0060, 
         {'shabbat_start': dt(2018, 9, 30, 18, 20), 'shabbat_end': dt(2018, 10, 2, 19, 28),
          'title': 'Shmini Atzeret', 'hebrew_title': 'שמיני עצרת'}),
        (dt(2018, 9, 29, 21, 25), 18, 53, False, "Asia/Jerusalem", 31.778, 35.235,
         {'shabbat_start': dt(2018, 9, 30, 18, 7), 'shabbat_end': dt(2018, 10, 1, 19, 17),
          'title': 'Shmini Atzeret', 'hebrew_title': 'שמיני עצרת'}),
        (dt(2018, 10, 1, 21, 25), 18, 53, False, "Asia/Jerusalem", 31.778, 35.235,
         {'shabbat_start': dt(2018, 9, 30, 18, 7), 'shabbat_end': dt(2018, 10, 2, 19, 28),
          'title': 'Parashat Bereshit', 'hebrew_title': 'פרשת בראשית'}),
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
    def test_shabbat_times_sensor(self, now, name, candle_lighting, havdalah,
                                  diaspora, tzname, latitude, longitude, 
                                  result):
        """Test Shabbat Times sensor output."""
        tz = get_time_zone(tzname)
        set_default_time_zone(tz)
        test_time = tz.localize(now)
        self.hass.config.latitude = latitude
        self.hass.config.longitude = longitude
        sensor = ShabbatTimes(
            self.hass, latitude=latitude, longitude=longitude,
            timezone=tz, name="Shabbat Times", havdalah=havdalah,
            candle_lighting=candle_lighting, diaspora=diaspora)
        with patch('homeassistant.util.dt.now', return_value=test_time):
          with patch('homeassistant.components.shabbat_times.ShabbatTimesFetcher',
                     return_value=FakeFetcher):
            run_coroutine_threadsafe(
                sensor.async_update(),
                self.hass.loop).result()
            assert sensor.state == 'Updated'
            expected_attrs = result
            actual_attrs = {key: value for key in 
                            sensor.device_state_attributes().items() 
                            if key in ('shabbat_start', 'shabbat_end', 'title', 
                                       'hebrew_title')}
            assert expected_attrs == actual_attrs

    # TODO use mock instead of fake