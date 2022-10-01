"""Test the Light significant change platform."""
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
)
from homeassistant.components.light.significant_change import (
    async_check_significant_change,
)


async def test_significant_change():
    """Detect Light significant changes."""
    assert not async_check_significant_change(None, "on", {}, "on", {})
    assert async_check_significant_change(None, "on", {}, "off", {})

    # Brightness
    assert not async_check_significant_change(
        None, "on", {ATTR_BRIGHTNESS: 60}, "on", {ATTR_BRIGHTNESS: 61}
    )
    assert async_check_significant_change(
        None, "on", {ATTR_BRIGHTNESS: 60}, "on", {ATTR_BRIGHTNESS: 63}
    )

    # Color temp
    assert not async_check_significant_change(
        None, "on", {ATTR_COLOR_TEMP: 60}, "on", {ATTR_COLOR_TEMP: 64}
    )
    assert async_check_significant_change(
        None, "on", {ATTR_COLOR_TEMP: 60}, "on", {ATTR_COLOR_TEMP: 65}
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
            None, "on", {ATTR_EFFECT: eff1}, "on", {ATTR_EFFECT: eff2}
        )
        assert result is expected

    # Hue
    assert not async_check_significant_change(
        None, "on", {ATTR_HS_COLOR: [120, 20]}, "on", {ATTR_HS_COLOR: [124, 20]}
    )
    assert async_check_significant_change(
        None, "on", {ATTR_HS_COLOR: [120, 20]}, "on", {ATTR_HS_COLOR: [125, 20]}
    )

    # Satursation
    assert not async_check_significant_change(
        None, "on", {ATTR_HS_COLOR: [120, 20]}, "on", {ATTR_HS_COLOR: [120, 22]}
    )
    assert async_check_significant_change(
        None, "on", {ATTR_HS_COLOR: [120, 20]}, "on", {ATTR_HS_COLOR: [120, 23]}
    )
