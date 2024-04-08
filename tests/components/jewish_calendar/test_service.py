"""Tests for service.py."""

from freezegun import freeze_time
import pytest

from homeassistant.components.jewish_calendar.const import CONF_DIASPORA, DOMAIN
from homeassistant.const import CONF_LANGUAGE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_config_entry(hass: HomeAssistant, data: dict[str, str | bool]):
    """Add a Jewish Calendar config entry to Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("input", "expected"),
    [
        # Date only
        ("2023-01-01", "2023-01-01"),
        # Before sunset (time comes from plag_mincha below)
        ("2023-01-01T15:50:30-08:00", "2023-01-01"),
        # After sunset (time comes from three_stars below)
        ("2023-01-01T17:34:00-08:00", "2023-01-02"),
    ],
)
async def test_get_gregorian_date(
    hass: HomeAssistant, input: str, expected: str
) -> None:
    """Tests get_gregorian_date with various inputs."""
    await setup_config_entry(hass, {CONF_LANGUAGE: "hebrew"})

    result = await hass.services.async_call(
        DOMAIN,
        "get_gregorian_date",
        {"date": input},
        blocking=True,
        return_response=True,
    )

    assert result == {"date": expected}


async def test_get_gregorian_date_range(hass: HomeAssistant) -> None:
    """Tests get_gregorian_date_range with various inputs."""
    await setup_config_entry(hass, {CONF_LANGUAGE: "hebrew"})

    result = await hass.services.async_call(
        DOMAIN,
        "get_gregorian_date_range",
        {"date": "2024-04-04", "number_of_days": 7},
        blocking=True,
        return_response=True,
    )

    assert result == {
        "dates": [
            {"date": "2024-04-04"},
            {"date": "2024-04-05"},
            {"date": "2024-04-06"},
            {"date": "2024-04-07"},
            {"date": "2024-04-08"},
            {"date": "2024-04-09"},
            {"date": "2024-04-10"},
        ]
    }


@freeze_time("2020-01-01")  # Hebrew year 5780.
@pytest.mark.parametrize(
    ("input", "expected"),
    [
        ({"year": "5784", "month": "Nisan", "day": 1}, "1 Nisan 5784"),
        ({"year": "5784", "month": "ניסן", "day": 1}, "1 Nisan 5784"),
        # 5784 is a leap year
        ({"year": "5784", "month": "Adar I", "day": 1}, "1 Adar I 5784"),
        ({"year": "5784", "month": "Adar II", "day": 1}, "1 Adar II 5784"),
        # 5783 is not a leap year
        ({"year": "5783", "month": "Adar I", "day": 1}, "1 Adar 5783"),
        ({"year": "5783", "month": "Adar II", "day": 1}, "1 Adar 5783"),
        # Year defaults to current year (mocked above, not a leap year)
        ({"month": "תשרי", "day": 1}, "1 Tishrei 5780"),
        ({"month": "Adar I", "day": 1}, "1 Adar 5780"),
        ({"month": "Adar II", "day": 1}, "1 Adar 5780"),
    ],
)
async def test_get_hebrew_date_result(
    hass: HomeAssistant, input: dict[str, str], expected: str
) -> None:
    """Tests get_hebrew_date with various inputs."""
    await setup_config_entry(hass, {CONF_LANGUAGE: "english"})

    result = await hass.services.async_call(
        DOMAIN,
        "get_hebrew_date",
        {**input, "include_hebrew_date_info": "true"},
        blocking=True,
        return_response=True,
    )

    assert result["hebrew_date"]["str"] == expected


@pytest.mark.parametrize(
    ("input", "expected"),
    [
        ({"date": "2023-09-16"}, "1 Tishrei 5784"),
        ({"date": "2023-09-17"}, "2 Tishrei 5784"),
        ({"date": "2023-09-18"}, "3 Tishrei 5784"),
        ({"date": "2023-09-19"}, "9 Tishrei 5784"),
        ({"date": "2024-04-18", "types": "YOM_TOV"}, "15 Nisan 5784"),
        ({"date": "2024-04-18", "types": "EREV_YOM_TOV"}, "14 Nisan 5784"),
        ({"date": "2024-04-18", "types": "HOL_HAMOED"}, "17 Nisan 5784"),
        # Wrap around to next year
        ({"date": "2023-09-15", "types": "YOM_TOV"}, "1 Tishrei 5784"),
        # And preserve diaspora
        ({"date": "2023-09-15", "types": "HOL_HAMOED"}, "17 Tishrei 5784"),
    ],
)
async def test_get_next_holiday(
    hass: HomeAssistant, input: dict[str, str], expected: str
) -> None:
    """Tests get_next_holiday with various inputs."""
    await setup_config_entry(
        hass,
        {
            CONF_LANGUAGE: "english",
            CONF_DIASPORA: True,
        },
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_next_holiday",
        {**input, "include_hebrew_date_info": "true"},
        blocking=True,
        return_response=True,
    )

    assert result["hebrew_date"]["str"] == expected


@freeze_time("2020-01-01")  # Hebrew year 5780.
@pytest.mark.parametrize(
    ("input", "expected"),
    [
        # Defaults to current year (mocked above)
        ({"holidays": "פסח"}, ["15 Nisan 5780"]),
        ({"year": 5784, "holidays": "שמחת תורה"}, ["23 Tishrei 5784"]),
        # Leap Year
        ({"year": 5784, "holidays": "Purim"}, ["14 Adar II 5784"]),
        # Regular Year
        ({"year": 5783, "holidays": "Purim"}, ["14 Adar 5783"]),
        (
            {"year": 5784, "types": "MINOR_HOLIDAY"},
            ["15 Sh'vat 5784", "18 Iyyar 5784", "15 Av 5784"],
        ),
        (
            {"year": 5784, "types": "FAST_DAY"},
            [
                "3 Tishrei 5784",
                "10 Tevet 5784",
                "11 Adar II 5784",
                "17 Tammuz 5784",
                "9 Av 5784",
            ],
        ),
        ({"year": 5784, "holidays": 'יוה"כ'}, ["10 Tishrei 5784"]),
        ({"year": 5784, "holidays": "יום הכפורים"}, ["10 Tishrei 5784"]),
        (
            {"year": 5784, "holidays": "חול המועד סוכות"},
            [
                "17 Tishrei 5784",
                "18 Tishrei 5784",
                "19 Tishrei 5784",
                "20 Tishrei 5784",
            ],
        ),
    ],
)
async def test_get_holidays(
    hass: HomeAssistant, input: dict[str, str], expected: list[str]
) -> None:
    """Tests get_holidays with various inputs."""
    await setup_config_entry(
        hass,
        {
            CONF_LANGUAGE: "english",
            CONF_DIASPORA: True,
        },
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_holidays",
        {**input, "include_hebrew_date_info": "true"},
        blocking=True,
        return_response=True,
    )

    assert [r["hebrew_date"]["str"] for r in result["holidays"]] == expected


async def test_include_holiday_info_non_holiday(hass: HomeAssistant) -> None:
    """Tests include_holiday_info with a normal date."""
    await setup_config_entry(
        hass,
        {CONF_LANGUAGE: "hebrew", CONF_DIASPORA: True},
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_gregorian_date",
        {"date": "2023-01-01", "include_holiday_info": "true"},
        blocking=True,
        return_response=True,
    )

    assert result == {
        "date": "2023-01-01",
        "is_yom_tov": False,
        "is_shabbat": False,
        "holiday_name": "",
        "holiday_description": "",
        "holiday_type": "UNKNOWN",
        "first_day": "2022-12-31",
        "last_day": "2023-01-01",
    }


async def test_include_holiday_info_multi_day_holiday(hass: HomeAssistant) -> None:
    """Tests include_holiday_info with a normal date."""
    await setup_config_entry(
        hass,
        {CONF_LANGUAGE: "hebrew", CONF_DIASPORA: True},
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_gregorian_date",
        {"date": "2023-04-07", "include_holiday_info": "true"},
        blocking=True,
        return_response=True,
    )

    assert result == {
        "date": "2023-04-07",
        "is_yom_tov": True,
        "is_shabbat": False,
        "holiday_name": "pesach_ii",
        "holiday_description": "שני של פסח",
        "holiday_type": "YOM_TOV",
        "first_day": "2023-04-06",
        "last_day": "2023-04-08",
    }


async def test_include_hebrew_date_info(hass: HomeAssistant) -> None:
    """Tests get_gregorian_date with include_hebrew_date_info."""
    await setup_config_entry(hass, {CONF_LANGUAGE: "hebrew"})

    result = await hass.services.async_call(
        DOMAIN,
        "get_gregorian_date",
        {"date": "2023-01-01", "include_hebrew_date_info": "true"},
        blocking=True,
        return_response=True,
    )

    assert result == {
        "date": "2023-01-01",
        "hebrew_date": {
            "str": "ח' טבת ה' תשפ\"ג",
            "year": 5783,
            "month_name": {"french": "Tevet", "english": "Tevet", "hebrew": "טבת"},
            "day": 8,
        },
        "day_of_week": 1,
        "daf_yomi": {
            "label": "נדרים סח",
            "mesechta": {"french": "Nedarim", "english": "Nedarim", "hebrew": "נדרים"},
            "daf": 68,
        },
        "parasha": {"french": "Vaye'hi", "english": "Vayechi", "hebrew": "ויחי"},
        "omer_day": 0,
        "is_yom_tov": False,
        "is_shabbat": False,
        "upcoming_shabbat": "2023-01-07",
        "upcoming_yom_tov": "2023-04-06",
        "upcoming_shabbat_or_yom_tov": "2023-01-07",
    }


async def test_include_zmanim(hass: HomeAssistant) -> None:
    """Tests get_gregorian_date with include_zmanim."""
    await setup_config_entry(hass, {CONF_LANGUAGE: "hebrew"})

    result = await hass.services.async_call(
        DOMAIN,
        "get_gregorian_date",
        {"date": "2023-01-01", "include_zmanim": "true"},
        blocking=True,
        return_response=True,
    )

    assert result == {
        "date": "2023-01-01",
        "zmanim": {
            "big_mincha": "2023-01-01T12:17:00-08:00",
            "first_light": "2023-01-01T05:33:00-08:00",
            "first_stars": "2023-01-01T17:21:00-08:00",
            "gra_end_shma": "2023-01-01T09:22:00-08:00",
            "gra_end_tfila": "2023-01-01T10:12:00-08:00",
            "mga_end_shma": "2023-01-01T08:42:30-08:00",
            "mga_end_tfila": "2023-01-01T09:45:40-08:00",
            "midday": "2023-01-01T11:52:00-08:00",
            "midnight": "2023-01-01T23:52:00-08:00",
            "plag_mincha": "2023-01-01T15:50:30-08:00",
            "small_mincha": "2023-01-01T14:47:00-08:00",
            "stars_out": "2023-01-01T17:08:00-08:00",
            "sun_hour": "2022-12-31T16:50:00-08:00",
            "sunrise": "2023-01-01T06:52:00-08:00",
            "sunset": "2023-01-01T16:53:00-08:00",
            "talit": "2023-01-01T05:59:00-08:00",
            "three_stars": "2023-01-01T17:34:00-08:00",
        },
    }


async def test_include_all_fields(hass: HomeAssistant) -> None:
    """Tests include_holiday_info with a normal date."""
    await setup_config_entry(
        hass,
        {CONF_LANGUAGE: "hebrew", CONF_DIASPORA: True},
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_gregorian_date",
        {
            "date": "2023-04-07",
            "include_hebrew_date_info": "true",
            "include_holiday_info": "true",
            "include_zmanim": "true",
        },
        blocking=True,
        return_response=True,
    )

    assert result == {
        "date": "2023-04-07",
        "hebrew_date": {
            "str": 'ט"ז ניסן ה\' תשפ"ג',
            "year": 5783,
            "month_name": {"french": "Nissan", "english": "Nisan", "hebrew": "ניסן"},
            "day": 16,
        },
        "day_of_week": 6,
        "daf_yomi": {
            "label": "סוטה ט",
            "mesechta": {"french": "Sotah", "english": "Sotah", "hebrew": "סוטה"},
            "daf": 9,
        },
        "parasha": {"french": "none", "english": "none", "hebrew": "none"},
        "omer_day": 1,
        "is_yom_tov": True,
        "is_shabbat": False,
        "upcoming_shabbat": "2023-04-08",
        "upcoming_yom_tov": "2023-04-07",
        "upcoming_shabbat_or_yom_tov": "2023-04-07",
        "holiday_name": "pesach_ii",
        "holiday_type": "YOM_TOV",
        "holiday_description": "שני של פסח",
        "first_day": "2023-04-06",
        "last_day": "2023-04-08",
        "zmanim": {
            "sunrise": "2023-04-07T06:29:00-07:00",
            "sunset": "2023-04-07T19:13:00-07:00",
            "sun_hour": "2023-04-06T18:03:00-07:00",
            "midday": "2023-04-07T12:51:00-07:00",
            "first_light": "2023-04-07T05:14:00-07:00",
            "talit": "2023-04-07T05:40:00-07:00",
            "first_stars": "2023-04-07T19:39:00-07:00",
            "three_stars": "2023-04-07T19:51:00-07:00",
            "plag_mincha": "2023-04-07T17:54:15-07:00",
            "stars_out": "2023-04-07T19:31:54-07:00",
            "small_mincha": "2023-04-07T16:27:30-07:00",
            "big_mincha": "2023-04-07T13:18:30-07:00",
            "mga_end_shma": "2023-04-07T09:02:30-07:00",
            "gra_end_shma": "2023-04-07T09:38:00-07:00",
            "mga_end_tfila": "2023-04-07T10:18:40-07:00",
            "gra_end_tfila": "2023-04-07T10:41:00-07:00",
            "midnight": "2023-04-08T00:51:00-07:00",
        },
    }
