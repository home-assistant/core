"""The tests for the Select component."""
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant


class MockSelectEntity(SelectEntity):
    """Mock SelectEntity to use in tests."""

    _attr_current_option = "option_one"
    _attr_options = ["option_one", "option_two", "option_three"]


async def test_select(hass: HomeAssistant) -> None:
    """Test getting data from the mocked select entity."""
    select = MockSelectEntity()
    assert select.current_option == "option_one"
    assert select.options == ["option_one", "option_two", "option_three"]
