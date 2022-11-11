"""The tests for the datetime component."""
from datetime import date, datetime, time

import pytest
import voluptuous as vol

from homeassistant.components.datetime import (
    ATTR_DATE,
    ATTR_DATETIME,
    ATTR_DAY,
    ATTR_MONTH,
    ATTR_TIME,
    ATTR_TIMESTAMP,
    ATTR_YEAR,
    DOMAIN,
    SERVICE_SET_VALUE,
    DateTimeEntity,
    _async_set_value,
    _split_date_time,
)
from homeassistant.core import ServiceCall


class MockDateTimeEntity(DateTimeEntity):
    """Mock datetime device to use in tests."""

    def __init__(
        self,
        native_value=datetime(2020, 1, 1, 12, 0, 0),
    ):
        """Initialize mock datetime entity."""
        self._attr_native_value = native_value

    async def async_set_value(self, dt_value: datetime) -> None:
        """Set the value of the datetime."""
        self._attr_native_value = dt_value


async def test_datetime_default():
    """Test default datetime."""
    datetime_entity = MockDateTimeEntity()
    assert datetime_entity.state == "2020-01-01 12:00:00"
    assert datetime_entity.day == 1
    assert datetime_entity.month == 1
    assert datetime_entity.year == 2020
    assert datetime_entity.timestamp == 1577898000.0
    assert datetime_entity.state_attributes == {
        ATTR_DAY: 1,
        ATTR_MONTH: 1,
        ATTR_YEAR: 2020,
        ATTR_TIMESTAMP: 1577898000.0,
    }


async def test_set_datetime_valid():
    """Test set_datetime service valid scenarios."""
    datetime_entity = MockDateTimeEntity()
    await _async_set_value(
        datetime_entity,
        ServiceCall(
            DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_DATE: date(2021, 12, 12)},
        ),
    )
    assert datetime_entity.state == "2021-12-12 12:00:00"

    await _async_set_value(
        datetime_entity,
        ServiceCall(
            DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_TIME: time(5, 1, 2)},
        ),
    )
    assert datetime_entity.state == "2021-12-12 05:01:02"


async def test_validate():
    """Test service validation."""
    with pytest.raises(vol.Invalid):
        _split_date_time(
            {ATTR_DATETIME: datetime(2020, 1, 1, 12, 0, 0), ATTR_TIMESTAMP: 12.0}
        )

    assert _split_date_time({ATTR_DATETIME: datetime(2020, 1, 1, 12, 0, 0)}) == {
        ATTR_DATE: date(2020, 1, 1),
        ATTR_TIME: time(12, 0, 0),
    }
