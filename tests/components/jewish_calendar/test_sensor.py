"""The tests for the Jewish calendar sensor platform."""
from collections import namedtuple
from datetime import time
from datetime import datetime as dt
from unittest.mock import patch

import pytest

from homeassistant.util.async_ import run_coroutine_threadsafe
from homeassistant.util.dt import get_time_zone, set_default_time_zone
from homeassistant.setup import setup_component
from homeassistant.components.jewish_calendar.sensor import (
    JewishCalSensor, CANDLE_LIGHT_DEFAULT)
from tests.common import get_test_home_assistant


_LatLng = namedtuple('_LatLng', ['lat', 'lng'])

NYC_LATLNG = _LatLng(40.7128, -74.0060)
JERUSALEM_LATLNG = _LatLng(31.778, 35.235)


def make_nyc_test_params(dtime, results, havdalah_offset=0):
    """Make test params for NYC."""
    return (dtime, CANDLE_LIGHT_DEFAULT, havdalah_offset, True,
            'America/New_York', NYC_LATLNG.lat, NYC_LATLNG.lng, results)


def make_jerusalem_test_params(dtime, results, havdalah_offset=0):
    """Make test params for Jerusalem."""
    return (dtime, CANDLE_LIGHT_DEFAULT, havdalah_offset, False,
            'Asia/Jerusalem', JERUSALEM_LATLNG.lat, JERUSALEM_LATLNG.lng,
            results)


