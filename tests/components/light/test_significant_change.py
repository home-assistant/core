"""Test the Light significant change platform."""

from homeassistant.components.light import LightEntityStateAttribute
from homeassistant.components.light.significant_change import (
    async_check_significant_change,
)


async def test_significant_change() -> None:
    """Detect Light significant changes."""
    assert not async_check_significant_change(None, "on", {}, "on", {})
    assert async_check_significant_change(None, "on", {}, "off", {})

    # Brightness
    assert not async_check_significant_change(
        None,
        "on",
        {LightEntityStateAttribute.BRIGHTNESS: 60},
        "on",
        {LightEntityStateAttribute.BRIGHTNESS: 61},
    )
    assert async_check_significant_change(
        None,
        "on",
        {LightEntityStateAttribute.BRIGHTNESS: 60},
        "on",
        {LightEntityStateAttribute.BRIGHTNESS: 63},
    )

    # Color temp
    assert not async_check_significant_change(
        None,
        "on",
        {LightEntityStateAttribute.COLOR_TEMP_KELVIN: 2000},
        "on",
        {LightEntityStateAttribute.COLOR_TEMP_KELVIN: 2049},
    )
    assert async_check_significant_change(
        None,
        "on",
        {LightEntityStateAttribute.COLOR_TEMP_KELVIN: 2000},
        "on",
        {LightEntityStateAttribute.COLOR_TEMP_KELVIN: 2050},
    )

    # Effect
    for eff1, eff2, expected in (
        (None, None, False),
        (None, "colorloop", True),
        ("colorloop", None, True),
        ("colorloop", "jump", True),
        ("colorloop", "colorloop", False),
    ):
        result = async_check_significant_change(
            None,
            "on",
            {LightEntityStateAttribute.EFFECT: eff1},
            "on",
            {LightEntityStateAttribute.EFFECT: eff2},
        )
        assert result is expected

    # Hue
    assert not async_check_significant_change(
        None,
        "on",
        {LightEntityStateAttribute.HS_COLOR: [120, 20]},
        "on",
        {LightEntityStateAttribute.HS_COLOR: [124, 20]},
    )
    assert async_check_significant_change(
        None,
        "on",
        {LightEntityStateAttribute.HS_COLOR: [120, 20]},
        "on",
        {LightEntityStateAttribute.HS_COLOR: [125, 20]},
    )

    # Satursation
    assert not async_check_significant_change(
        None,
        "on",
        {LightEntityStateAttribute.HS_COLOR: [120, 20]},
        "on",
        {LightEntityStateAttribute.HS_COLOR: [120, 22]},
    )
    assert async_check_significant_change(
        None,
        "on",
        {LightEntityStateAttribute.HS_COLOR: [120, 20]},
        "on",
        {LightEntityStateAttribute.HS_COLOR: [120, 23]},
    )
