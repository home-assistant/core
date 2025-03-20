"""The tests for the Jewish calendar sensors."""

from datetime import datetime as dt, timedelta

from freezegun import freeze_time
from hdate.holidays import HolidayDatabase
from hdate.parasha import Parasha
import pytest

from homeassistant.components.jewish_calendar.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_LANGUAGE, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import JewishCalendarTestParameters

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize("language", ["english", "hebrew"])
async def test_min_config(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test minimum jewish calendar configuration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.jewish_calendar_date") is not None


TEST_PARAMS = [
    pytest.param(
        ("Jerusalem", dt(2018, 9, 3), {"state": "23 Elul 5778", "attr": None}),
        "english",
        "date",
        id="date_output",
    ),
    pytest.param(
        ("Jerusalem", dt(2018, 9, 3), {"state": 'כ"ג אלול ה\' תשע"ח', "attr": None}),
        "hebrew",
        "date",
        id="date_output_hebrew",
    ),
    pytest.param(
        ("Jerusalem", dt(2018, 9, 10), {"state": "א' ראש השנה", "attr": None}),
        "hebrew",
        "holiday",
        id="holiday",
    ),
    pytest.param(
        (
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
                    "options": HolidayDatabase(False).get_all_names("english"),
                },
            },
        ),
        "english",
        "holiday",
        id="holiday_english",
    ),
    pytest.param(
        (
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
                    "options": HolidayDatabase(False).get_all_names("english"),
                },
            },
        ),
        "english",
        "holiday",
        id="holiday_multiple",
    ),
    pytest.param(
        (
            "Jerusalem",
            dt(2018, 9, 8),
            {
                "state": "נצבים",
                "attr": {
                    "device_class": "enum",
                    "friendly_name": "Jewish Calendar Parshat Hashavua",
                    "icon": "mdi:book-open-variant",
                    "options": list(Parasha),
                },
            },
        ),
        "hebrew",
        "parshat_hashavua",
        id="torah_reading",
    ),
    pytest.param(
        ("New York", dt(2018, 9, 8), {"state": dt(2018, 9, 8, 19, 47), "attr": None}),
        "hebrew",
        "t_set_hakochavim",
        id="first_stars_ny",
    ),
    pytest.param(
        ("Jerusalem", dt(2018, 9, 8), {"state": dt(2018, 9, 8, 19, 21), "attr": None}),
        "hebrew",
        "t_set_hakochavim",
        id="first_stars_jerusalem",
    ),
    pytest.param(
        ("Jerusalem", dt(2018, 10, 14), {"state": "לך לך", "attr": None}),
        "hebrew",
        "parshat_hashavua",
        id="torah_reading_weekday",
    ),
    pytest.param(
        (
            "Jerusalem",
            dt(2018, 10, 14, 17, 0, 0),
            {"state": "ה' מרחשוון ה' תשע\"ט", "attr": None},
        ),
        "hebrew",
        "date",
        id="date_before_sunset",
    ),
    pytest.param(
        (
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
        ),
        "hebrew",
        "date",
        id="date_after_sunset",
    ),
]


