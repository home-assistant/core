"""Helper to test significant Switch state changes."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, callback


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
    return old_state != new_state
