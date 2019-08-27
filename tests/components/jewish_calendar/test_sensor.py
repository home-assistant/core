"""The tests for the Jewish calendar sensor platform."""
from collections import namedtuple
from contextlib import contextmanager
from datetime import time
from datetime import datetime as dt
from unittest.mock import patch

import pytest

from homeassistant.util.dt import get_time_zone
from homeassistant.setup import async_setup_component
from homeassistant.components import jewish_calendar


_LatLng = namedtuple("_LatLng", ["lat", "lng"])

NYC_LATLNG = _LatLng(40.7128, -74.0060)
JERUSALEM_LATLNG = _LatLng(31.778, 35.235)


def make_nyc_test_params(dtime, results, havdalah_offset=0):
    """Make test params for NYC."""
    return (
        dtime,
        jewish_calendar.CANDLE_LIGHT_DEFAULT,
        havdalah_offset,
        True,
        "America/New_York",
        NYC_LATLNG.lat,
        NYC_LATLNG.lng,
        results,
    )


def make_jerusalem_test_params(dtime, results, havdalah_offset=0):
    """Make test params for Jerusalem."""
    return (
        dtime,
        jewish_calendar.CANDLE_LIGHT_DEFAULT,
        havdalah_offset,
        False,
        "Asia/Jerusalem",
        JERUSALEM_LATLNG.lat,
        JERUSALEM_LATLNG.lng,
        results,
    )


@contextmanager
def alter_time(retval):
    """Manage multiple time mocks."""
    patch1 = patch("homeassistant.util.dt.utcnow", return_value=retval)
    patch2 = patch("homeassistant.util.dt.now", return_value=retval)

    with patch1, patch2:
        yield