@pytest.mark.parametrize(
    ("jcal_params", "language", "sensor"),
    TEST_PARAMS,
    indirect=["jcal_params", "language"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_jewish_calendar_sensor(
    hass: HomeAssistant,
    jcal_params: JewishCalendarTestParameters,
    config_entry: MockConfigEntry,
    sensor: str,
) -> None:
    """Test Jewish calendar sensor output."""
    with freeze_time(test_time := jcal_params.test_time):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        future = test_time + timedelta(seconds=30)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    result = jcal_params.results["state"]
    if isinstance(result, dt):
        result = dt_util.as_utc(result).isoformat()

    sensor_object = hass.states.get(f"sensor.jewish_calendar_{sensor}")
    assert sensor_object.state == result

    if attrs := getattr(jcal_params.results, "attr", None):
        assert sensor_object.attributes == attrs


SHABBAT_PARAMS = [
    pytest.param(
        (
            "New York",
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
        id="currently_first_shabbat",
    ),
    pytest.param(
        (
            "New York",
            dt(2018, 9, 1, 16, 0),
            {
                "english_upcoming_candle_lighting": dt(2018, 8, 31, 19, 12),
                "english_upcoming_havdalah": dt(2018, 9, 1, 20, 18),
                "english_upcoming_shabbat_candle_lighting": dt(2018, 8, 31, 19, 12),
                "english_upcoming_shabbat_havdalah": dt(2018, 9, 1, 20, 18),
                "english_parshat_hashavua": "Ki Tavo",
                "hebrew_parshat_hashavua": "כי תבוא",
            },
            50,  # Havdalah offset
        ),
        id="currently_first_shabbat_with_havdalah_offset",
    ),
    pytest.param(
        (
            "New York",
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
        id="currently_first_shabbat_bein_hashmashot_lagging_date",
    ),
    pytest.param(
        (
            "New York",
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
        id="after_first_shabbat",
    ),
    pytest.param(
        (
            "New York",
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
        id="friday_upcoming_shabbat",
    ),
    pytest.param(
        (
            "New York",
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
        id="upcoming_rosh_hashana",
    ),
    pytest.param(
        (
            "New York",
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
        id="currently_rosh_hashana",
    ),
    pytest.param(
        (
            "New York",
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
        id="second_day_rosh_hashana",
    ),
    pytest.param(
        (
            "New York",
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
        id="currently_shabbat_chol_hamoed",
    ),
    pytest.param(
        (
            "New York",
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
        id="upcoming_two_day_yomtov_in_diaspora",
    ),
    pytest.param(
        (
            "New York",
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
        id="currently_first_day_of_two_day_yomtov_in_diaspora",
    ),
    pytest.param(
        (
            "New York",
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
        id="currently_second_day_of_two_day_yomtov_in_diaspora",
    ),
    pytest.param(
        (
            "Jerusalem",
            dt(2018, 9, 29, 21, 25),
            {
                "english_upcoming_candle_lighting": dt(2018, 9, 30, 17, 46),
                "english_upcoming_havdalah": dt(2018, 10, 1, 19, 1),
                "english_upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 17, 39),
                "english_upcoming_shabbat_havdalah": dt(2018, 10, 6, 18, 54),
                "english_parshat_hashavua": "Bereshit",
                "hebrew_parshat_hashavua": "בראשית",
                "english_holiday": "Hoshana Raba",
                "hebrew_holiday": "הושענא רבה",
            },
        ),
        id="upcoming_one_day_yom_tov_in_israel",
    ),
    pytest.param(
        (
            "Jerusalem",
            dt(2018, 9, 30, 21, 25),
            {
                "english_upcoming_candle_lighting": dt(2018, 9, 30, 17, 46),
                "english_upcoming_havdalah": dt(2018, 10, 1, 19, 1),
                "english_upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 17, 39),
                "english_upcoming_shabbat_havdalah": dt(2018, 10, 6, 18, 54),
                "english_parshat_hashavua": "Bereshit",
                "hebrew_parshat_hashavua": "בראשית",
                "english_holiday": "Shmini Atzeret, Simchat Torah",
                "hebrew_holiday": "שמיני עצרת, שמחת תורה",
            },
        ),
        id="currently_one_day_yom_tov_in_israel",
    ),
    pytest.param(
        (
            "Jerusalem",
            dt(2018, 10, 1, 21, 25),
            {
                "english_upcoming_candle_lighting": dt(2018, 10, 5, 17, 39),
                "english_upcoming_havdalah": dt(2018, 10, 6, 18, 54),
                "english_upcoming_shabbat_candle_lighting": dt(2018, 10, 5, 17, 39),
                "english_upcoming_shabbat_havdalah": dt(2018, 10, 6, 18, 54),
                "english_parshat_hashavua": "Bereshit",
                "hebrew_parshat_hashavua": "בראשית",
            },
        ),
        id="after_one_day_yom_tov_in_israel",
    ),
    pytest.param(
        (
            "New York",
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
        id="currently_first_day_of_three_day_type1_yomtov_in_diaspora",  # Type 1 = Sat/Sun/Mon
    ),
    pytest.param(
        (
            "New York",
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
        id="currently_second_day_of_three_day_type1_yomtov_in_diaspora",  # Type 1 = Sat/Sun/Mon
    ),
    pytest.param(
        (
            "Jerusalem",
            dt(2017, 9, 21, 8, 25),
            {
                "english_upcoming_candle_lighting": dt(2017, 9, 20, 17, 58),
                "english_upcoming_havdalah": dt(2017, 9, 23, 19, 11),
                "english_upcoming_shabbat_candle_lighting": dt(2017, 9, 22, 17, 56),
                "english_upcoming_shabbat_havdalah": dt(2017, 9, 23, 19, 11),
                "english_parshat_hashavua": "Ha'Azinu",
                "hebrew_parshat_hashavua": "האזינו",
                "english_holiday": "Rosh Hashana I",
                "hebrew_holiday": "א' ראש השנה",
            },
        ),
        id="currently_first_day_of_three_day_type2_yomtov_in_israel",  # Type 2 = Thurs/Fri/Sat
    ),
    pytest.param(
        (
            "Jerusalem",
            dt(2017, 9, 22, 8, 25),
            {
                "english_upcoming_candle_lighting": dt(2017, 9, 20, 17, 58),
                "english_upcoming_havdalah": dt(2017, 9, 23, 19, 11),
                "english_upcoming_shabbat_candle_lighting": dt(2017, 9, 22, 17, 56),
                "english_upcoming_shabbat_havdalah": dt(2017, 9, 23, 19, 11),
                "english_parshat_hashavua": "Ha'Azinu",
                "hebrew_parshat_hashavua": "האזינו",
                "english_holiday": "Rosh Hashana II",
                "hebrew_holiday": "ב' ראש השנה",
            },
        ),
        id="currently_second_day_of_three_day_type2_yomtov_in_israel",  # Type 2 = Thurs/Fri/Sat
    ),
    pytest.param(
        (
            "Jerusalem",
            dt(2017, 9, 23, 8, 25),
            {
                "english_upcoming_candle_lighting": dt(2017, 9, 20, 17, 58),
                "english_upcoming_havdalah": dt(2017, 9, 23, 19, 11),
                "english_upcoming_shabbat_candle_lighting": dt(2017, 9, 22, 17, 56),
                "english_upcoming_shabbat_havdalah": dt(2017, 9, 23, 19, 11),
                "english_parshat_hashavua": "Ha'Azinu",
                "hebrew_parshat_hashavua": "האזינו",
                "english_holiday": "",
                "hebrew_holiday": "",
            },
        ),
        id="currently_third_day_of_three_day_type2_yomtov_in_israel",  # Type 2 = Thurs/Fri/Sat
    ),
]


@pytest.mark.parametrize("language", ["english", "hebrew"], indirect=True)
@pytest.mark.parametrize("jcal_params", SHABBAT_PARAMS, indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_shabbat_times_sensor(
    hass: HomeAssistant,
    jcal_params: JewishCalendarTestParameters,
    config_entry: MockConfigEntry,
) -> None:
    """Test sensor output for upcoming shabbat/yomtov times."""
    with freeze_time(test_time := jcal_params.test_time):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        future = test_time + timedelta(seconds=30)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    for sensor_type, result_value in jcal_params.results.items():
        if not sensor_type.startswith(language := config_entry.data[CONF_LANGUAGE]):
            continue

        sensor_type = sensor_type.replace(f"{language}_", "")

        result_value = (
            dt_util.as_utc(result_value).isoformat()
            if isinstance(result_value, dt)
            else result_value
        )

        assert hass.states.get(f"sensor.jewish_calendar_{sensor_type}").state == str(
            result_value
        ), f"Value for {sensor_type}"


OMER_PARAMS = [
    pytest.param(dt(2019, 4, 21, 0), "1", id="first_day_of_omer"),
    pytest.param(dt(2019, 4, 21, 23), "2", id="first_day_of_omer_after_tzeit"),
    pytest.param(dt(2019, 5, 23, 0), "33", id="lag_baomer"),
    pytest.param(dt(2019, 6, 8, 0), "49", id="last_day_of_omer"),
    pytest.param(dt(2019, 6, 9, 0), "0", id="shavuot_no_omer"),
    pytest.param(dt(2019, 1, 1, 0), "0", id="jan_1st_no_omer"),
]


@pytest.mark.parametrize(("test_time", "result"), OMER_PARAMS)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_omer_sensor(
    hass: HomeAssistant, config_entry: MockConfigEntry, test_time, result
) -> None:
    """Test Omer Count sensor output."""
    test_time = test_time.replace(tzinfo=dt_util.get_time_zone(hass.config.time_zone))

    with freeze_time(test_time):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        future = test_time + timedelta(seconds=30)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.jewish_calendar_day_of_the_omer").state == result


DAFYOMI_PARAMS = [
    pytest.param(dt(2014, 4, 28, 0), "Beitzah 29", id="randomly_picked_date"),
    pytest.param(dt(2020, 1, 4, 0), "Niddah 73", id="end_of_cycle13"),
    pytest.param(dt(2020, 1, 5, 0), "Berachos 2", id="start_of_cycle14"),
    pytest.param(dt(2020, 3, 7, 0), "Berachos 64", id="cycle14_end_of_berachos"),
    pytest.param(dt(2020, 3, 8, 0), "Shabbos 2", id="cycle14_start_of_shabbos"),
]


@pytest.mark.parametrize(("test_time", "result"), DAFYOMI_PARAMS)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dafyomi_sensor(
    hass: HomeAssistant, config_entry: MockConfigEntry, test_time, result
) -> None:
    """Test Daf Yomi sensor output."""
    test_time = test_time.replace(tzinfo=dt_util.get_time_zone(hass.config.time_zone))

    with freeze_time(test_time):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        future = test_time + timedelta(seconds=30)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.jewish_calendar_daf_yomi").state == result


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
