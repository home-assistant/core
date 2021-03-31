"""The tests for the Modbus init."""
import pytest
import voluptuous as vol

from homeassistant.components.modbus import number


@pytest.mark.parametrize(
    "value,value_type",
    [
        (15, int),
        (15.1, float),
        ("15", int),
        ("15.1", float),
        (-15, int),
        (-15.1, float),
        ("-15", int),
        ("-15.1", float),
    ],
)
async def test_number_validator(value, value_type):
    """Test number validator."""

    assert isinstance(number(value), value_type)


async def test_number_exception():
    """Test number exception."""

    try:
        number("x15.1")
    except (vol.Invalid):
        return

    pytest.fail("Number not throwing exception")
