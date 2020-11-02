"""The tests for the Analog Switch component."""
from unittest.mock import MagicMock

from homeassistant.components.number import NumberEntity


class MockNumberEntity(NumberEntity):
    """Mock NumberEntity device to use in tests."""

    @property
    def max_value(self) -> float:
        """Return the max value."""
        return 1.0

    @property
    def state(self):
        """Return the current value."""
        return "0.5"


async def test_step(hass):
    """Test if calculation of step."""
    number = NumberEntity()
    assert number.step == 1.0

    number_2 = MockNumberEntity()
    assert number_2.step == 0.1


async def test_sync_set_value(hass):
    """Test if async set_value calls sync set_value."""
    number = NumberEntity()
    number.hass = hass

    number.set_value = MagicMock()
    await number.async_set_value(42)

    assert number.set_value.called
    assert number.set_value.call_args[0][0] == 42


async def test_async_increment(hass):
    """Test if async increment calls set_value with correct value."""
    number = MockNumberEntity()
    number.hass = hass

    number.set_value = MagicMock()
    await number.async_increment()

    assert number.set_value.called
    assert number.set_value.call_args[0][0] == 0.6


async def test_async_decrement(hass):
    """Test if async decrement calls set_value with correct value."""
    number = MockNumberEntity()
    number.hass = hass

    number.set_value = MagicMock()
    await number.async_decrement()

    assert number.set_value.called
    assert number.set_value.call_args[0][0] == 0.4


async def test_sync_increment(hass):
    """Test if sync increment calls set_value with correct value."""
    number = MockNumberEntity()
    number.hass = hass

    number.set_value = MagicMock()
    number.increment()

    assert number.set_value.called
    assert number.set_value.call_args[0][0] == 0.6


async def test_sync_decrement(hass):
    """Test if sync decrement calls set_value with correct value."""
    number = MockNumberEntity()
    number.hass = hass

    number.set_value = MagicMock()
    number.decrement()

    assert number.set_value.called
    assert number.set_value.call_args[0][0] == 0.4
