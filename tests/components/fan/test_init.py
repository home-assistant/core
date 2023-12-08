"""Tests for fan platforms."""
import pytest

from homeassistant.components.fan import (
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN,
    SERVICE_SET_PRESET_MODE,
    FanEntity,
    NotValidPresetModeError,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er
from homeassistant.setup import async_setup_component

from tests.testing_config.custom_components.test.fan import MockFan


class BaseFan(FanEntity):
    """Implementation of the abstract FanEntity."""

    def __init__(self):
        """Initialize the fan."""


def test_fanentity() -> None:
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


async def test_async_fanentity(hass: HomeAssistant) -> None:
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
    ("attribute_name", "attribute_value"),
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
def test_fanentity_attributes(attribute_name, attribute_value) -> None:
    """Test fan entity attribute shorthand."""
    fan = BaseFan()
    setattr(fan, f"_attr_{attribute_name}", attribute_value)
    assert getattr(fan, attribute_name) == attribute_value


async def test_preset_mode_validation(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    entity_registry: er.EntityRegistry,
    enable_custom_integrations: None,
) -> None:
    """Test preset mode validation."""

    await hass.async_block_till_done()

    platform = getattr(hass.components, "test.fan")
    platform.init(empty=False)

    assert await async_setup_component(hass, "fan", {"fan": {"platform": "test"}})
    await hass.async_block_till_done()

    test_fan: MockFan = platform.ENTITIES["support_preset_mode"]
    await hass.async_block_till_done()

    state = hass.states.get("fan.support_fan_with_preset_mode_support")
    assert state.attributes.get(ATTR_PRESET_MODES) == ["auto", "eco"]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            "entity_id": "fan.support_fan_with_preset_mode_support",
            "preset_mode": "eco",
        },
        blocking=True,
    )

    state = hass.states.get("fan.support_fan_with_preset_mode_support")
    assert state.attributes.get(ATTR_PRESET_MODE) == "eco"

    with pytest.raises(NotValidPresetModeError) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                "entity_id": "fan.support_fan_with_preset_mode_support",
                "preset_mode": "invalid",
            },
            blocking=True,
        )
        assert exc.value.translation_key == "not_valid_preset_mode"

    with pytest.raises(NotValidPresetModeError) as exc:
        await test_fan._valid_preset_mode_or_raise("invalid")
    assert exc.value.translation_key == "not_valid_preset_mode"
