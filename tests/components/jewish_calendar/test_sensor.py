"""The tests for the Jewish calendar sensors."""
from datetime import datetime as dt, timedelta

import pytest

from homeassistant.components import jewish_calendar
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import (
    HDATE_DEFAULT_ALTITUDE,
    alter_time,
    make_jerusalem_test_params,
    make_nyc_test_params,
)

from tests.common import async_fire_time_changed


async def test_jewish_calendar_min_config(hass):
    """Test minimum jewish calendar configuration."""
    assert await async_setup_component(
        hass, jewish_calendar.DOMAIN, {"jewish_calendar": {}}
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.jewish_calendar_date") is not None


async def test_jewish_calendar_hebrew(hass):
    """Test jewish calendar sensor with language set to hebrew."""
    assert await async_setup_component(
        hass, jewish_calendar.DOMAIN, {"jewish_calendar": {"language": "hebrew"}}
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.jewish_calendar_date") is not None


TEST_PARAMS = [
    (dt(2018, 9, 3), "UTC", 31.778, 35.235, "english", "date", False, "23 Elul 5778"),
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
    (dt(2018, 9, 10), "UTC", 31.778, 35.235, "hebrew", "holiday", False, "א' ראש השנה"),
    (
        dt(2018, 9, 10),
        "UTC",
        31.778,
        35.235,
        "english",
        "holiday",
        False,
        "Rosh Hashana I",
    ),
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
        dt(2018, 9, 8, 19, 45),
    ),
    (
        dt(2018, 9, 8),
        "Asia/Jerusalem",
        31.778,
        35.235,
        "hebrew",
        "t_set_hakochavim",
        False,
        dt(2018, 9, 8, 19, 19),
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

TEST_IDS = [
    "date_output",
    "date_output_hebrew",
    "holiday",
    "holiday_english",
    "torah_reading",
    "first_stars_ny",
    "first_stars_jerusalem",
    "torah_reading_weekday",
    "date_before_sunset",
    "date_after_sunset",
]


@pytest.mark.parametrize(
    [
        "now",
        "tzname",
        "latitude",
        "longitude",
        "language",
        "sensor",
        "diaspora",
        "result",
    ],
    TEST_PARAMS,
    ids=TEST_IDS,
)
async def test_jewish_calendar_sensor(
    hass,
    legacy_patchable_time,
    now,
    tzname,
    latitude,
    longitude,
    language,
    sensor,
    diaspora,
    result,
):
    """Test Jewish calendar sensor output."""
    time_zone = dt_util.get_time_zone(tzname)
    test_time = time_zone.localize(now)

    hass.config.time_zone = time_zone
    hass.config.latitude = latitude
    hass.config.longitude = longitude

    with alter_time(test_time):
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

        future = dt_util.utcnow() + timedelta(seconds=30)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    result = (
        dt_util.as_utc(time_zone.localize(result)) if isinstance(result, dt) else result
    )

    sensor_object = hass.states.get(f"sensor.test_{sensor}")
    assert sensor_object.state == str(result)

    if sensor == "holiday":
        assert sensor_object.attributes.get("id") == "rosh_hashana_i"
        assert sensor_object.attributes.get("type") == "YOM_TOV"
        assert sensor_object.attributes.get("type_id") == 1


SHABBAT_PARAMS = [
    make_nyc_test_params(
        dt(2018, 9, 1, 16, 0),
        {
            "english_upcoming_candle_lighting": dt(2018, 8, 31, 19, 12),
            "english_upcoming_havdalah": dt(2018, 9, 1, 20, 10),
            "english_upcoming_shabbat_candle_lighting": dt(2018, 8, 31, 19, 12),
            "english_upcoming_shabbat_havdalah": dt(2018, 9, 1, 20, 10),
            "english_parshat_hashavua": "Ki Tavo",
            "hebrew_parshat_hashavua": "כי תבוא",
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 1, 16, 0),
        {
            "english_upcoming_candle_lighting": dt(2018, 8, 31, 19, 12),
            "english_upcoming_havdalah": dt(2018, 9, 1, 20, 18),
            "english_upcoming_shabbat_candle_lighting": dt(2018, 8, 31, 19, 12),
            "english_upcoming_shabbat_havdalah": dt(2018, 9, 1, 20, 18),
            "english_parshat_hashavua": "Ki Tavo",
            "hebrew_parshat_hashavua": "כי תבוא",
        },
        havdalah_offset=50,
    ),
    make_nyc_test_params(
        dt(2018, 9, 1, 20, 0),
        {
            "english_upcoming_shabbat_candle_lighting": dt(2018, 8, 31, 19, 12),
            "english_upcoming_shabbat_havdalah": dt(2018, 9, 1, 20, 10),
            "english_upcoming_candle_lighting": dt(2018, 8, 31, 19, 12),
            "english_upcoming_havdalah": dt(2018, 9, 1, 20, 10),
            "english_parshat_hashavua": "Ki Tavo",
            "hebrew_parshat_hashavua": "כי תבוא",
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 1, 20, 21),
        {
            "english_upcoming_candle_lighting": dt(2018, 9, 7, 19),
            "english_upcoming_havdalah": dt(2018, 9, 8, 19, 58),
            "english_upcoming_shabbat_candle_lighting": dt(2018, 9, 7, 19),
            "english_upcoming_shabbat_havdalah": dt(2018, 9, 8, 19, 58),
            "english_parshat_hashavua": "Nitzavim",
            "hebrew_parshat_hashavua": "נצבים",
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 7, 13, 1),
        {
            "english_upcoming_candle_lighting": dt(2018, 9, 7, 19),
            "english_upcoming_havdalah": dt(2018, 9, 8, 19, 58),
            "english_upcoming_shabbat_candle_lighting": dt(2018, 9, 7, 19),
            "english_upcoming_shabbat_havdalah": dt(2018, 9, 8, 19, 58),
            "english_parshat_hashavua": "Nitzavim",
            "hebrew_parshat_hashavua": "נצבים",
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 8, 21, 25),
        {
            "english_upcoming_candle_lighting": dt(2018, 9, 9, 18, 57),
            "english_upcoming_havdalah": dt(2018, 9, 11, 19, 53),
            "english_upcoming_shabbat_candle_lighting": dt(2018, 9, 14, 18, 48),
            "english_upcoming_shabbat_havdalah": dt(2018, 9, 15, 19, 46),
            "english_parshat_hashavua": "Vayeilech",
            "hebrew_parshat_hashavua": "וילך",
            "english_holiday": "Erev Rosh Hashana",
            "hebrew_holiday": "ערב ראש השנה",
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 9, 21, 25),
        {
            "english_upcoming_candle_lighting": dt(2018, 9, 9, 18, 57),
            "english_upcoming_havdalah": dt(2018, 9, 11, 19, 53),
            "english_upcoming_shabbat_candle_lighting": dt(2018, 9, 14, 18, 48),
            "english_upcoming_shabbat_havdalah": dt(2018, 9, 15, 19, 46),
            "english_parshat_hashavua": "Vayeilech",
            "hebrew_parshat_hashavua": "וילך",
            "english_holiday": "Rosh Hashana I",
            "hebrew_holiday": "א' ראש השנה",
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 10, 21, 25),
        {
            "english_upcoming_candle_lighting": dt(2018, 9, 9, 18, 57),
            "english_upcoming_havdalah": dt(2018, 9, 11, 19, 53),
            "english_upcoming_shabbat_candle_lighting": dt(2018, 9, 14, 18, 48),
            "english_upcoming_shabbat_havdalah": dt(2018, 9, 15, 19, 46),
            "english_parshat_hashavua": "Vayeilech",
            "hebrew_parshat_hashavua": "וילך",
            "english_holiday": "Rosh Hashana II",
            "hebrew_holiday": "ב' ראש השנה",
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 28, 21, 25),
        {
            "english_upcoming_candle_lighting": dt(2018, 9, 28, 18, 25),
            "english_upcoming_havdalah": dt(2018, 9, 29, 19, 22),
            "english_upcoming_shabbat_candle_lighting": dt(2018, 9, 28, 18, 25),
            "english_upcoming_shabbat_havdalah": dt(2018, 9, 29, 19, 22),
            "english_parshat_hashavua": "none",
            "hebrew_parshat_hashavua": "none",
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 29, 21, 25),
        {
            "english_upcoming_candle_lighting": dt(2018, 9, 30, 18, 22),
            "english_upcoming_havdalah": dt(2018, 10, 2, 19, 17),
            "english_upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 18, 13),
            "english_upcoming_shabbat_havdalah": dt(2018, 10, 6, 19, 11),
            "english_parshat_hashavua": "Bereshit",
            "hebrew_parshat_hashavua": "בראשית",
            "english_holiday": "Hoshana Raba",
            "hebrew_holiday": "הושענא רבה",
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 30, 21, 25),
        {
            "english_upcoming_candle_lighting": dt(2018, 9, 30, 18, 22),
            "english_upcoming_havdalah": dt(2018, 10, 2, 19, 17),
            "english_upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 18, 13),
            "english_upcoming_shabbat_havdalah": dt(2018, 10, 6, 19, 11),
            "english_parshat_hashavua": "Bereshit",
            "hebrew_parshat_hashavua": "בראשית",
            "english_holiday": "Shmini Atzeret",
            "hebrew_holiday": "שמיני עצרת",
        },
    ),
    make_nyc_test_params(
        dt(2018, 10, 1, 21, 25),
        {
            "english_upcoming_candle_lighting": dt(2018, 9, 30, 18, 22),
            "english_upcoming_havdalah": dt(2018, 10, 2, 19, 17),
            "english_upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 18, 13),
            "english_upcoming_shabbat_havdalah": dt(2018, 10, 6, 19, 11),
            "english_parshat_hashavua": "Bereshit",
            "hebrew_parshat_hashavua": "בראשית",
            "english_holiday": "Simchat Torah",
            "hebrew_holiday": "שמחת תורה",
        },
    ),
    make_jerusalem_test_params(
        dt(2018, 9, 29, 21, 25),
        {
            "english_upcoming_candle_lighting": dt(2018, 9, 30, 18, 7),
            "english_upcoming_havdalah": dt(2018, 10, 1, 19, 1),
            "english_upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 18, 1),
            "english_upcoming_shabbat_havdalah": dt(2018, 10, 6, 18, 54),
            "english_parshat_hashavua": "Bereshit",
            "hebrew_parshat_hashavua": "בראשית",
            "english_holiday": "Hoshana Raba",
            "hebrew_holiday": "הושענא רבה",
        },
    ),
    make_jerusalem_test_params(
        dt(2018, 9, 30, 21, 25),
        {
            "english_upcoming_candle_lighting": dt(2018, 9, 30, 18, 7),
            "english_upcoming_havdalah": dt(2018, 10, 1, 19, 1),
            "english_upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 18, 1),
            "english_upcoming_shabbat_havdalah": dt(2018, 10, 6, 18, 54),
            "english_parshat_hashavua": "Bereshit",
            "hebrew_parshat_hashavua": "בראשית",
            "english_holiday": "Shmini Atzeret",
            "hebrew_holiday": "שמיני עצרת",
        },
    ),
    make_jerusalem_test_params(
        dt(2018, 10, 1, 21, 25),
        {
            "english_upcoming_candle_lighting": dt(2018, 10, 5, 18, 1),
            "english_upcoming_havdalah": dt(2018, 10, 6, 18, 54),
            "english_upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 18, 1),
            "english_upcoming_shabbat_havdalah": dt(2018, 10, 6, 18, 54),
            "english_parshat_hashavua": "Bereshit",
            "hebrew_parshat_hashavua": "בראשית",
        },
    ),
    make_nyc_test_params(
        dt(2016, 6, 11, 8, 25),
        {
            "english_upcoming_candle_lighting": dt(2016, 6, 10, 20, 9),
            "english_upcoming_havdalah": dt(2016, 6, 13, 21, 19),
            "english_upcoming_shabbat_candle_lighting": dt(2016, 6, 10, 20, 9),
            "english_upcoming_shabbat_havdalah": "unknown",
            "english_parshat_hashavua": "Bamidbar",
            "hebrew_parshat_hashavua": "במדבר",
            "english_holiday": "Erev Shavuot",
            "hebrew_holiday": "ערב שבועות",
        },
    ),
    make_nyc_test_params(
        dt(2016, 6, 12, 8, 25),
        {
            "english_upcoming_candle_lighting": dt(2016, 6, 10, 20, 9),
            "english_upcoming_havdalah": dt(2016, 6, 13, 21, 19),
            "english_upcoming_shabbat_candle_lighting": dt(2016, 6, 17, 20, 12),
            "english_upcoming_shabbat_havdalah": dt(2016, 6, 18, 21, 21),
            "english_parshat_hashavua": "Nasso",
            "hebrew_parshat_hashavua": "נשא",
            "english_holiday": "Shavuot",
            "hebrew_holiday": "שבועות",
        },
    ),
    make_jerusalem_test_params(
        dt(2017, 9, 21, 8, 25),
        {
            "english_upcoming_candle_lighting": dt(2017, 9, 20, 18, 20),
            "english_upcoming_havdalah": dt(2017, 9, 23, 19, 11),
            "english_upcoming_shabbat_candle_lighting": dt(2017, 9, 22, 19, 12),
            "english_upcoming_shabbat_havdalah": dt(2017, 9, 23, 19, 11),
            "english_parshat_hashavua": "Ha'Azinu",
            "hebrew_parshat_hashavua": "האזינו",
            "english_holiday": "Rosh Hashana I",
            "hebrew_holiday": "א' ראש השנה",
        },
    ),
    make_jerusalem_test_params(
        dt(2017, 9, 22, 8, 25),
        {
            "english_upcoming_candle_lighting": dt(2017, 9, 20, 18, 20),
            "english_upcoming_havdalah": dt(2017, 9, 23, 19, 11),
            "english_upcoming_shabbat_candle_lighting": dt(2017, 9, 22, 19, 12),
            "english_upcoming_shabbat_havdalah": dt(2017, 9, 23, 19, 11),
            "english_parshat_hashavua": "Ha'Azinu",
            "hebrew_parshat_hashavua": "האזינו",
            "english_holiday": "Rosh Hashana II",
            "hebrew_holiday": "ב' ראש השנה",
        },
    ),
    make_jerusalem_test_params(
        dt(2017, 9, 23, 8, 25),
        {
            "english_upcoming_candle_lighting": dt(2017, 9, 20, 18, 20),
            "english_upcoming_havdalah": dt(2017, 9, 23, 19, 11),
            "english_upcoming_shabbat_candle_lighting": dt(2017, 9, 22, 19, 12),
            "english_upcoming_shabbat_havdalah": dt(2017, 9, 23, 19, 11),
            "english_parshat_hashavua": "Ha'Azinu",
            "hebrew_parshat_hashavua": "האזינו",
            "english_holiday": "",
            "hebrew_holiday": "",
        },
    ),
]

SHABBAT_TEST_IDS = [
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


@pytest.mark.parametrize("language", ["english", "hebrew"])
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
    SHABBAT_PARAMS,
    ids=SHABBAT_TEST_IDS,
)
async def test_shabbat_times_sensor(
    hass,
    legacy_patchable_time,
    language,
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
    time_zone = dt_util.get_time_zone(tzname)
    test_time = time_zone.localize(now)

    hass.config.time_zone = time_zone
    hass.config.latitude = latitude
    hass.config.longitude = longitude

    registry = er.async_get(hass)

    with alter_time(test_time):
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

        future = dt_util.utcnow() + timedelta(seconds=30)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    for sensor_type, result_value in result.items():
        if not sensor_type.startswith(language):
            print(f"Not checking {sensor_type} for {language}")
            continue

        sensor_type = sensor_type.replace(f"{language}_", "")

        result_value = (
            dt_util.as_utc(result_value)
            if isinstance(result_value, dt)
            else result_value
        )

        assert hass.states.get(f"sensor.test_{sensor_type}").state == str(
            result_value
        ), f"Value for {sensor_type}"

        entity = registry.async_get(f"sensor.test_{sensor_type}")
        target_sensor_type = sensor_type.replace("parshat_hashavua", "weekly_portion")
        target_uid = "_".join(
            map(
                str,
                [
                    latitude,
                    longitude,
                    time_zone,
                    HDATE_DEFAULT_ALTITUDE,
                    diaspora,
                    language,
                    candle_lighting,
                    havdalah,
                    target_sensor_type,
                ],
            )
        )
        assert entity.unique_id == target_uid


OMER_PARAMS = [
    (dt(2019, 4, 21, 0), "1"),
    (dt(2019, 4, 21, 23), "2"),
    (dt(2019, 5, 23, 0), "33"),
    (dt(2019, 6, 8, 0), "49"),
    (dt(2019, 6, 9, 0), "0"),
    (dt(2019, 1, 1, 0), "0"),
]
OMER_TEST_IDS = [
    "first_day_of_omer",
    "first_day_of_omer_after_tzeit",
    "lag_baomer",
    "last_day_of_omer",
    "shavuot_no_omer",
    "jan_1st_no_omer",
]


@pytest.mark.parametrize(["test_time", "result"], OMER_PARAMS, ids=OMER_TEST_IDS)
async def test_omer_sensor(hass, legacy_patchable_time, test_time, result):
    """Test Omer Count sensor output."""
    test_time = hass.config.time_zone.localize(test_time)

    with alter_time(test_time):
        assert await async_setup_component(
            hass, jewish_calendar.DOMAIN, {"jewish_calendar": {"name": "test"}}
        )
        await hass.async_block_till_done()

        future = dt_util.utcnow() + timedelta(seconds=30)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.test_day_of_the_omer").state == result


DAFYOMI_PARAMS = [
    (dt(2014, 4, 28, 0), "Beitzah 29"),
    (dt(2020, 1, 4, 0), "Niddah 73"),
    (dt(2020, 1, 5, 0), "Berachos 2"),
    (dt(2020, 3, 7, 0), "Berachos 64"),
    (dt(2020, 3, 8, 0), "Shabbos 2"),
]
DAFYOMI_TEST_IDS = [
    "randomly_picked_date",
    "end_of_cycle13",
    "start_of_cycle14",
    "cycle14_end_of_berachos",
    "cycle14_start_of_shabbos",
]


@pytest.mark.parametrize(["test_time", "result"], DAFYOMI_PARAMS, ids=DAFYOMI_TEST_IDS)
async def test_dafyomi_sensor(hass, legacy_patchable_time, test_time, result):
    """Test Daf Yomi sensor output."""
    test_time = hass.config.time_zone.localize(test_time)

    with alter_time(test_time):
        assert await async_setup_component(
            hass, jewish_calendar.DOMAIN, {"jewish_calendar": {"name": "test"}}
        )
        await hass.async_block_till_done()

        future = dt_util.utcnow() + timedelta(seconds=30)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.test_daf_yomi").state == result
