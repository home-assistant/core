"""Tests the Home Assistant workday utilities."""
from datetime import date
from typing import Any

import pytest

from homeassistant.components.workday import util
from homeassistant.components.workday.const import ALLOWED_DAYS
from homeassistant.const import CONF_COUNTRY

from .fixtures import (
    SENSOR_DATA,
    USER_INPUT,
    USER_INPUT_ADD_BAD_HOLIDAY,
    USER_INPUT_ADD_HOLIDAY,
    USER_INPUT_EMPTY_PROVINCE,
    USER_INPUT_INVALID_PROVINCE,
    USER_INPUT_REMOVE_HOLIDAYS,
    USER_INPUT_REMOVE_NONEXISTENT_HOLIDAYS,
)


async def test_day_to_string() -> None:
    """Test that indexing a list works. Here only for test coverage."""
    for idx, val in enumerate(ALLOWED_DAYS):
        assert util.day_to_string(idx) == val

    assert util.day_to_string(len(ALLOWED_DAYS)) is None


async def test_get_date() -> None:
    """Test that returning a parameter works. Here only for test coverage."""
    test_date = date(2020, 1, 1)
    assert util.get_date(test_date) == test_date


async def test_build_with_bad_data() -> None:
    """Validate that missing/bad data raises errors."""
    holiday_data: dict[str, Any] = {}
    holiday_data.update(SENSOR_DATA)

    with pytest.raises(KeyError):
        holiday_data.pop(CONF_COUNTRY)
        util.build_holidays(holiday_data)

    with pytest.raises(AttributeError):
        holiday_data[CONF_COUNTRY] = "Test"
        util.build_holidays(holiday_data)

    with pytest.raises(util.NoProvinceError):
        holiday_data.update(SENSOR_DATA)
        holiday_data.update(USER_INPUT_INVALID_PROVINCE)
        util.build_holidays(holiday_data)

    with pytest.raises(util.AddHolidayError):
        holiday_data.update(USER_INPUT_ADD_BAD_HOLIDAY)
        util.build_holidays(holiday_data)

    with pytest.raises(util.NoSuchHolidayError):
        holiday_data.update(USER_INPUT_REMOVE_NONEXISTENT_HOLIDAYS)
        util.build_holidays(holiday_data)


async def test_build_holidays() -> None:
    """Test that building a holiday object works."""
    holiday_data = {}
    holiday_data.update(SENSOR_DATA)

    holiday_data.update(USER_INPUT)
    util.build_holidays(holiday_data)

    holiday_data.update(USER_INPUT_ADD_HOLIDAY)
    util.build_holidays(holiday_data)

    holiday_data.update(USER_INPUT_EMPTY_PROVINCE)
    util.build_holidays(holiday_data)

    holiday_data.update(USER_INPUT_REMOVE_HOLIDAYS)
    util.build_holidays(holiday_data)
