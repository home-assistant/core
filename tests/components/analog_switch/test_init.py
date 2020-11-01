"""The tests for the Analog Switch component."""
from unittest.mock import MagicMock

from homeassistant.components.analog_switch import AnalogSwitchEntity


class MockAnalogSwitchEntity(AnalogSwitchEntity):
    """Mock AnalogSwitch device to use in tests."""

    @property
    def max_value(self) -> float:
        """Return the max value."""
        return 1.0

    @property
    def state(self):
        """Return the current value."""
        return 0.5


async def test_step(hass):
    """Test if calculation of step."""
    analog_switch = AnalogSwitchEntity()
    assert analog_switch.step == 1.0

    analog_switch_2 = MockAnalogSwitchEntity()
    assert analog_switch_2.step == 0.1


async def test_sync_set_value(hass):
    """Test if async set_value calls sync set_value."""
    analog_switch = AnalogSwitchEntity()
    analog_switch.hass = hass

    analog_switch.set_value = MagicMock()
    await analog_switch.async_set_value(42)

    assert analog_switch.set_value.called
    assert analog_switch.set_value.call_args.args == (42,)


async def test_async_increment(hass):
    """Test if async increment calls set_value with correct value."""
    analog_switch = MockAnalogSwitchEntity()
    analog_switch.hass = hass

    analog_switch.set_value = MagicMock()
    await analog_switch.async_increment()

    assert analog_switch.set_value.called
    assert analog_switch.set_value.call_args.args == (0.6,)


async def test_async_decrement(hass):
    """Test if async decrement calls set_value with correct value."""
    analog_switch = MockAnalogSwitchEntity()
    analog_switch.hass = hass

    analog_switch.set_value = MagicMock()
    await analog_switch.async_decrement()

    assert analog_switch.set_value.called
    assert analog_switch.set_value.call_args.args == (0.4,)


async def test_sync_increment(hass):
    """Test if sync increment calls set_value with correct value."""
    analog_switch = MockAnalogSwitchEntity()
    analog_switch.hass = hass

    analog_switch.set_value = MagicMock()
    analog_switch.increment()

    assert analog_switch.set_value.called
    assert analog_switch.set_value.call_args.args == (0.6,)


async def test_sync_decrement(hass):
    """Test if sync decrement calls set_value with correct value."""
    analog_switch = MockAnalogSwitchEntity()
    analog_switch.hass = hass

    analog_switch.set_value = MagicMock()
    analog_switch.decrement()

    assert analog_switch.set_value.called
    assert analog_switch.set_value.call_args.args == (0.4,)
