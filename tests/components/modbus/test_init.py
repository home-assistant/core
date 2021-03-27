"""The tests for the Modbus init."""
import pytest
import voluptuous as vol

from homeassistant.components.modbus import number


async def test_number_validator():
    """Test number validator."""

    # positive tests
    value = number(15)
    assert isinstance(value, int)

    value = number(15.1)
    assert isinstance(value, float)

    value = number("15")
    assert isinstance(value, int)

    value = number("15.1")
    assert isinstance(value, float)

    # exception test
    try:
        value = number("x15.1")
    except (vol.Invalid):
        return

    pytest.fail("Number not throwing exception")
