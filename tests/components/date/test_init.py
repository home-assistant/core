"""The tests for the date component."""
from datetime import date

from homeassistant.components.date import ATTR_DAY, ATTR_MONTH, ATTR_YEAR, DateEntity
from homeassistant.core import HomeAssistant


class MockDateEntity(DateEntity):
    """Mock date device to use in tests."""

    _attr_name = "date"

    def __init__(self, native_value=date(2020, 1, 1)) -> None:
        """Initialize mock date entity."""
        self._attr_native_value = native_value

    async def async_set_value(self, value: date) -> None:
        """Set the value of the date."""
        self._attr_native_value = value


async def test_date(hass: HomeAssistant) -> None:
    """Test date entity."""
    date_entity = MockDateEntity()
    assert date_entity.state == "2020-01-01"
    assert date_entity.state_attributes == {
        ATTR_DAY: 1,
        ATTR_MONTH: 1,
        ATTR_YEAR: 2020,
    }

    date_entity = MockDateEntity(native_value=None)
    assert date_entity.state is None
    assert date_entity.state_attributes == {
        ATTR_DAY: None,
        ATTR_MONTH: None,
        ATTR_YEAR: None,
    }
