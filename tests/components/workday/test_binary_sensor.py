"""Tests the Home Assistant workday binary sensor."""

from datetime import date, datetime, timedelta, timezone
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.workday.binary_sensor import SERVICE_CHECK_DATE
from homeassistant.components.workday.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.dt import UTC

from . import (
    TEST_CONFIG_ADD_REMOVE_DATE_RANGE,
    TEST_CONFIG_DAY_AFTER_TOMORROW,
    TEST_CONFIG_EXAMPLE_1,
    TEST_CONFIG_EXAMPLE_2,
    TEST_CONFIG_INCLUDE_HOLIDAY,
    TEST_CONFIG_INCORRECT_ADD_DATE_RANGE,
    TEST_CONFIG_INCORRECT_ADD_DATE_RANGE_LEN,
    TEST_CONFIG_INCORRECT_ADD_REMOVE,
    TEST_CONFIG_INCORRECT_COUNTRY,
    TEST_CONFIG_INCORRECT_PROVINCE,
    TEST_CONFIG_INCORRECT_REMOVE_DATE_RANGE,
    TEST_CONFIG_INCORRECT_REMOVE_DATE_RANGE_LEN,
    TEST_CONFIG_NO_COUNTRY,
    TEST_CONFIG_NO_COUNTRY_ADD_HOLIDAY,
    TEST_CONFIG_NO_LANGUAGE_CONFIGURED,
    TEST_CONFIG_NO_PROVINCE,
    TEST_CONFIG_NO_STATE,
    TEST_CONFIG_REMOVE_HOLIDAY,
    TEST_CONFIG_REMOVE_NAMED,
    TEST_CONFIG_TOMORROW,
    TEST_CONFIG_WITH_PROVINCE,
    TEST_CONFIG_WITH_STATE,
    TEST_CONFIG_YESTERDAY,
    TEST_LANGUAGE_CHANGE,
    TEST_LANGUAGE_NO_CHANGE,
    init_integration,
)

from tests.common import async_fire_time_changed


