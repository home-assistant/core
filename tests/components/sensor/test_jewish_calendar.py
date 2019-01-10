"""The tests for the Jewish calendar sensor platform."""
from datetime import time
from datetime import datetime as dt
from unittest.mock import patch

import pytest

from homeassistant.util.async_ import run_coroutine_threadsafe
from homeassistant.util.dt import get_time_zone, set_default_time_zone
from homeassistant.setup import setup_component
from homeassistant.components.sensor.jewish_calendar import JewishCalSensor
from tests.common import get_test_home_assistant


class TestJewishCalenderSensor():
    """Test the Jewish Calendar sensor."""

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

    @pytest.mark.parametrize(["time", "tzname", "latitude", "longitude",
                              "language", "sensor", "diaspora", "result"],
                             test_params, ids=test_ids)
    def test_jewish_calendar_sensor(self, time, tzname, latitude, longitude,
                                    language, sensor, diaspora, result):
        """Test Jewish calendar sensor output."""
        tz = get_time_zone(tzname)
        set_default_time_zone(tz)
        test_time = tz.localize(time)
        self.hass.config.latitude = latitude
        self.hass.config.longitude = longitude
        sensor = JewishCalSensor(
            name='test', language=language, sensor_type=sensor,
            latitude=latitude, longitude=longitude,
            timezone=tz, diaspora=diaspora)
        sensor.hass = self.hass
        with patch('homeassistant.util.dt.now', return_value=test_time):
            run_coroutine_threadsafe(
                sensor.async_update(),
                self.hass.loop).result()
            assert sensor.state == result
