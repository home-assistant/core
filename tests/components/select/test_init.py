"""The tests for the Select component."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.select import ATTR_OPTIONS, SelectEntity
from homeassistant.core import HomeAssistant


class MockSelectEntity(SelectEntity):
    """Mock SelectEntity to use in tests."""

    _attr_current_option = "option_one"
    _attr_options = ["option_one", "option_two", "option_three"]

    async def async_select_option(self, option: str) -> None:
        """Test changing the selected option."""
        return await super().async_select_option(option)


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

    select.hass = hass

    with pytest.raises(NotImplementedError):
        await select.async_select_option("option_one")

    select.select_option = MagicMock()
    await select.async_select_option("option_one")

    assert select.select_option.called
    assert select.select_option.call_args[0][0] == "option_one"

    assert select.capability_attributes[ATTR_OPTIONS] == [
        "option_one",
        "option_two",
        "option_three",
    ]