@pytest.mark.parametrize(
    ("config", "expected_state", "expected_state_weekend"),
    [
        (TEST_CONFIG_NO_COUNTRY, "on", "off"),
        (TEST_CONFIG_WITH_PROVINCE, "off", "off"),
        (TEST_CONFIG_NO_PROVINCE, "off", "off"),
        (TEST_CONFIG_WITH_STATE, "on", "off"),
        (TEST_CONFIG_NO_STATE, "on", "off"),
        (TEST_CONFIG_EXAMPLE_1, "on", "off"),
        (TEST_CONFIG_EXAMPLE_2, "off", "off"),
        (TEST_CONFIG_TOMORROW, "off", "off"),
        (TEST_CONFIG_DAY_AFTER_TOMORROW, "off", "off"),
        (TEST_CONFIG_YESTERDAY, "on", "off"),  # Friday was good Friday
        (TEST_CONFIG_NO_LANGUAGE_CONFIGURED, "off", "off"),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    config: dict[str, Any],
    expected_state: str,
    expected_state_weekend: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup from various configs."""
    # Start on a Friday
    await hass.config.async_set_time_zone("Europe/Paris")
    freezer.move_to(datetime(2022, 4, 15, 0, tzinfo=timezone(timedelta(hours=1))))
    await init_integration(hass, config)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state is not None
    assert state.state == expected_state
    assert state.attributes == {
        "friendly_name": "Workday Sensor",
        "workdays": config["workdays"],
        "excludes": config["excludes"],
        "days_offset": config["days_offset"],
    }

    freezer.tick(timedelta(days=1))  # Saturday
    async_fire_time_changed(hass)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state is not None
    assert state.state == expected_state_weekend


async def test_setup_with_invalid_province_from_yaml(hass: HomeAssistant) -> None:
    """Test setup invalid province with import."""
    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "workday",
                "country": "DE",
                "province": "invalid",
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state is None


async def test_setup_with_working_holiday(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup from various configs."""
    freezer.move_to(datetime(2017, 1, 6, 12, tzinfo=UTC))  # Friday
    await init_integration(hass, TEST_CONFIG_INCLUDE_HOLIDAY)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state is not None
    assert state.state == "on"


@pytest.mark.parametrize(
    "config",
    [
        TEST_CONFIG_EXAMPLE_2,
        TEST_CONFIG_NO_COUNTRY_ADD_HOLIDAY,
    ],
)
async def test_setup_add_holiday(
    hass: HomeAssistant,
    config: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup from various configs."""
    freezer.move_to(datetime(2020, 2, 24, 12, tzinfo=UTC))  # Monday
    await init_integration(hass, TEST_CONFIG_EXAMPLE_2)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state is not None
    assert state.state == "off"


@pytest.mark.parametrize(
    "time_zone", ["Asia/Tokyo", "Europe/Berlin", "America/Chicago", "US/Hawaii"]
)
async def test_setup_no_country_weekend(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    time_zone: str,
) -> None:
    """Test setup shows weekend as non-workday with no country."""
    await hass.config.async_set_time_zone(time_zone)
    zone = await dt_util.async_get_time_zone(time_zone)
    freezer.move_to(datetime(2020, 2, 22, 0, 1, 1, tzinfo=zone))  # Saturday
    await init_integration(hass, TEST_CONFIG_NO_COUNTRY)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state is not None
    assert state.state == "off"

    freezer.move_to(datetime(2020, 2, 24, 23, 59, 59, tzinfo=zone))  # Monday
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state is not None
    assert state.state == "on"


@pytest.mark.parametrize(
    "time_zone", ["Asia/Tokyo", "Europe/Berlin", "America/Chicago", "US/Hawaii"]
)
async def test_setup_no_country_weekday(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    time_zone: str,
) -> None:
    """Test setup shows a weekday as a workday with no country."""
    await hass.config.async_set_time_zone(time_zone)
    zone = await dt_util.async_get_time_zone(time_zone)
    freezer.move_to(datetime(2020, 2, 21, 23, 59, 59, tzinfo=zone))  # Friday
    await init_integration(hass, TEST_CONFIG_NO_COUNTRY)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state is not None
    assert state.state == "on"

    freezer.move_to(datetime(2020, 2, 22, 23, 59, 59, tzinfo=zone))  # Saturday
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state is not None
    assert state.state == "off"


async def test_setup_remove_holiday(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup from various configs."""
    freezer.move_to(datetime(2020, 12, 25, 12, tzinfo=UTC))  # Friday
    await init_integration(hass, TEST_CONFIG_REMOVE_HOLIDAY)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state is not None
    assert state.state == "on"


async def test_setup_remove_holiday_named(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup from various configs."""
    freezer.move_to(datetime(2020, 12, 25, 12, tzinfo=UTC))  # Friday
    await init_integration(hass, TEST_CONFIG_REMOVE_NAMED)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state is not None
    assert state.state == "on"


async def test_setup_day_after_tomorrow(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup from various configs."""
    freezer.move_to(datetime(2022, 5, 27, 12, tzinfo=UTC))  # Friday
    await init_integration(hass, TEST_CONFIG_DAY_AFTER_TOMORROW)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state is not None
    assert state.state == "off"


async def test_setup_faulty_country(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup with faulty province."""
    freezer.move_to(datetime(2017, 1, 6, 12, tzinfo=UTC))  # Friday
    await init_integration(hass, TEST_CONFIG_INCORRECT_COUNTRY)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state is None

    assert "Selected country ZZ is not valid" in caplog.text


async def test_setup_faulty_province(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup with faulty province."""
    freezer.move_to(datetime(2017, 1, 6, 12, tzinfo=UTC))  # Friday
    await init_integration(hass, TEST_CONFIG_INCORRECT_PROVINCE)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state is None

    assert "Selected province ZZ for country DE is not valid" in caplog.text


async def test_setup_incorrect_add_remove(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup with incorrect add/remove custom holiday."""
    freezer.move_to(datetime(2017, 1, 6, 12, tzinfo=UTC))  # Friday
    await init_integration(hass, TEST_CONFIG_INCORRECT_ADD_REMOVE)

    hass.states.get("binary_sensor.workday_sensor")

    assert (
        "Could not add custom holidays: Cannot parse date from string '2023-12-32'"
        in caplog.text
    )
    assert "No holiday found matching '2023-12-32'" in caplog.text


async def test_setup_incorrect_add_holiday_ranges(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup with incorrect add/remove holiday ranges."""
    freezer.move_to(datetime(2017, 1, 6, 12, tzinfo=UTC))  # Friday
    await init_integration(hass, TEST_CONFIG_INCORRECT_ADD_DATE_RANGE)
    await init_integration(hass, TEST_CONFIG_INCORRECT_ADD_DATE_RANGE_LEN, "2")

    hass.states.get("binary_sensor.workday_sensor")

    assert "Incorrect dates in date range: 2023-12-30,2023-12-32" in caplog.text
    assert (
        "Incorrect dates in date range: 2023-12-29,2023-12-30,2023-12-31" in caplog.text
    )


async def test_setup_incorrect_remove_holiday_ranges(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup with incorrect add/remove holiday ranges."""
    freezer.move_to(datetime(2017, 1, 6, 12, tzinfo=UTC))  # Friday
    await init_integration(hass, TEST_CONFIG_INCORRECT_REMOVE_DATE_RANGE)
    await init_integration(hass, TEST_CONFIG_INCORRECT_REMOVE_DATE_RANGE_LEN, "2")

    hass.states.get("binary_sensor.workday_sensor")

    assert "Incorrect dates in date range: 2023-12-30,2023-12-32" in caplog.text
    assert (
        "Incorrect dates in date range: 2023-12-29,2023-12-30,2023-12-31" in caplog.text
    )


async def test_setup_date_range(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup with date range."""
    freezer.move_to(
        datetime(2022, 12, 26, 12, tzinfo=UTC)
    )  # Boxing Day should be working day
    await init_integration(hass, TEST_CONFIG_ADD_REMOVE_DATE_RANGE)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state.state == "on"


async def test_check_date_service(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test check date service with response data."""

    freezer.move_to(datetime(2017, 1, 6, 12, tzinfo=UTC))  # Friday
    await init_integration(hass, TEST_CONFIG_WITH_PROVINCE)

    hass.states.get("binary_sensor.workday_sensor")

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CHECK_DATE,
        {
            "entity_id": "binary_sensor.workday_sensor",
            "check_date": date(2022, 12, 25),  # Christmas Day
        },
        blocking=True,
        return_response=True,
    )
    assert response == {"binary_sensor.workday_sensor": {"workday": False}}

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CHECK_DATE,
        {
            "entity_id": "binary_sensor.workday_sensor",
            "check_date": date(2022, 12, 23),  # Normal Friday
        },
        blocking=True,
        return_response=True,
    )
    assert response == {"binary_sensor.workday_sensor": {"workday": True}}

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CHECK_DATE,
        {
            "entity_id": "binary_sensor.workday_sensor",
            "check_date": date(2022, 12, 17),  # Saturday (no workday)
        },
        blocking=True,
        return_response=True,
    )
    assert response == {"binary_sensor.workday_sensor": {"workday": False}}


async def test_language_difference_english_language(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling difference in English language naming."""
    await init_integration(hass, TEST_LANGUAGE_CHANGE)
    assert "Changing language from en to en_US" in caplog.text


async def test_language_difference_no_change_other_language(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test skipping if no difference in language naming."""
    await init_integration(hass, TEST_LANGUAGE_NO_CHANGE)
    assert "Changing language from en to en_US" not in caplog.text
