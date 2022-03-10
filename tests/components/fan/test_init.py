"""Tests for fan platforms."""

import pytest

from homeassistant.components.fan import FanEntity


class BaseFan(FanEntity):
    """Implementation of the abstract FanEntity."""

    def __init__(self):
        """Initialize the fan."""


def test_fanentity():
    """Test fan entity methods."""
    fan = BaseFan()
    assert fan.state == "off"
    assert fan.preset_modes is None
    assert fan.supported_features == 0
    assert fan.percentage_step == 1
    assert fan.speed_count == 100
    assert fan.capability_attributes == {}
    # Test set_speed not required
    with pytest.raises(NotImplementedError):
        fan.oscillate(True)
    with pytest.raises(AttributeError):
        fan.set_speed("low")
    with pytest.raises(NotImplementedError):
        fan.set_percentage(0)
    with pytest.raises(NotImplementedError):
        fan.set_preset_mode("auto")
    with pytest.raises(NotImplementedError):
        fan.turn_on()
    with pytest.raises(NotImplementedError):
        fan.turn_off()


async def test_async_fanentity(hass):
    """Test async fan entity methods."""
    fan = BaseFan()
    fan.hass = hass
    assert fan.state == "off"
    assert fan.preset_modes is None
    assert fan.supported_features == 0
    assert fan.percentage_step == 1
    assert fan.speed_count == 100
    assert fan.capability_attributes == {}
    # Test set_speed not required
    with pytest.raises(NotImplementedError):
        await fan.async_oscillate(True)
    with pytest.raises(AttributeError):
        await fan.async_set_speed("low")
    with pytest.raises(NotImplementedError):
        await fan.async_set_percentage(0)
    with pytest.raises(NotImplementedError):
        await fan.async_set_preset_mode("auto")
    with pytest.raises(NotImplementedError):
        await fan.async_turn_on()
    with pytest.raises(NotImplementedError):
        await fan.async_turn_off()
    with pytest.raises(NotImplementedError):
        await fan.async_increase_speed()
    with pytest.raises(NotImplementedError):
        await fan.async_decrease_speed()


@pytest.mark.parametrize(
    "attribute_name, attribute_value",
    [
        ("current_direction", "forward"),
        ("oscillating", True),
        ("percentage", 50),
        ("preset_mode", "medium"),
        ("preset_modes", ["low", "medium", "high"]),
        ("speed_count", 50),
        ("supported_features", 1),
    ],
)
def test_fanentity_attributes(attribute_name, attribute_value):
    """Test fan entity attribute shorthand."""
    fan = BaseFan()
    setattr(fan, f"_attr_{attribute_name}", attribute_value)
    assert getattr(fan, attribute_name) == attribute_value
