"""The tests for the datetime component."""
from datetime import date, datetime, time

import pytest
import voluptuous as vol

from homeassistant.components.datetime import (
    ATTR_DATE,
    ATTR_DATETIME,
    ATTR_DAY,
    ATTR_HAS_DATE,
    ATTR_HAS_TIME,
    ATTR_MODE,
    ATTR_MONTH,
    ATTR_TIME,
    ATTR_TIMESTAMP,
    ATTR_YEAR,
    DOMAIN,
    SERVICE_SET_DATETIME,
    DateTimeEntity,
    DateTimeMode,
    _async_set_datetime,
    _validate_svc_attrs_and_split_date_time,
)
from homeassistant.core import ServiceCall


class MockDateTimeEntity(DateTimeEntity):
    """Mock datetime device to use in tests."""

    def __init__(
        self,
        native_value=datetime(2020, 1, 1, 12, 0, 0),
        mode=DateTimeMode.DATETIME,
    ):
        """Initialize mock datetime entity."""
        self._attr_native_value = native_value
        self._attr_mode = mode

    async def async_set_datetime(self, dt_value: datetime | date | time) -> None:
        """Set the value of the datetime."""
        self._attr_native_value = dt_value


async def test_datetime_default():
    """Test default datetime."""
    datetime_entity = MockDateTimeEntity()
    assert datetime_entity.state == "2020-01-01 12:00:00"
    assert datetime_entity.mode == DateTimeMode.DATETIME
    assert datetime_entity.has_time
    assert datetime_entity.has_date
    assert datetime_entity.day == 1
    assert datetime_entity.month == 1
    assert datetime_entity.year == 2020
    assert datetime_entity.timestamp == 1577898000.0
    assert datetime_entity.capability_attributes == {ATTR_MODE: DateTimeMode.DATETIME}
    assert datetime_entity.state_attributes == {
        ATTR_MODE: DateTimeMode.DATETIME,
        ATTR_HAS_DATE: True,
        ATTR_HAS_TIME: True,
        ATTR_DAY: 1,
        ATTR_MONTH: 1,
        ATTR_YEAR: 2020,
        ATTR_TIMESTAMP: 1577898000.0,
    }


async def test_datetime_date():
    """Test datetime in date mode."""
    datetime_entity = MockDateTimeEntity(
        native_value=date(2020, 1, 1), mode=DateTimeMode.DATE
    )
    assert datetime_entity.state == "2020-01-01"
    assert datetime_entity.mode == DateTimeMode.DATE
    assert not datetime_entity.has_time
    assert datetime_entity.has_date
    assert datetime_entity.day == 1
    assert datetime_entity.month == 1
    assert datetime_entity.year == 2020
    assert not datetime_entity.timestamp
    assert datetime_entity.capability_attributes == {ATTR_MODE: DateTimeMode.DATE}
    assert datetime_entity.state_attributes == {
        ATTR_MODE: DateTimeMode.DATE,
        ATTR_HAS_DATE: True,
        ATTR_HAS_TIME: False,
        ATTR_DAY: 1,
        ATTR_MONTH: 1,
        ATTR_YEAR: 2020,
    }


async def test_datetime_time():
    """Test datetime in time mode."""
    datetime_entity = MockDateTimeEntity(
        native_value=time(12, 0, 0), mode=DateTimeMode.TIME
    )
    assert datetime_entity.state == "12:00:00"
    assert datetime_entity.mode == DateTimeMode.TIME
    assert datetime_entity.has_time
    assert not datetime_entity.has_date
    assert not datetime_entity.day
    assert not datetime_entity.month
    assert not datetime_entity.year
    assert not datetime_entity.timestamp
    assert datetime_entity.capability_attributes == {ATTR_MODE: DateTimeMode.TIME}
    assert datetime_entity.state_attributes == {
        ATTR_MODE: DateTimeMode.TIME,
        ATTR_HAS_DATE: False,
        ATTR_HAS_TIME: True,
    }


async def test_datetime_date_mode_with_datetime():
    """Test datetime in date mode with datetime as native value."""
    datetime_entity = MockDateTimeEntity(mode=DateTimeMode.DATE)
    assert datetime_entity.state == "2020-01-01"
    assert datetime_entity.mode == DateTimeMode.DATE
    assert not datetime_entity.has_time
    assert datetime_entity.has_date
    assert datetime_entity.day == 1
    assert datetime_entity.month == 1
    assert datetime_entity.year == 2020
    assert not datetime_entity.timestamp
    assert datetime_entity.capability_attributes == {ATTR_MODE: DateTimeMode.DATE}
    assert datetime_entity.state_attributes == {
        ATTR_MODE: DateTimeMode.DATE,
        ATTR_HAS_DATE: True,
        ATTR_HAS_TIME: False,
        ATTR_DAY: 1,
        ATTR_MONTH: 1,
        ATTR_YEAR: 2020,
    }


