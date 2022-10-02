"""The tests for the time component."""
from datetime import datetime, time

from homeassistant.components.time import (
    ATTR_HOUR,
    ATTR_MINUTE,
    ATTR_SECOND,
    TimeEntity,
)


class MockTimeEntity(TimeEntity):
    """Mock time device to use in tests."""

    def __init__(self, native_value: datetime | time = time(12, 0, 0)):
        """Initialize mock time entity."""
        self._attr_native_value = native_value

    async def async_set_value(self, time_value: time) -> None:
        """Set the value of the time."""
        self._attr_native_value = time_value


async def test_time():
    """Test time entity."""
    time_entity = MockTimeEntity(native_value=time(12, 0, 0))
    assert time_entity.state == "12:00:00"
    assert time_entity.hour == 12
    assert time_entity.minute == 0
    assert time_entity.second == 0
    assert time_entity.state_attributes == {
        ATTR_HOUR: 12,
        ATTR_MINUTE: 0,
        ATTR_SECOND: 0,
    }


async def test_time_with_datetime():
    """Test time with datetime as native value."""
    time_entity = MockTimeEntity(datetime(2020, 1, 1, 12, 0, 0))
    assert time_entity.state == "12:00:00"
    assert time_entity.hour == 12
    assert time_entity.minute == 0
    assert time_entity.second == 0
    assert time_entity.state_attributes == {
        ATTR_HOUR: 12,
        ATTR_MINUTE: 0,
        ATTR_SECOND: 0,
    }
