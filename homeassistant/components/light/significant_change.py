"""Helper to test significant Light state changes."""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.significant_change import check_absolute_change

from . import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
)


@callback
def async_check_significant_change(
    hass: HomeAssistant,
    old_state: str,
    old_attrs: dict,
    new_state: str,
    new_attrs: dict,
    **kwargs: Any,
) -> bool | None:
    """Test if state significantly changed."""
    if old_state != new_state:
        return True

    if old_attrs.get(ATTR_EFFECT) != new_attrs.get(ATTR_EFFECT):
        return True

    old_color = old_attrs.get(ATTR_HS_COLOR)
    new_color = new_attrs.get(ATTR_HS_COLOR)

    if old_color and new_color:
        # Range 0..360
        if check_absolute_change(old_color[0], new_color[0], 5):
            return True

        # Range 0..100
        if check_absolute_change(old_color[1], new_color[1], 3):
            return True

    if check_absolute_change(
        old_attrs.get(ATTR_BRIGHTNESS), new_attrs.get(ATTR_BRIGHTNESS), 3
    ):
        return True

    if check_absolute_change(
        # Default range 153..500
        old_attrs.get(ATTR_COLOR_TEMP),
        new_attrs.get(ATTR_COLOR_TEMP),
        5,
    ):
        return True

    if check_absolute_change(
        # Range 0..255
        old_attrs.get(ATTR_WHITE_VALUE),
        new_attrs.get(ATTR_WHITE_VALUE),
        5,
    ):
        return True

    return False
