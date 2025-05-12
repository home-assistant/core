"""The tests for the Jewish calendar sensors."""

from datetime import datetime as dt
from typing import Any

from hdate.holidays import HolidayDatabase
from hdate.parasha import Parasha
import pytest

from homeassistant.components.jewish_calendar.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.mark.parametrize("language", ["en", "he"])
async def test_min_config(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test minimum jewish calendar configuration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.jewish_calendar_date") is not None


TEST_PARAMS = [
    pytest.param(
        "Jerusalem",
        dt(2018, 9, 3),
        {"state": "23 Elul 5778"},
        "en",
        "date",
        id="date_output",
    ),
    pytest.param(
        "Jerusalem",
        dt(2018, 9, 3),
        {"state": 'כ"ג אלול ה\' תשע"ח'},
        "he",
        "date",
        id="date_output_hebrew",
    ),
    pytest.param(
        "Jerusalem",
        dt(2018, 9, 10),
        {"state": "א' ראש השנה"},
        "he",
        "holiday",
        id="holiday",
    ),
    pytest.param(
        "Jerusalem",
        dt(2018, 9, 10),
        {
            "state": "Rosh Hashana I",
            "attr": {
                "device_class": "enum",
                "friendly_name": "Jewish Calendar Holiday",
                "icon": "mdi:calendar-star",
                "id": "rosh_hashana_i",
                "type": "YOM_TOV",
                "options": lambda: HolidayDatabase(False).get_all_names(),
            },
        },
        "en",
        "holiday",
        id="holiday_english",
    ),
    pytest.param(
        "Jerusalem",
        dt(2024, 12, 31),
        {
            "state": "Chanukah, Rosh Chodesh",
            "attr": {
                "device_class": "enum",
                "friendly_name": "Jewish Calendar Holiday",
                "icon": "mdi:calendar-star",
                "id": "chanukah, rosh_chodesh",
                "type": "MELACHA_PERMITTED_HOLIDAY, ROSH_CHODESH",
                "options": lambda: HolidayDatabase(False).get_all_names(),
            },
        },
        "en",
        "holiday",
        id="holiday_multiple",
    ),
    pytest.param(
        "Jerusalem",
        dt(2018, 9, 8),
        {
            "state": "נצבים",
            "attr": {
                "device_class": "enum",
                "friendly_name": "Jewish Calendar Weekly Torah portion",
                "icon": "mdi:book-open-variant",
                "options": list(Parasha),
            },
        },
        "he",
        "weekly_torah_portion",
        id="torah_portion",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 8),
        {"state": dt(2018, 9, 8, 19, 47)},
        "he",
        "nightfall_t_set_hakochavim",
        id="first_stars_ny",
    ),
    pytest.param(
        "Jerusalem",
        dt(2018, 9, 8),
        {"state": dt(2018, 9, 8, 19, 21)},
        "he",
        "nightfall_t_set_hakochavim",
        id="first_stars_jerusalem",
    ),
    pytest.param(
        "Jerusalem",
        dt(2018, 10, 14),
        {"state": "לך לך"},
        "he",
        "weekly_torah_portion",
        id="torah_portion_weekday",
    ),
    pytest.param(
        "Jerusalem",
        dt(2018, 10, 14, 17, 0, 0),
        {"state": "ה' מרחשוון ה' תשע\"ט"},
        "he",
        "date",
        id="date_before_sunset",
    ),
    pytest.param(
        "Jerusalem",
        dt(2018, 10, 14, 19, 0, 0),
        {
            "state": "ו' מרחשוון ה' תשע\"ט",
            "attr": {
                "hebrew_year": "5779",
                "hebrew_month_name": "מרחשוון",
                "hebrew_day": "6",
                "icon": "mdi:star-david",
                "friendly_name": "Jewish Calendar Date",
            },
        },
        "he",
        "date",
        id="date_after_sunset",
    ),
]