async def test_datetime_time_mode_with_datetime():
    """Test datetime in time mode with datetime as native value."""
    datetime_entity = MockDateTimeEntity(mode=DateTimeMode.TIME)
    assert datetime_entity.state == "12:00:00"
    assert datetime_entity.mode == DateTimeMode.TIME
    assert datetime_entity.has_time
    assert not datetime_entity.has_date
    assert not datetime_entity.day
    assert not datetime_entity.month
    assert not datetime_entity.year
    assert not datetime_entity.timestamp
    assert datetime_entity.capability_attributes == {ATTR_MODE: DateTimeMode.TIME}
    assert datetime_entity.state_attributes == {
        ATTR_MODE: DateTimeMode.TIME,
        ATTR_HAS_DATE: False,
        ATTR_HAS_TIME: True,
    }


async def test_datetime_date_mode_with_time():
    """Test datetime in date mode with time as native value."""
    datetime_entity = MockDateTimeEntity(
        native_value=time(12, 0, 0), mode=DateTimeMode.DATE
    )
    assert datetime_entity.state is None
    assert datetime_entity.mode == DateTimeMode.DATE
    assert not datetime_entity.has_time
    assert datetime_entity.has_date
    assert not datetime_entity.day
    assert not datetime_entity.month
    assert not datetime_entity.year
    assert not datetime_entity.timestamp
    assert datetime_entity.capability_attributes == {ATTR_MODE: DateTimeMode.DATE}
    assert datetime_entity.state_attributes == {
        ATTR_MODE: DateTimeMode.DATE,
        ATTR_HAS_DATE: True,
        ATTR_HAS_TIME: False,
    }


async def test_set_datetime_mode_data_mismatch():
    """Test set_datetime service with mode and input data mismatched."""
    datetime_entity = MockDateTimeEntity(mode=DateTimeMode.DATE)
    with pytest.raises(vol.Error):
        await _async_set_datetime(
            datetime_entity,
            ServiceCall(
                DOMAIN,
                SERVICE_SET_DATETIME,
                {ATTR_DATE: date(2020, 1, 1), ATTR_TIME: time(12, 0, 0)},
            ),
        )

    datetime_entity = MockDateTimeEntity(mode=DateTimeMode.TIME)
    with pytest.raises(vol.Error):
        await _async_set_datetime(
            datetime_entity,
            ServiceCall(
                DOMAIN,
                SERVICE_SET_DATETIME,
                {ATTR_DATE: date(2020, 1, 1), ATTR_TIME: time(12, 0, 0)},
            ),
        )

    datetime_entity = MockDateTimeEntity(
        native_value=date(2020, 1, 1), mode=DateTimeMode.DATETIME
    )
    with pytest.raises(vol.Error):
        await _async_set_datetime(
            datetime_entity,
            ServiceCall(
                DOMAIN,
                SERVICE_SET_DATETIME,
                {ATTR_DATE: date(2020, 1, 1)},
            ),
        )


async def test_set_datetime_valid():
    """Test set_datetime service valid scenarios."""
    datetime_entity = MockDateTimeEntity(mode=DateTimeMode.DATETIME)
    await _async_set_datetime(
        datetime_entity,
        ServiceCall(
            DOMAIN,
            SERVICE_SET_DATETIME,
            {ATTR_DATE: date(2021, 12, 12)},
        ),
    )
    assert datetime_entity.state == "2021-12-12 12:00:00"

    await _async_set_datetime(
        datetime_entity,
        ServiceCall(
            DOMAIN,
            SERVICE_SET_DATETIME,
            {ATTR_TIME: time(5, 1, 2)},
        ),
    )
    assert datetime_entity.state == "2021-12-12 05:01:02"

    datetime_entity = MockDateTimeEntity(mode=DateTimeMode.DATE)
    await _async_set_datetime(
        datetime_entity,
        ServiceCall(
            DOMAIN,
            SERVICE_SET_DATETIME,
            {ATTR_DATE: date(2021, 12, 12)},
        ),
    )
    assert datetime_entity.state == "2021-12-12"

    datetime_entity = MockDateTimeEntity(mode=DateTimeMode.TIME)
    await _async_set_datetime(
        datetime_entity,
        ServiceCall(
            DOMAIN,
            SERVICE_SET_DATETIME,
            {ATTR_TIME: time(5, 1, 2)},
        ),
    )
    assert datetime_entity.state == "05:01:02"


async def test_validate():
    """Test service validation."""
    with pytest.raises(vol.Invalid):
        _validate_svc_attrs_and_split_date_time(
            {ATTR_DATETIME: datetime(2020, 1, 1, 12, 0, 0), ATTR_TIMESTAMP: 12.0}
        )

    assert _validate_svc_attrs_and_split_date_time(
        {ATTR_DATETIME: datetime(2020, 1, 1, 12, 0, 0)}
    ) == {ATTR_DATE: date(2020, 1, 1), ATTR_TIME: time(12, 0, 0)}
