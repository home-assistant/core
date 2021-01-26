"""Helper to test significant NEW_NAME state changes."""
from typing import Any, Optional

from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant


async def async_check_significant_change(
    hass: HomeAssistant,
    old_state: str,
    old_attrs: dict,
    new_state: str,
    new_attrs: dict,
    **kwargs: Any,
) -> Optional[bool]:
    """Test if state significantly changed."""
    device_class = new_attrs.get(ATTR_DEVICE_CLASS)

    if device_class is None:
        return None

    return None