@pytest.mark.parametrize(
    ("location_data", "test_time", "results", "language", "sensor"),
    TEST_PARAMS,
    indirect=["location_data", "test_time", "results"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_at_time")
async def test_jewish_calendar_sensor(
    hass: HomeAssistant, results: dict[str, Any], sensor: str
) -> None:
    """Test Jewish calendar sensor output."""
    result = results["state"]
    if isinstance(result, dt):
        result = dt_util.as_utc(result).isoformat()

    sensor_object = hass.states.get(f"sensor.jewish_calendar_{sensor}")
    assert sensor_object.state == result

    if attrs := results.get("attr"):
        assert sensor_object.attributes == attrs


SHABBAT_PARAMS = [
    pytest.param(
        "New York",
        dt(2018, 9, 1, 16, 0),
        {
            "en_upcoming_candle_lighting": dt(2018, 8, 31, 19, 12),
            "en_upcoming_havdalah": dt(2018, 9, 1, 20, 10),
            "en_upcoming_shabbat_candle_lighting": dt(2018, 8, 31, 19, 12),
            "en_upcoming_shabbat_havdalah": dt(2018, 9, 1, 20, 10),
            "en_weekly_torah_portion": "Ki Tavo",
            "he_weekly_torah_portion": "כי תבוא",
        },
        None,
        id="currently_first_shabbat",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 1, 16, 0),
        {
            "en_upcoming_candle_lighting": dt(2018, 8, 31, 19, 12),
            "en_upcoming_havdalah": dt(2018, 9, 1, 20, 18),
            "en_upcoming_shabbat_candle_lighting": dt(2018, 8, 31, 19, 12),
            "en_upcoming_shabbat_havdalah": dt(2018, 9, 1, 20, 18),
            "en_weekly_torah_portion": "Ki Tavo",
            "he_weekly_torah_portion": "כי תבוא",
        },
        50,  # Havdalah offset
        id="currently_first_shabbat_with_havdalah_offset",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 1, 20, 0),
        {
            "en_upcoming_shabbat_candle_lighting": dt(2018, 8, 31, 19, 12),
            "en_upcoming_shabbat_havdalah": dt(2018, 9, 1, 20, 10),
            "en_upcoming_candle_lighting": dt(2018, 8, 31, 19, 12),
            "en_upcoming_havdalah": dt(2018, 9, 1, 20, 10),
            "en_weekly_torah_portion": "Ki Tavo",
            "he_weekly_torah_portion": "כי תבוא",
        },
        None,
        id="currently_first_shabbat_bein_hashmashot_lagging_date",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 1, 20, 21),
        {
            "en_upcoming_candle_lighting": dt(2018, 9, 7, 19),
            "en_upcoming_havdalah": dt(2018, 9, 8, 19, 58),
            "en_upcoming_shabbat_candle_lighting": dt(2018, 9, 7, 19),
            "en_upcoming_shabbat_havdalah": dt(2018, 9, 8, 19, 58),
            "en_weekly_torah_portion": "Nitzavim",
            "he_weekly_torah_portion": "נצבים",
        },
        None,
        id="after_first_shabbat",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 7, 13, 1),
        {
            "en_upcoming_candle_lighting": dt(2018, 9, 7, 19),
            "en_upcoming_havdalah": dt(2018, 9, 8, 19, 58),
            "en_upcoming_shabbat_candle_lighting": dt(2018, 9, 7, 19),
            "en_upcoming_shabbat_havdalah": dt(2018, 9, 8, 19, 58),
            "en_weekly_torah_portion": "Nitzavim",
            "he_weekly_torah_portion": "נצבים",
        },
        None,
        id="friday_upcoming_shabbat",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 8, 21, 25),
        {
            "en_upcoming_candle_lighting": dt(2018, 9, 9, 18, 57),
            "en_upcoming_havdalah": dt(2018, 9, 11, 19, 53),
            "en_upcoming_shabbat_candle_lighting": dt(2018, 9, 14, 18, 48),
            "en_upcoming_shabbat_havdalah": dt(2018, 9, 15, 19, 46),
            "en_weekly_torah_portion": "Vayeilech",
            "he_weekly_torah_portion": "וילך",
            "en_holiday": "Erev Rosh Hashana",
            "he_holiday": "ערב ראש השנה",
        },
        None,
        id="upcoming_rosh_hashana",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 9, 21, 25),
        {
            "en_upcoming_candle_lighting": dt(2018, 9, 9, 18, 57),
            "en_upcoming_havdalah": dt(2018, 9, 11, 19, 53),
            "en_upcoming_shabbat_candle_lighting": dt(2018, 9, 14, 18, 48),
            "en_upcoming_shabbat_havdalah": dt(2018, 9, 15, 19, 46),
            "en_weekly_torah_portion": "Vayeilech",
            "he_weekly_torah_portion": "וילך",
            "en_holiday": "Rosh Hashana I",
            "he_holiday": "א' ראש השנה",
        },
        None,
        id="currently_rosh_hashana",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 10, 21, 25),
        {
            "en_upcoming_candle_lighting": dt(2018, 9, 9, 18, 57),
            "en_upcoming_havdalah": dt(2018, 9, 11, 19, 53),
            "en_upcoming_shabbat_candle_lighting": dt(2018, 9, 14, 18, 48),
            "en_upcoming_shabbat_havdalah": dt(2018, 9, 15, 19, 46),
            "en_weekly_torah_portion": "Vayeilech",
            "he_weekly_torah_portion": "וילך",
            "en_holiday": "Rosh Hashana II",
            "he_holiday": "ב' ראש השנה",
        },
        None,
        id="second_day_rosh_hashana",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 28, 21, 25),
        {
            "en_upcoming_candle_lighting": dt(2018, 9, 28, 18, 25),
            "en_upcoming_havdalah": dt(2018, 9, 29, 19, 22),
            "en_upcoming_shabbat_candle_lighting": dt(2018, 9, 28, 18, 25),
            "en_upcoming_shabbat_havdalah": dt(2018, 9, 29, 19, 22),
            "en_weekly_torah_portion": "none",
            "he_weekly_torah_portion": "none",
        },
        None,
        id="currently_shabbat_chol_hamoed",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 29, 21, 25),
        {
            "en_upcoming_candle_lighting": dt(2018, 9, 30, 18, 22),
            "en_upcoming_havdalah": dt(2018, 10, 2, 19, 17),
            "en_upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 18, 13),
            "en_upcoming_shabbat_havdalah": dt(2018, 10, 6, 19, 11),
            "en_weekly_torah_portion": "Bereshit",
            "he_weekly_torah_portion": "בראשית",
            "en_holiday": "Hoshana Raba",
            "he_holiday": "הושענא רבה",
        },
        None,
        id="upcoming_two_day_yomtov_in_diaspora",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 30, 21, 25),
        {
            "en_upcoming_candle_lighting": dt(2018, 9, 30, 18, 22),
            "en_upcoming_havdalah": dt(2018, 10, 2, 19, 17),
            "en_upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 18, 13),
            "en_upcoming_shabbat_havdalah": dt(2018, 10, 6, 19, 11),
            "en_weekly_torah_portion": "Bereshit",
            "he_weekly_torah_portion": "בראשית",
            "en_holiday": "Shmini Atzeret",
            "he_holiday": "שמיני עצרת",
        },
        None,
        id="currently_first_day_of_two_day_yomtov_in_diaspora",
    ),
    pytest.param(
        "New York",
        dt(2018, 10, 1, 21, 25),
        {
            "en_upcoming_candle_lighting": dt(2018, 9, 30, 18, 22),
            "en_upcoming_havdalah": dt(2018, 10, 2, 19, 17),
            "en_upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 18, 13),
            "en_upcoming_shabbat_havdalah": dt(2018, 10, 6, 19, 11),
            "en_weekly_torah_portion": "Bereshit",
            "he_weekly_torah_portion": "בראשית",
            "en_holiday": "Simchat Torah",
            "he_holiday": "שמחת תורה",
        },
        None,
        id="currently_second_day_of_two_day_yomtov_in_diaspora",
    ),
    pytest.param(
        "Jerusalem",
        dt(2018, 9, 29, 21, 25),
        {
            "en_upcoming_candle_lighting": dt(2018, 9, 30, 17, 46),
            "en_upcoming_havdalah": dt(2018, 10, 1, 19, 1),
            "en_upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 17, 39),
            "en_upcoming_shabbat_havdalah": dt(2018, 10, 6, 18, 54),
            "en_weekly_torah_portion": "Bereshit",
            "he_weekly_torah_portion": "בראשית",
            "en_holiday": "Hoshana Raba",
            "he_holiday": "הושענא רבה",
        },
        None,
        id="upcoming_one_day_yom_tov_in_israel",
    ),
    pytest.param(
        "Jerusalem",
        dt(2018, 9, 30, 21, 25),
        {
            "en_upcoming_candle_lighting": dt(2018, 9, 30, 17, 46),
            "en_upcoming_havdalah": dt(2018, 10, 1, 19, 1),
            "en_upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 17, 39),
            "en_upcoming_shabbat_havdalah": dt(2018, 10, 6, 18, 54),
            "en_weekly_torah_portion": "Bereshit",
            "he_weekly_torah_portion": "בראשית",
            "en_holiday": "Shmini Atzeret, Simchat Torah",
            "he_holiday": "שמיני עצרת, שמחת תורה",
        },
        None,
        id="currently_one_day_yom_tov_in_israel",
    ),
    pytest.param(
        "Jerusalem",
        dt(2018, 10, 1, 21, 25),
        {
            "en_upcoming_candle_lighting": dt(2018, 10, 5, 17, 39),
            "en_upcoming_havdalah": dt(2018, 10, 6, 18, 54),
            "en_upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 17, 39),
            "en_upcoming_shabbat_havdalah": dt(2018, 10, 6, 18, 54),
            "en_weekly_torah_portion": "Bereshit",
            "he_weekly_torah_portion": "בראשית",
        },
        None,
        id="after_one_day_yom_tov_in_israel",
    ),
    pytest.param(
        "New York",
        dt(2016, 6, 11, 8, 25),
        {
            "en_upcoming_candle_lighting": dt(2016, 6, 10, 20, 9),
            "en_upcoming_havdalah": dt(2016, 6, 13, 21, 19),
            "en_upcoming_shabbat_candle_lighting": dt(2016, 6, 10, 20, 9),
            "en_upcoming_shabbat_havdalah": "unknown",
            "en_weekly_torah_portion": "Bamidbar",
            "he_weekly_torah_portion": "במדבר",
            "en_holiday": "Erev Shavuot",
            "he_holiday": "ערב שבועות",
        },
        None,
        id="currently_first_day_of_three_day_type1_yomtov_in_diaspora",  # Type 1 = Sat/Sun/Mon
    ),
    pytest.param(
        "New York",
        dt(2016, 6, 12, 8, 25),
        {
            "en_upcoming_candle_lighting": dt(2016, 6, 10, 20, 9),
            "en_upcoming_havdalah": dt(2016, 6, 13, 21, 19),
            "en_upcoming_shabbat_candle_lighting": dt(2016, 6, 17, 20, 12),
            "en_upcoming_shabbat_havdalah": dt(2016, 6, 18, 21, 21),
            "en_weekly_torah_portion": "Nasso",
            "he_weekly_torah_portion": "נשא",
            "en_holiday": "Shavuot",
            "he_holiday": "שבועות",
        },
        None,
        id="currently_second_day_of_three_day_type1_yomtov_in_diaspora",  # Type 1 = Sat/Sun/Mon
    ),
    pytest.param(
        "Jerusalem",
        dt(2017, 9, 21, 8, 25),
        {
            "en_upcoming_candle_lighting": dt(2017, 9, 20, 17, 58),
            "en_upcoming_havdalah": dt(2017, 9, 23, 19, 11),
            "en_upcoming_shabbat_candle_lighting": dt(2017, 9, 22, 17, 56),
            "en_upcoming_shabbat_havdalah": dt(2017, 9, 23, 19, 11),
            "en_weekly_torah_portion": "Ha'Azinu",
            "he_weekly_torah_portion": "האזינו",
            "en_holiday": "Rosh Hashana I",
            "he_holiday": "א' ראש השנה",
        },
        None,
        id="currently_first_day_of_three_day_type2_yomtov_in_israel",  # Type 2 = Thurs/Fri/Sat
    ),
    pytest.param(
        "Jerusalem",
        dt(2017, 9, 22, 8, 25),
        {
            "en_upcoming_candle_lighting": dt(2017, 9, 20, 17, 58),
            "en_upcoming_havdalah": dt(2017, 9, 23, 19, 11),
            "en_upcoming_shabbat_candle_lighting": dt(2017, 9, 22, 17, 56),
            "en_upcoming_shabbat_havdalah": dt(2017, 9, 23, 19, 11),
            "en_weekly_torah_portion": "Ha'Azinu",
            "he_weekly_torah_portion": "האזינו",
            "en_holiday": "Rosh Hashana II",
            "he_holiday": "ב' ראש השנה",
        },
        None,
        id="currently_second_day_of_three_day_type2_yomtov_in_israel",  # Type 2 = Thurs/Fri/Sat
    ),
    pytest.param(
        "Jerusalem",
        dt(2017, 9, 23, 8, 25),
        {
            "en_upcoming_candle_lighting": dt(2017, 9, 20, 17, 58),
            "en_upcoming_havdalah": dt(2017, 9, 23, 19, 11),
            "en_upcoming_shabbat_candle_lighting": dt(2017, 9, 22, 17, 56),
            "en_upcoming_shabbat_havdalah": dt(2017, 9, 23, 19, 11),
            "en_weekly_torah_portion": "Ha'Azinu",
            "he_weekly_torah_portion": "האזינו",
            "en_holiday": "",
            "he_holiday": "",
        },
        None,
        id="currently_third_day_of_three_day_type2_yomtov_in_israel",  # Type 2 = Thurs/Fri/Sat
    ),
]


