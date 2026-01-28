"""Helper to test significant Vacuum state changes."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, callback

from . import ATTR_FAN_SPEED

SIGNIFICANT_ATTRIBUTES: set[str] = {
    ATTR_FAN_SPEED,
}


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

    old_attrs_s = set(
        {k: v for k, v in old_attrs.items() if k in SIGNIFICANT_ATTRIBUTES}.items()
    )
    new_attrs_s = set(
        {k: v for k, v in new_attrs.items() if k in SIGNIFICANT_ATTRIBUTES}.items()
    )
    return any(old_attrs_s ^ new_attrs_s)
