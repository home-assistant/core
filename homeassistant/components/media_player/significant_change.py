"""Helper to test significant Media Player state changes."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.significant_change import (
    check_absolute_change,
    check_valid_float,
)

from . import (
    ATTR_ENTITY_PICTURE_LOCAL,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_TO_PROPERTY,
)

INSIGNIFICANT_ATTRIBUTES: set[str] = {
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
}

SIGNIFICANT_ATTRIBUTES: set[str] = {
    ATTR_ENTITY_PICTURE_LOCAL,
    *ATTR_TO_PROPERTY,
} - INSIGNIFICANT_ATTRIBUTES


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
    changed_attrs: set[str] = {item[0] for item in old_attrs_s ^ new_attrs_s}

    for attr_name in changed_attrs:
        if attr_name != ATTR_MEDIA_VOLUME_LEVEL:
            return True

        old_attr_value = old_attrs.get(attr_name)
        new_attr_value = new_attrs.get(attr_name)
        if new_attr_value is None or not check_valid_float(new_attr_value):
            # New attribute value is invalid, ignore it
            continue

        if old_attr_value is None or not check_valid_float(old_attr_value):
            # Old attribute value was invalid, we should report again
            return True

        if check_absolute_change(old_attr_value, new_attr_value, 0.1):
            return True

    # no significant attribute change detected
    return False