class TestJewishCalenderSensor:
    """Test the Jewish Calendar sensor."""

    async def test_jewish_calendar_min_config(self, hass):
        """Test minimum jewish calendar configuration."""
        assert await async_setup_component(
            hass, jewish_calendar.DOMAIN, {"jewish_calendar": {}}
        )
        await hass.async_block_till_done()
        assert hass.states.get("sensor.jewish_calendar_date") is not None

    async def test_jewish_calendar_hebrew(self, hass):
        """Test jewish calendar sensor with language set to hebrew."""
        assert await async_setup_component(
            hass, jewish_calendar.DOMAIN, {"jewish_calendar": {"language": "hebrew"}}
        )
        await hass.async_block_till_done()
        assert hass.states.get("sensor.jewish_calendar_date") is not None

    test_params = [
        (
            dt(2018, 9, 3),
            "UTC",
            31.778,
            35.235,
            "english",
            "date",
            False,
            "23 Elul 5778",
        ),
        (
            dt(2018, 9, 3),
            "UTC",
            31.778,
            35.235,
            "hebrew",
            "date",
            False,
            'כ"ג אלול ה\' תשע"ח',
        ),
        (
            dt(2018, 9, 10),
            "UTC",
            31.778,
            35.235,
            "hebrew",
            "holiday_name",
            False,
            "א' ראש השנה",
        ),
        (
            dt(2018, 9, 10),
            "UTC",
            31.778,
            35.235,
            "english",
            "holiday_name",
            False,
            "Rosh Hashana I",
        ),
        (dt(2018, 9, 10), "UTC", 31.778, 35.235, "english", "holiday_type", False, 1),
        (
            dt(2018, 9, 8),
            "UTC",
            31.778,
            35.235,
            "hebrew",
            "parshat_hashavua",
            False,
            "נצבים",
        ),
        (
            dt(2018, 9, 8),
            "America/New_York",
            40.7128,
            -74.0060,
            "hebrew",
            "t_set_hakochavim",
            True,
            time(19, 48),
        ),
        (
            dt(2018, 9, 8),
            "Asia/Jerusalem",
            31.778,
            35.235,
            "hebrew",
            "t_set_hakochavim",
            False,
            time(19, 21),
        ),
        (
            dt(2018, 10, 14),
            "Asia/Jerusalem",
            31.778,
            35.235,
            "hebrew",
            "parshat_hashavua",
            False,
            "לך לך",
        ),
        (
            dt(2018, 10, 14, 17, 0, 0),
            "Asia/Jerusalem",
            31.778,
            35.235,
            "hebrew",
            "date",
            False,
            "ה' מרחשוון ה' תשע\"ט",
        ),
        (
            dt(2018, 10, 14, 19, 0, 0),
            "Asia/Jerusalem",
            31.778,
            35.235,
            "hebrew",
            "date",
            False,
            "ו' מרחשוון ה' תשע\"ט",
        ),
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
        "date_after_sunset",
    ]

    @pytest.mark.parametrize(
        [
            "cur_time",
            "tzname",
            "latitude",
            "longitude",
            "language",
            "sensor",
            "diaspora",
            "result",
        ],
        test_params,
        ids=test_ids,
    )
    async def test_jewish_calendar_sensor(
        self,
        hass,
        cur_time,
        tzname,
        latitude,
        longitude,
        language,
        sensor,
        diaspora,
        result,
    ):
        """Test Jewish calendar sensor output."""
        time_zone = get_time_zone(tzname)
        test_time = time_zone.localize(cur_time)

        hass.config.set_time_zone(tzname)
        hass.config.latitude = latitude
        hass.config.longitude = longitude

        assert await async_setup_component(
            hass,
            jewish_calendar.DOMAIN,
            {
                "jewish_calendar": {
                    "name": "test",
                    "language": language,
                    "diaspora": diaspora,
                }
            },
        )
        await hass.async_block_till_done()

        with alter_time(test_time):
            await hass.helpers.entity_component.async_update_entity(
                f"sensor.test_{sensor}"
            )

        assert hass.states.get(f"sensor.test_{sensor}").state == str(result)

    shabbat_params = [
        make_nyc_test_params(
            dt(2018, 9, 1, 16, 0),
            {
                "upcoming_candle_lighting": dt(2018, 8, 31, 19, 15),
                "upcoming_havdalah": dt(2018, 9, 1, 20, 14),
                "upcoming_shabbat_candle_lighting": dt(2018, 8, 31, 19, 15),
                "upcoming_shabbat_havdalah": dt(2018, 9, 1, 20, 14),
                "weekly_portion": "Ki Tavo",
                "hebrew_weekly_portion": "כי תבוא",
            },
        ),
        make_nyc_test_params(
            dt(2018, 9, 1, 16, 0),
            {
                "upcoming_candle_lighting": dt(2018, 8, 31, 19, 15),
                "upcoming_havdalah": dt(2018, 9, 1, 20, 22),
                "upcoming_shabbat_candle_lighting": dt(2018, 8, 31, 19, 15),
                "upcoming_shabbat_havdalah": dt(2018, 9, 1, 20, 22),
                "weekly_portion": "Ki Tavo",
                "hebrew_weekly_portion": "כי תבוא",
            },
            havdalah_offset=50,
        ),
        make_nyc_test_params(
            dt(2018, 9, 1, 20, 0),
            {
                "upcoming_shabbat_candle_lighting": dt(2018, 8, 31, 19, 15),
                "upcoming_shabbat_havdalah": dt(2018, 9, 1, 20, 14),
                "upcoming_candle_lighting": dt(2018, 8, 31, 19, 15),
                "upcoming_havdalah": dt(2018, 9, 1, 20, 14),
                "weekly_portion": "Ki Tavo",
                "hebrew_weekly_portion": "כי תבוא",
            },
        ),
        make_nyc_test_params(
            dt(2018, 9, 1, 20, 21),
            {
                "upcoming_candle_lighting": dt(2018, 9, 7, 19, 4),
                "upcoming_havdalah": dt(2018, 9, 8, 20, 2),
                "upcoming_shabbat_candle_lighting": dt(2018, 9, 7, 19, 4),
                "upcoming_shabbat_havdalah": dt(2018, 9, 8, 20, 2),
                "weekly_portion": "Nitzavim",
                "hebrew_weekly_portion": "נצבים",
            },
        ),
        make_nyc_test_params(
            dt(2018, 9, 7, 13, 1),
            {
                "upcoming_candle_lighting": dt(2018, 9, 7, 19, 4),
                "upcoming_havdalah": dt(2018, 9, 8, 20, 2),
                "upcoming_shabbat_candle_lighting": dt(2018, 9, 7, 19, 4),
                "upcoming_shabbat_havdalah": dt(2018, 9, 8, 20, 2),
                "weekly_portion": "Nitzavim",
                "hebrew_weekly_portion": "נצבים",
            },
        ),
        make_nyc_test_params(
            dt(2018, 9, 8, 21, 25),
            {
                "upcoming_candle_lighting": dt(2018, 9, 9, 19, 1),
                "upcoming_havdalah": dt(2018, 9, 11, 19, 57),
                "upcoming_shabbat_candle_lighting": dt(2018, 9, 14, 18, 52),
                "upcoming_shabbat_havdalah": dt(2018, 9, 15, 19, 50),
                "weekly_portion": "Vayeilech",
                "hebrew_weekly_portion": "וילך",
                "holiday_name": "Erev Rosh Hashana",
                "hebrew_holiday_name": "ערב ראש השנה",
            },
        ),
        make_nyc_test_params(
            dt(2018, 9, 9, 21, 25),
            {
                "upcoming_candle_lighting": dt(2018, 9, 9, 19, 1),
                "upcoming_havdalah": dt(2018, 9, 11, 19, 57),
                "upcoming_shabbat_candle_lighting": dt(2018, 9, 14, 18, 52),
                "upcoming_shabbat_havdalah": dt(2018, 9, 15, 19, 50),
                "weekly_portion": "Vayeilech",
                "hebrew_weekly_portion": "וילך",
                "holiday_name": "Rosh Hashana I",
                "hebrew_holiday_name": "א' ראש השנה",
            },
        ),
        make_nyc_test_params(
            dt(2018, 9, 10, 21, 25),
            {
                "upcoming_candle_lighting": dt(2018, 9, 9, 19, 1),
                "upcoming_havdalah": dt(2018, 9, 11, 19, 57),
                "upcoming_shabbat_candle_lighting": dt(2018, 9, 14, 18, 52),
                "upcoming_shabbat_havdalah": dt(2018, 9, 15, 19, 50),
                "weekly_portion": "Vayeilech",
                "hebrew_weekly_portion": "וילך",
                "holiday_name": "Rosh Hashana II",
                "hebrew_holiday_name": "ב' ראש השנה",
            },
        ),
        make_nyc_test_params(
            dt(2018, 9, 28, 21, 25),
            {
                "upcoming_candle_lighting": dt(2018, 9, 28, 18, 28),
                "upcoming_havdalah": dt(2018, 9, 29, 19, 25),
                "upcoming_shabbat_candle_lighting": dt(2018, 9, 28, 18, 28),
                "upcoming_shabbat_havdalah": dt(2018, 9, 29, 19, 25),
                "weekly_portion": "none",
                "hebrew_weekly_portion": "none",
            },
        ),
        make_nyc_test_params(
            dt(2018, 9, 29, 21, 25),
            {
                "upcoming_candle_lighting": dt(2018, 9, 30, 18, 25),
                "upcoming_havdalah": dt(2018, 10, 2, 19, 20),
                "upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 18, 17),
                "upcoming_shabbat_havdalah": dt(2018, 10, 6, 19, 13),
                "weekly_portion": "Bereshit",
                "hebrew_weekly_portion": "בראשית",
                "holiday_name": "Hoshana Raba",
                "hebrew_holiday_name": "הושענא רבה",
            },
        ),
        make_nyc_test_params(
            dt(2018, 9, 30, 21, 25),
            {
                "upcoming_candle_lighting": dt(2018, 9, 30, 18, 25),
                "upcoming_havdalah": dt(2018, 10, 2, 19, 20),
                "upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 18, 17),
                "upcoming_shabbat_havdalah": dt(2018, 10, 6, 19, 13),
                "weekly_portion": "Bereshit",
                "hebrew_weekly_portion": "בראשית",
                "holiday_name": "Shmini Atzeret",
                "hebrew_holiday_name": "שמיני עצרת",
            },
        ),
        make_nyc_test_params(
            dt(2018, 10, 1, 21, 25),
            {
                "upcoming_candle_lighting": dt(2018, 9, 30, 18, 25),
                "upcoming_havdalah": dt(2018, 10, 2, 19, 20),
                "upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 18, 17),
                "upcoming_shabbat_havdalah": dt(2018, 10, 6, 19, 13),
                "weekly_portion": "Bereshit",
                "hebrew_weekly_portion": "בראשית",
                "holiday_name": "Simchat Torah",
                "hebrew_holiday_name": "שמחת תורה",
            },
        ),
        make_jerusalem_test_params(
            dt(2018, 9, 29, 21, 25),
            {
                "upcoming_candle_lighting": dt(2018, 9, 30, 18, 10),
                "upcoming_havdalah": dt(2018, 10, 1, 19, 2),
                "upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 18, 3),
                "upcoming_shabbat_havdalah": dt(2018, 10, 6, 18, 56),
                "weekly_portion": "Bereshit",
                "hebrew_weekly_portion": "בראשית",
                "holiday_name": "Hoshana Raba",
                "hebrew_holiday_name": "הושענא רבה",
            },
        ),
        make_jerusalem_test_params(
            dt(2018, 9, 30, 21, 25),
            {
                "upcoming_candle_lighting": dt(2018, 9, 30, 18, 10),
                "upcoming_havdalah": dt(2018, 10, 1, 19, 2),
                "upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 18, 3),
                "upcoming_shabbat_havdalah": dt(2018, 10, 6, 18, 56),
                "weekly_portion": "Bereshit",
                "hebrew_weekly_portion": "בראשית",
                "holiday_name": "Shmini Atzeret",
                "hebrew_holiday_name": "שמיני עצרת",
            },
        ),
        make_jerusalem_test_params(
            dt(2018, 10, 1, 21, 25),
            {
                "upcoming_candle_lighting": dt(2018, 10, 5, 18, 3),
                "upcoming_havdalah": dt(2018, 10, 6, 18, 56),
                "upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 18, 3),
                "upcoming_shabbat_havdalah": dt(2018, 10, 6, 18, 56),
                "weekly_portion": "Bereshit",
                "hebrew_weekly_portion": "בראשית",
            },
        ),
        make_nyc_test_params(
            dt(2016, 6, 11, 8, 25),
            {
                "upcoming_candle_lighting": dt(2016, 6, 10, 20, 7),
                "upcoming_havdalah": dt(2016, 6, 13, 21, 17),
                "upcoming_shabbat_candle_lighting": dt(2016, 6, 10, 20, 7),
                "upcoming_shabbat_havdalah": None,
                "weekly_portion": "Bamidbar",
                "hebrew_weekly_portion": "במדבר",
                "holiday_name": "Erev Shavuot",
                "hebrew_holiday_name": "ערב שבועות",
            },
        ),
        make_nyc_test_params(
            dt(2016, 6, 12, 8, 25),
            {
                "upcoming_candle_lighting": dt(2016, 6, 10, 20, 7),
                "upcoming_havdalah": dt(2016, 6, 13, 21, 17),
                "upcoming_shabbat_candle_lighting": dt(2016, 6, 17, 20, 10),
                "upcoming_shabbat_havdalah": dt(2016, 6, 18, 21, 19),
                "weekly_portion": "Nasso",
                "hebrew_weekly_portion": "נשא",
                "holiday_name": "Shavuot",
                "hebrew_holiday_name": "שבועות",
            },
        ),
        make_jerusalem_test_params(
            dt(2017, 9, 21, 8, 25),
            {
                "upcoming_candle_lighting": dt(2017, 9, 20, 18, 23),
                "upcoming_havdalah": dt(2017, 9, 23, 19, 13),
                "upcoming_shabbat_candle_lighting": dt(2017, 9, 22, 19, 14),
                "upcoming_shabbat_havdalah": dt(2017, 9, 23, 19, 13),
                "weekly_portion": "Ha'Azinu",
                "hebrew_weekly_portion": "האזינו",
                "holiday_name": "Rosh Hashana I",
                "hebrew_holiday_name": "א' ראש השנה",
            },
        ),
        make_jerusalem_test_params(
            dt(2017, 9, 22, 8, 25),
            {
                "upcoming_candle_lighting": dt(2017, 9, 20, 18, 23),
                "upcoming_havdalah": dt(2017, 9, 23, 19, 13),
                "upcoming_shabbat_candle_lighting": dt(2017, 9, 22, 19, 14),
                "upcoming_shabbat_havdalah": dt(2017, 9, 23, 19, 13),
                "weekly_portion": "Ha'Azinu",
                "hebrew_weekly_portion": "האזינו",
                "holiday_name": "Rosh Hashana II",
                "hebrew_holiday_name": "ב' ראש השנה",
            },
        ),
        make_jerusalem_test_params(
            dt(2017, 9, 23, 8, 25),
            {
                "upcoming_candle_lighting": dt(2017, 9, 20, 18, 23),
                "upcoming_havdalah": dt(2017, 9, 23, 19, 13),
                "upcoming_shabbat_candle_lighting": dt(2017, 9, 22, 19, 14),
                "upcoming_shabbat_havdalah": dt(2017, 9, 23, 19, 13),
                "weekly_portion": "Ha'Azinu",
                "hebrew_weekly_portion": "האזינו",
                "holiday_name": "",
                "hebrew_holiday_name": "",
            },
        ),
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

    @pytest.mark.parametrize(
        [
            "now",
            "candle_lighting",
            "havdalah",
            "diaspora",
            "tzname",
            "latitude",
            "longitude",
            "result",
        ],
        shabbat_params,
        ids=shabbat_test_ids,
    )
    async def test_shabbat_times_sensor(
        self,
        hass,
        now,
        candle_lighting,
        havdalah,
        diaspora,
        tzname,
        latitude,
        longitude,
        result,
    ):
        """Test sensor output for upcoming shabbat/yomtov times."""
        time_zone = get_time_zone(tzname)
        test_time = time_zone.localize(now)

        hass.config.set_time_zone(tzname)
        for sensor_type, value in result.items():
            if isinstance(value, dt):
                result[sensor_type] = time_zone.localize(value)
        hass.config.latitude = latitude
        hass.config.longitude = longitude

        for sensor_type, result_value in result.items():
            language = "english"
            if sensor_type.startswith("hebrew_"):
                language = "hebrew"
                sensor_type = sensor_type.replace("hebrew_", "")

            assert await async_setup_component(
                hass,
                jewish_calendar.DOMAIN,
                {
                    "jewish_calendar": {
                        "name": "test",
                        "language": language,
                        "diaspora": diaspora,
                        "candle_lighting_minutes_before_sunset": candle_lighting,
                        "havdalah_minutes_after_sunset": havdalah,
                    }
                },
            )
            await hass.async_block_till_done()

            with alter_time(test_time):
                await hass.helpers.entity_component.async_update_entity(
                    f"sensor.test_{sensor_type}"
                )
            assert (
                hass.states.get(f"sensor.test_{sensor_type}").state == str(result_value)
            ), f"Value for {sensor_type}"

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

    @pytest.mark.parametrize(
        [
            "now",
            "candle_lighting",
            "havdalah",
            "diaspora",
            "tzname",
            "latitude",
            "longitude",
            "result",
        ],
        melacha_params,
        ids=melacha_test_ids,
    )
    async def test_issur_melacha_sensor(
        self,
        hass,
        now,
        candle_lighting,
        havdalah,
        diaspora,
        tzname,
        latitude,
        longitude,
        result,
    ):
        """Test Issur Melacha sensor output."""
        time_zone = get_time_zone(tzname)
        test_time = time_zone.localize(now)

        hass.config.set_time_zone(tzname)
        hass.config.latitude = latitude
        hass.config.longitude = longitude

        assert await async_setup_component(
            hass,
            jewish_calendar.DOMAIN,
            {
                "jewish_calendar": {
                    "name": "test",
                    "language": "english",
                    "diaspora": diaspora,
                    "candle_lighting_minutes_before_sunset": candle_lighting,
                    "havdalah_minutes_after_sunset": havdalah,
                }
            },
        )
        await hass.async_block_till_done()

        with alter_time(test_time):
            await hass.helpers.entity_component.async_update_entity(
                "binary_sensor.test_issur_melacha_in_effect"
            )

        assert (
            hass.states.get("binary_sensor.test_issur_melacha_in_effect").state
            == result
        )

    omer_params = [
        make_nyc_test_params(dt(2019, 4, 21, 0, 0), 1),
        make_jerusalem_test_params(dt(2019, 4, 21, 0, 0), 1),
        make_nyc_test_params(dt(2019, 4, 21, 23, 0), 2),
        make_jerusalem_test_params(dt(2019, 4, 21, 23, 0), 2),
        make_nyc_test_params(dt(2019, 5, 23, 0, 0), 33),
        make_jerusalem_test_params(dt(2019, 5, 23, 0, 0), 33),
        make_nyc_test_params(dt(2019, 6, 8, 0, 0), 49),
        make_jerusalem_test_params(dt(2019, 6, 8, 0, 0), 49),
        make_nyc_test_params(dt(2019, 6, 9, 0, 0), 0),
        make_jerusalem_test_params(dt(2019, 6, 9, 0, 0), 0),
        make_nyc_test_params(dt(2019, 1, 1, 0, 0), 0),
        make_jerusalem_test_params(dt(2019, 1, 1, 0, 0), 0),
    ]
    omer_test_ids = [
        "nyc_first_day_of_omer",
        "israel_first_day_of_omer",
        "nyc_first_day_of_omer_after_tzeit",
        "israel_first_day_of_omer_after_tzeit",
        "nyc_lag_baomer",
        "israel_lag_baomer",
        "nyc_last_day_of_omer",
        "israel_last_day_of_omer",
        "nyc_shavuot_no_omer",
        "israel_shavuot_no_omer",
        "nyc_jan_1st_no_omer",
        "israel_jan_1st_no_omer",
    ]

    @pytest.mark.parametrize(
        [
            "now",
            "candle_lighting",
            "havdalah",
            "diaspora",
            "tzname",
            "latitude",
            "longitude",
            "result",
        ],
        omer_params,
        ids=omer_test_ids,
    )
    async def test_omer_sensor(
        self,
        hass,
        now,
        candle_lighting,
        havdalah,
        diaspora,
        tzname,
        latitude,
        longitude,
        result,
    ):
        """Test Omer Count sensor output."""
        time_zone = get_time_zone(tzname)
        test_time = time_zone.localize(now)

        hass.config.set_time_zone(tzname)
        hass.config.latitude = latitude
        hass.config.longitude = longitude

        assert await async_setup_component(
            hass,
            jewish_calendar.DOMAIN,
            {
                "jewish_calendar": {
                    "name": "test",
                    "language": "english",
                    "diaspora": diaspora,
                    "candle_lighting_minutes_before_sunset": candle_lighting,
                    "havdalah_minutes_after_sunset": havdalah,
                }
            },
        )
        await hass.async_block_till_done()

        with alter_time(test_time):
            await hass.helpers.entity_component.async_update_entity(
                "sensor.test_omer_count"
            )

        assert hass.states.get("sensor.test_omer_count").state == result