class TestJewishCalenderSensor():
    """Test the Jewish Calendar sensor."""

    # pylint: disable=attribute-defined-outside-init
    def setup_method(self, method):
        """Set up things to run when tests begin."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()
        # Reset the default timezone, so we don't affect other tests
        set_default_time_zone(get_time_zone('UTC'))

    def test_jewish_calendar_min_config(self):
        """Test minimum jewish calendar configuration."""
        config = {
            'sensor': {
                'platform': 'jewish_calendar'
            }
        }
        assert setup_component(self.hass, 'sensor', config)

    def test_jewish_calendar_hebrew(self):
        """Test jewish calendar sensor with language set to hebrew."""
        config = {
            'sensor': {
                'platform': 'jewish_calendar',
                'language': 'hebrew',
            }
        }

        assert setup_component(self.hass, 'sensor', config)

    def test_jewish_calendar_multiple_sensors(self):
        """Test jewish calendar sensor with multiple sensors setup."""
        config = {
            'sensor': {
                'platform': 'jewish_calendar',
                'sensors': [
                    'date', 'weekly_portion', 'holiday_name',
                    'holyness', 'first_light', 'gra_end_shma',
                    'mga_end_shma', 'plag_mincha', 'first_stars'
                ]
            }
        }

        assert setup_component(self.hass, 'sensor', config)

    test_params = [
        (dt(2018, 9, 3), 'UTC', 31.778, 35.235, "english", "date",
         False, "23 Elul 5778"),
        (dt(2018, 9, 3), 'UTC', 31.778, 35.235, "hebrew", "date",
         False, "כ\"ג אלול ה\' תשע\"ח"),
        (dt(2018, 9, 10), 'UTC', 31.778, 35.235, "hebrew", "holiday_name",
         False, "א\' ראש השנה"),
        (dt(2018, 9, 10), 'UTC', 31.778, 35.235, "english", "holiday_name",
         False, "Rosh Hashana I"),
        (dt(2018, 9, 10), 'UTC', 31.778, 35.235, "english", "holyness",
         False, 1),
        (dt(2018, 9, 8), 'UTC', 31.778, 35.235, "hebrew", "weekly_portion",
         False, "נצבים"),
        (dt(2018, 9, 8), 'America/New_York', 40.7128, -74.0060, "hebrew",
         "first_stars", True, time(19, 48)),
        (dt(2018, 9, 8), "Asia/Jerusalem", 31.778, 35.235, "hebrew",
         "first_stars", False, time(19, 21)),
        (dt(2018, 10, 14), "Asia/Jerusalem", 31.778, 35.235, "hebrew",
         "weekly_portion", False, "לך לך"),
        (dt(2018, 10, 14, 17, 0, 0), "Asia/Jerusalem", 31.778, 35.235,
         "hebrew", "date", False, "ה\' מרחשוון ה\' תשע\"ט"),
        (dt(2018, 10, 14, 19, 0, 0), "Asia/Jerusalem", 31.778, 35.235,
         "hebrew", "date", False, "ו\' מרחשוון ה\' תשע\"ט")
    ]

    test_ids = [
        "date_output",
        "date_output_hebrew",
        "holiday_name",
        "holiday_name_english",
        "holyness",
        "torah_reading",
        "first_stars_ny",
        "first_stars_jerusalem",
        "torah_reading_weekday",
        "date_before_sunset",
        "date_after_sunset"
    ]

    @pytest.mark.parametrize(["cur_time", "tzname", "latitude", "longitude",
                              "language", "sensor", "diaspora", "result"],
                             test_params, ids=test_ids)
    def test_jewish_calendar_sensor(self, cur_time, tzname, latitude,
                                    longitude, language, sensor, diaspora,
                                    result):
        """Test Jewish calendar sensor output."""
        time_zone = get_time_zone(tzname)
        set_default_time_zone(time_zone)
        test_time = time_zone.localize(cur_time)
        self.hass.config.latitude = latitude
        self.hass.config.longitude = longitude
        sensor = JewishCalSensor(
            name='test', language=language, sensor_type=sensor,
            latitude=latitude, longitude=longitude,
            timezone=time_zone, diaspora=diaspora)
        sensor.hass = self.hass
        with patch('homeassistant.util.dt.now', return_value=test_time):
            run_coroutine_threadsafe(
                sensor.async_update(),
                self.hass.loop).result()
            assert sensor.state == result

    shabbat_params = [
        make_nyc_test_params(
            dt(2018, 9, 1, 16, 0),
            {'upcoming_shabbat_candle_lighting': dt(2018, 8, 31, 19, 15),
             'upcoming_shabbat_havdalah': dt(2018, 9, 1, 20, 14),
             'weekly_portion': 'Ki Tavo',
             'hebrew_weekly_portion': 'כי תבוא'}),
        make_nyc_test_params(
            dt(2018, 9, 1, 16, 0),
            {'upcoming_shabbat_candle_lighting': dt(2018, 8, 31, 19, 15),
             'upcoming_shabbat_havdalah': dt(2018, 9, 1, 20, 22),
             'weekly_portion': 'Ki Tavo',
             'hebrew_weekly_portion': 'כי תבוא'},
            havdalah_offset=50),
        make_nyc_test_params(
            dt(2018, 9, 1, 20, 0),
            {'upcoming_shabbat_candle_lighting': dt(2018, 8, 31, 19, 15),
             'upcoming_shabbat_havdalah': dt(2018, 9, 1, 20, 14),
             'upcoming_candle_lighting': dt(2018, 8, 31, 19, 15),
             'upcoming_havdalah': dt(2018, 9, 1, 20, 14),
             'weekly_portion': 'Ki Tavo',
             'hebrew_weekly_portion': 'כי תבוא'}),
        make_nyc_test_params(
            dt(2018, 9, 1, 20, 21),
            {'upcoming_shabbat_candle_lighting': dt(2018, 9, 7, 19, 4),
             'upcoming_shabbat_havdalah': dt(2018, 9, 8, 20, 2),
             'weekly_portion': 'Nitzavim',
             'hebrew_weekly_portion': 'נצבים'}),
        make_nyc_test_params(
            dt(2018, 9, 7, 13, 1),
            {'upcoming_shabbat_candle_lighting': dt(2018, 9, 7, 19, 4),
             'upcoming_shabbat_havdalah': dt(2018, 9, 8, 20, 2),
             'weekly_portion': 'Nitzavim',
             'hebrew_weekly_portion': 'נצבים'}),
        make_nyc_test_params(
            dt(2018, 9, 8, 21, 25),
            {'upcoming_candle_lighting': dt(2018, 9, 9, 19, 1),
             'upcoming_havdalah': dt(2018, 9, 11, 19, 57),
             'upcoming_shabbat_candle_lighting': dt(2018, 9, 14, 18, 52),
             'upcoming_shabbat_havdalah': dt(2018, 9, 15, 19, 50),
             'weekly_portion': 'Vayeilech',
             'hebrew_weekly_portion': 'וילך',
             'holiday_name': 'Erev Rosh Hashana',
             'hebrew_holiday_name': 'ערב ראש השנה'}),
        make_nyc_test_params(
            dt(2018, 9, 9, 21, 25),
            {'upcoming_candle_lighting': dt(2018, 9, 9, 19, 1),
             'upcoming_havdalah': dt(2018, 9, 11, 19, 57),
             'upcoming_shabbat_candle_lighting': dt(2018, 9, 14, 18, 52),
             'upcoming_shabbat_havdalah': dt(2018, 9, 15, 19, 50),
             'weekly_portion': 'Vayeilech',
             'hebrew_weekly_portion': 'וילך',
             'holiday_name': 'Rosh Hashana I',
             'hebrew_holiday_name': "א' ראש השנה"}),
        make_nyc_test_params(
            dt(2018, 9, 10, 21, 25),
            {'upcoming_candle_lighting': dt(2018, 9, 9, 19, 1),
             'upcoming_havdalah': dt(2018, 9, 11, 19, 57),
             'upcoming_shabbat_candle_lighting': dt(2018, 9, 14, 18, 52),
             'upcoming_shabbat_havdalah': dt(2018, 9, 15, 19, 50),
             'weekly_portion': 'Vayeilech',
             'hebrew_weekly_portion': 'וילך',
             'holiday_name': 'Rosh Hashana II',
             'hebrew_holiday_name': "ב' ראש השנה"}),
        make_nyc_test_params(
            dt(2018, 9, 28, 21, 25),
            {'upcoming_shabbat_candle_lighting': dt(2018, 9, 28, 18, 28),
             'upcoming_shabbat_havdalah': dt(2018, 9, 29, 19, 25),
             'weekly_portion': 'none',
             'hebrew_weekly_portion': 'none'}),
        make_nyc_test_params(
            dt(2018, 9, 29, 21, 25),
            {'upcoming_candle_lighting': dt(2018, 9, 30, 18, 25),
             'upcoming_havdalah': dt(2018, 10, 2, 19, 20),
             'upcoming_shabbat_candle_lighting': dt(2018, 10, 5, 18, 17),
             'upcoming_shabbat_havdalah': dt(2018, 10, 6, 19, 13),
             'weekly_portion': 'Bereshit',
             'hebrew_weekly_portion': 'בראשית',
             'holiday_name': 'Hoshana Raba',
             'hebrew_holiday_name': 'הושענא רבה'}),
        make_nyc_test_params(
            dt(2018, 9, 30, 21, 25),
            {'upcoming_candle_lighting': dt(2018, 9, 30, 18, 25),
             'upcoming_havdalah': dt(2018, 10, 2, 19, 20),
             'upcoming_shabbat_candle_lighting': dt(2018, 10, 5, 18, 17),
             'upcoming_shabbat_havdalah': dt(2018, 10, 6, 19, 13),
             'weekly_portion': 'Bereshit',
             'hebrew_weekly_portion': 'בראשית',
             'holiday_name': 'Shmini Atzeret',
             'hebrew_holiday_name': 'שמיני עצרת'}),
        make_nyc_test_params(
            dt(2018, 10, 1, 21, 25),
            {'upcoming_candle_lighting': dt(2018, 9, 30, 18, 25),
             'upcoming_havdalah': dt(2018, 10, 2, 19, 20),
             'upcoming_shabbat_candle_lighting': dt(2018, 10, 5, 18, 17),
             'upcoming_shabbat_havdalah': dt(2018, 10, 6, 19, 13),
             'weekly_portion': 'Bereshit',
             'hebrew_weekly_portion': 'בראשית',
             'holiday_name': 'Simchat Torah',
             'hebrew_holiday_name': 'שמחת תורה'}),
        make_jerusalem_test_params(
            dt(2018, 9, 29, 21, 25),
            {'upcoming_candle_lighting': dt(2018, 9, 30, 18, 10),
             'upcoming_havdalah': dt(2018, 10, 1, 19, 2),
             'upcoming_shabbat_candle_lighting': dt(2018, 10, 5, 18, 3),
             'upcoming_shabbat_havdalah': dt(2018, 10, 6, 18, 56),
             'weekly_portion': 'Bereshit',
             'hebrew_weekly_portion': 'בראשית',
             'holiday_name': 'Hoshana Raba',
             'hebrew_holiday_name': 'הושענא רבה'}),
        make_jerusalem_test_params(
            dt(2018, 9, 30, 21, 25),
            {'upcoming_candle_lighting': dt(2018, 9, 30, 18, 10),
             'upcoming_havdalah': dt(2018, 10, 1, 19, 2),
             'upcoming_shabbat_candle_lighting': dt(2018, 10, 5, 18, 3),
             'upcoming_shabbat_havdalah': dt(2018, 10, 6, 18, 56),
             'weekly_portion': 'Bereshit',
             'hebrew_weekly_portion': 'בראשית',
             'holiday_name': 'Shmini Atzeret',
             'hebrew_holiday_name': 'שמיני עצרת'}),
        make_jerusalem_test_params(
            dt(2018, 10, 1, 21, 25),
            {'upcoming_shabbat_candle_lighting': dt(2018, 10, 5, 18, 3),
             'upcoming_shabbat_havdalah': dt(2018, 10, 6, 18, 56),
             'weekly_portion': 'Bereshit',
             'hebrew_weekly_portion': 'בראשית'}),
        make_nyc_test_params(
            dt(2016, 6, 11, 8, 25),
            {'upcoming_candle_lighting': dt(2016, 6, 10, 20, 7),
             'upcoming_havdalah': dt(2016, 6, 13, 21, 17),
             'upcoming_shabbat_candle_lighting': dt(2016, 6, 10, 20, 7),
             'upcoming_shabbat_havdalah': None,
             'weekly_portion': 'Bamidbar',
             'hebrew_weekly_portion': 'במדבר',
             'holiday_name': 'Erev Shavuot',
             'hebrew_holiday_name': 'ערב שבועות'}),
        make_nyc_test_params(
            dt(2016, 6, 12, 8, 25),
            {'upcoming_candle_lighting': dt(2016, 6, 10, 20, 7),
             'upcoming_havdalah': dt(2016, 6, 13, 21, 17),
             'upcoming_shabbat_candle_lighting': dt(2016, 6, 17, 20, 10),
             'upcoming_shabbat_havdalah': dt(2016, 6, 18, 21, 19),
             'weekly_portion': 'Nasso',
             'hebrew_weekly_portion': 'נשא',
             'holiday_name': 'Shavuot',
             'hebrew_holiday_name': 'שבועות'}),
        make_jerusalem_test_params(
            dt(2017, 9, 21, 8, 25),
            {'upcoming_candle_lighting': dt(2017, 9, 20, 18, 23),
             'upcoming_havdalah': dt(2017, 9, 23, 19, 13),
             'upcoming_shabbat_candle_lighting': dt(2017, 9, 22, 19, 14),
             'upcoming_shabbat_havdalah': dt(2017, 9, 23, 19, 13),
             'weekly_portion': "Ha'Azinu",
             'hebrew_weekly_portion': 'האזינו',
             'holiday_name': 'Rosh Hashana I',
             'hebrew_holiday_name': "א' ראש השנה"}),
        make_jerusalem_test_params(
            dt(2017, 9, 22, 8, 25),
            {'upcoming_candle_lighting': dt(2017, 9, 20, 18, 23),
             'upcoming_havdalah': dt(2017, 9, 23, 19, 13),
             'upcoming_shabbat_candle_lighting': dt(2017, 9, 22, 19, 14),
             'upcoming_shabbat_havdalah': dt(2017, 9, 23, 19, 13),
             'weekly_portion': "Ha'Azinu",
             'hebrew_weekly_portion': 'האזינו',
             'holiday_name': 'Rosh Hashana II',
             'hebrew_holiday_name': "ב' ראש השנה"}),
        make_jerusalem_test_params(
            dt(2017, 9, 23, 8, 25),
            {'upcoming_candle_lighting': dt(2017, 9, 20, 18, 23),
             'upcoming_havdalah': dt(2017, 9, 23, 19, 13),
             'upcoming_shabbat_candle_lighting': dt(2017, 9, 22, 19, 14),
             'upcoming_shabbat_havdalah': dt(2017, 9, 23, 19, 13),
             'weekly_portion': "Ha'Azinu",
             'hebrew_weekly_portion': 'האזינו',
             'holiday_name': '',
             'hebrew_holiday_name': ''}),
    ]

    shabbat_test_ids = [
        "currently_first_shabbat",
        "currently_first_shabbat_with_havdalah_offset",
        "currently_first_shabbat_bein_hashmashot_lagging_date",
        "after_first_shabbat",
        "friday_upcoming_shabbat",
        "upcoming_rosh_hashana",
        "currently_rosh_hashana",
        "second_day_rosh_hashana",
        "currently_shabbat_chol_hamoed",
        "upcoming_two_day_yomtov_in_diaspora",
        "currently_first_day_of_two_day_yomtov_in_diaspora",
        "currently_second_day_of_two_day_yomtov_in_diaspora",
        "upcoming_one_day_yom_tov_in_israel",
        "currently_one_day_yom_tov_in_israel",
        "after_one_day_yom_tov_in_israel",
        # Type 1 = Sat/Sun/Mon
        "currently_first_day_of_three_day_type1_yomtov_in_diaspora",
        "currently_second_day_of_three_day_type1_yomtov_in_diaspora",
        # Type 2 = Thurs/Fri/Sat
        "currently_first_day_of_three_day_type2_yomtov_in_israel",
        "currently_second_day_of_three_day_type2_yomtov_in_israel",
        "currently_third_day_of_three_day_type2_yomtov_in_israel",
    ]

    @pytest.mark.parametrize(["now", "candle_lighting", "havdalah", "diaspora",
                              "tzname", "latitude", "longitude", "result"],
                             shabbat_params, ids=shabbat_test_ids)
    def test_shabbat_times_sensor(self, now, candle_lighting, havdalah,
                                  diaspora, tzname, latitude, longitude,
                                  result):
        """Test sensor output for upcoming shabbat/yomtov times."""
        time_zone = get_time_zone(tzname)
        set_default_time_zone(time_zone)
        test_time = time_zone.localize(now)
        for sensor_type, value in result.items():
            if isinstance(value, dt):
                result[sensor_type] = time_zone.localize(value)
        self.hass.config.latitude = latitude
        self.hass.config.longitude = longitude

        if ('upcoming_shabbat_candle_lighting' in result
                and 'upcoming_candle_lighting' not in result):
            result['upcoming_candle_lighting'] = \
                result['upcoming_shabbat_candle_lighting']
        if ('upcoming_shabbat_havdalah' in result
                and 'upcoming_havdalah' not in result):
            result['upcoming_havdalah'] = result['upcoming_shabbat_havdalah']

        for sensor_type, result_value in result.items():
            language = 'english'
            if sensor_type.startswith('hebrew_'):
                language = 'hebrew'
                sensor_type = sensor_type.replace('hebrew_', '')
            sensor = JewishCalSensor(
                name='test', language=language, sensor_type=sensor_type,
                latitude=latitude, longitude=longitude,
                timezone=time_zone, diaspora=diaspora,
                havdalah_offset=havdalah,
                candle_lighting_offset=candle_lighting)
            sensor.hass = self.hass
            with patch('homeassistant.util.dt.now', return_value=test_time):
                run_coroutine_threadsafe(
                    sensor.async_update(),
                    self.hass.loop).result()
                assert sensor.state == result_value, "Value for {}".format(
                    sensor_type)

    melacha_params = [
        make_nyc_test_params(dt(2018, 9, 1, 16, 0), True),
        make_nyc_test_params(dt(2018, 9, 1, 20, 21), False),
        make_nyc_test_params(dt(2018, 9, 7, 13, 1), False),
        make_nyc_test_params(dt(2018, 9, 8, 21, 25), False),
        make_nyc_test_params(dt(2018, 9, 9, 21, 25), True),
        make_nyc_test_params(dt(2018, 9, 10, 21, 25), True),
        make_nyc_test_params(dt(2018, 9, 28, 21, 25), True),
        make_nyc_test_params(dt(2018, 9, 29, 21, 25), False),
        make_nyc_test_params(dt(2018, 9, 30, 21, 25), True),
        make_nyc_test_params(dt(2018, 10, 1, 21, 25), True),
        make_jerusalem_test_params(dt(2018, 9, 29, 21, 25), False),
        make_jerusalem_test_params(dt(2018, 9, 30, 21, 25), True),
        make_jerusalem_test_params(dt(2018, 10, 1, 21, 25), False),
    ]
    melacha_test_ids = [
        "currently_first_shabbat",
        "after_first_shabbat",
        "friday_upcoming_shabbat",
        "upcoming_rosh_hashana",
        "currently_rosh_hashana",
        "second_day_rosh_hashana",
        "currently_shabbat_chol_hamoed",
        "upcoming_two_day_yomtov_in_diaspora",
        "currently_first_day_of_two_day_yomtov_in_diaspora",
        "currently_second_day_of_two_day_yomtov_in_diaspora",
        "upcoming_one_day_yom_tov_in_israel",
        "currently_one_day_yom_tov_in_israel",
        "after_one_day_yom_tov_in_israel",
    ]

    @pytest.mark.parametrize(["now", "candle_lighting", "havdalah", "diaspora",
                              "tzname", "latitude", "longitude", "result"],
                             melacha_params, ids=melacha_test_ids)
    def test_issur_melacha_sensor(self, now, candle_lighting, havdalah,
                                  diaspora, tzname, latitude, longitude,
                                  result):
        """Test Issur Melacha sensor output."""
        time_zone = get_time_zone(tzname)
        set_default_time_zone(time_zone)
        test_time = time_zone.localize(now)
        self.hass.config.latitude = latitude
        self.hass.config.longitude = longitude
        sensor = JewishCalSensor(
            name='test', language='english',
            sensor_type='issur_melacha_in_effect',
            latitude=latitude, longitude=longitude,
            timezone=time_zone, diaspora=diaspora, havdalah_offset=havdalah,
            candle_lighting_offset=candle_lighting)
        sensor.hass = self.hass
        with patch('homeassistant.util.dt.now', return_value=test_time):
            run_coroutine_threadsafe(
                sensor.async_update(),
                self.hass.loop).result()
            assert sensor.state == result
