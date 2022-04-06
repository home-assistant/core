"""Helper to test significant update state changes."""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, callback

from .const import ATTR_INSTALLED_VERSION, ATTR_LATEST_VERSION


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

    if old_attrs.get(ATTR_INSTALLED_VERSION) != new_attrs.get(ATTR_INSTALLED_VERSION):
        return True

    if old_attrs.get(ATTR_LATEST_VERSION) != new_attrs.get(ATTR_LATEST_VERSION):
        return True

    return False
