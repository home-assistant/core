"""Helper to test significant NEW_NAME state changes."""

from typing import Any

from homeassistant.const import EntityStateAttribute
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
    device_class = new_attrs.get(EntityStateAttribute.DEVICE_CLASS)

    if device_class is None:
        return None

    return None
