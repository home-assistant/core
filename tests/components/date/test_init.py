"""The tests for the date component."""
from datetime import date, datetime

from homeassistant.components.date import ATTR_DAY, ATTR_MONTH, ATTR_YEAR, DateEntity


class MockDateEntity(DateEntity):
    """Mock date device to use in tests."""

    _attr_name = "date"

    def __init__(self, native_value=date(2020, 1, 1)) -> None:
        """Initialize mock date entity."""
        self._attr_native_value = native_value

    async def async_set_value(self, date_value: date) -> None:
        """Set the value of the date."""
        self._attr_native_value = date_value


async def test_date(hass):
    """Test date entity."""
    date_entity = MockDateEntity()
    assert date_entity.state == "2020-01-01"
    assert date_entity.day == 1
    assert date_entity.month == 1
    assert date_entity.year == 2020
    assert date_entity.state_attributes == {
        ATTR_DAY: 1,
        ATTR_MONTH: 1,
        ATTR_YEAR: 2020,
    }


async def test_date_with_datetime():
    """Test date with datetime as native value."""
    date_entity = MockDateEntity(datetime(2020, 1, 1, 12, 0, 0))
    assert date_entity.state == "2020-01-01"
    assert date_entity.day == 1
    assert date_entity.month == 1
    assert date_entity.year == 2020
    assert date_entity.state_attributes == {
        ATTR_DAY: 1,
        ATTR_MONTH: 1,
        ATTR_YEAR: 2020,
    }
