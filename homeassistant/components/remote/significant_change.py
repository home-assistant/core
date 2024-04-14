"""Helper to test significant Remote state changes."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, callback

from . import ATTR_CURRENT_ACTIVITY


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

    if old_attrs.get(ATTR_CURRENT_ACTIVITY) != new_attrs.get(ATTR_CURRENT_ACTIVITY):
        return True

    return False