@pytest.mark.parametrize("language", ["en", "he"])
@pytest.mark.parametrize(
    ("location_data", "test_time", "results", "havdalah_offset"),
    SHABBAT_PARAMS,
    indirect=("location_data", "test_time", "results"),
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_at_time")
async def test_shabbat_times_sensor(
    hass: HomeAssistant, results: dict[str, Any], language: str
) -> None:
    """Test sensor output for upcoming shabbat/yomtov times."""
    for sensor_type, result_value in results.items():
        if not sensor_type.startswith(language):
            continue

        sensor_type = sensor_type.replace(f"{language}_", "")

        if isinstance(result_value, dt):
            result_value = dt_util.as_utc(result_value).isoformat()

        assert hass.states.get(f"sensor.jewish_calendar_{sensor_type}").state == str(
            result_value
        ), f"Value for {sensor_type}"


@pytest.mark.parametrize(
    ("test_time", "results"),
    [
        pytest.param(dt(2019, 4, 21, 0), "1", id="first_day_of_omer"),
        pytest.param(dt(2019, 4, 21, 23), "2", id="first_day_of_omer_after_tzeit"),
        pytest.param(dt(2019, 5, 23, 0), "33", id="lag_baomer"),
        pytest.param(dt(2019, 6, 8, 0), "49", id="last_day_of_omer"),
        pytest.param(dt(2019, 6, 9, 0), "0", id="shavuot_no_omer"),
        pytest.param(dt(2019, 1, 1, 0), "0", id="jan_1st_no_omer"),
    ],
    indirect=True,
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_at_time")
async def test_omer_sensor(hass: HomeAssistant, results: str) -> None:
    """Test Omer Count sensor output."""
    assert hass.states.get("sensor.jewish_calendar_day_of_the_omer").state == results


@pytest.mark.parametrize(
    ("test_time", "results"),
    [
        pytest.param(dt(2014, 4, 28, 0), "Beitzah 29", id="randomly_picked_date"),
        pytest.param(dt(2020, 1, 4, 0), "Niddah 73", id="end_of_cycle13"),
        pytest.param(dt(2020, 1, 5, 0), "Berachos 2", id="start_of_cycle14"),
        pytest.param(dt(2020, 3, 7, 0), "Berachos 64", id="cycle14_end_of_berachos"),
        pytest.param(dt(2020, 3, 8, 0), "Shabbos 2", id="cycle14_start_of_shabbos"),
    ],
    indirect=True,
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_at_time")
async def test_dafyomi_sensor(hass: HomeAssistant, results: str) -> None:
    """Test Daf Yomi sensor output."""
    assert hass.states.get("sensor.jewish_calendar_daf_yomi").state == results


async def test_no_discovery_info(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup without discovery info."""
    assert SENSOR_DOMAIN not in hass.config.components
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {CONF_PLATFORM: DOMAIN}},
    )
    await hass.async_block_till_done()
    assert SENSOR_DOMAIN in hass.config.components
