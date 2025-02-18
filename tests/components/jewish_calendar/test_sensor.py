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

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize("language", ["english", "hebrew"])
async def test_min_config(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test minimum jewish calendar configuration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.jewish_calendar_date") is not None


TEST_PARAMS = [
    (
        ("Jerusalem", dt(2018, 9, 3), {"state": "23 Elul 5778", "attr": None}),
        "english",
        "date",
    ),
    (
        ("Jerusalem", dt(2018, 9, 3), {"state": 'כ"ג אלול ה\' תשע"ח', "attr": None}),
        "hebrew",
        "date",
    ),
    (
        ("Jerusalem", dt(2018, 9, 10), {"state": "א' ראש השנה", "attr": None}),
        "hebrew",
        "holiday",
    ),
    (
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
    ),
    (
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
    ),
    (
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
    ),
    (
        ("New York", dt(2018, 9, 8), {"state": dt(2018, 9, 8, 19, 47), "attr": None}),
        "hebrew",
        "t_set_hakochavim",
    ),
    (
        ("Jerusalem", dt(2018, 9, 8), {"state": dt(2018, 9, 8, 19, 21), "attr": None}),
        "hebrew",
        "t_set_hakochavim",
    ),
    (
        ("Jerusalem", dt(2018, 10, 14), {"state": "לך לך", "attr": None}),
        "hebrew",
        "parshat_hashavua",
    ),
    (
        (
            "Jerusalem",
            dt(2018, 10, 14, 17, 0, 0),
            {"state": "ה' מרחשוון ה' תשע\"ט", "attr": None},
        ),
        "hebrew",
        "date",
    ),
    (
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
    ),
]

TEST_IDS = [
    "date_output",
    "date_output_hebrew",
    "holiday",
    "holiday_english",
    "holiday_multiple",
    "torah_reading",
    "first_stars_ny",
    "first_stars_jerusalem",
    "torah_reading_weekday",
    "date_before_sunset",
    "date_after_sunset",
]


@pytest.mark.parametrize(
    ("jcal_params", "language", "sensor"),
    TEST_PARAMS,
    ids=TEST_IDS,
    indirect=["jcal_params", "language"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_jewish_calendar_sensor(
    hass: HomeAssistant, jcal_params: dict, config_entry: MockConfigEntry, sensor: str
) -> None:
    """Test Jewish calendar sensor output."""
    with freeze_time(test_time := jcal_params["test_time"]):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        future = test_time + timedelta(seconds=30)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    result = jcal_params["results"]["state"]
    if isinstance(result, dt):
        result = dt_util.as_utc(result).isoformat()

    sensor_object = hass.states.get(f"sensor.jewish_calendar_{sensor}")
    assert sensor_object.state == result

    if attrs := getattr(jcal_params, "results", None):
        assert sensor_object.attributes == attrs


SHABBAT_PARAMS = [
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


@pytest.mark.parametrize("language", ["english", "hebrew"], indirect=True)
@pytest.mark.parametrize(
    "jcal_params", SHABBAT_PARAMS, ids=SHABBAT_TEST_IDS, indirect=True
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_shabbat_times_sensor(
    hass: HomeAssistant, jcal_params: dict, config_entry: MockConfigEntry
) -> None:
    """Test sensor output for upcoming shabbat/yomtov times."""
    with freeze_time(test_time := jcal_params["test_time"]):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        future = test_time + timedelta(seconds=30)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    for sensor_type, result_value in jcal_params["results"].items():
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


@pytest.mark.parametrize(("test_time", "result"), OMER_PARAMS, ids=OMER_TEST_IDS)
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


@pytest.mark.parametrize(("test_time", "result"), DAFYOMI_PARAMS, ids=DAFYOMI_TEST_IDS)
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
