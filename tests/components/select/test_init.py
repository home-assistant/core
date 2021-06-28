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
    assert select.state == "option_one"
    assert select.options == ["option_one", "option_two", "option_three"]

    # Test none selected
    select._attr_current_option = None
    assert select.current_option is None
    assert select.state is None

    # Test none existing selected
    select._attr_current_option = "option_four"
    assert select.current_option == "option_four"
    assert select.state is None
