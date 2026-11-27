"""Helper to test significant Media Player state changes."""

from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.significant_change import (
    check_absolute_change,
    check_valid_float,
)

from .const import MediaPlayerEntityStateAttribute
from .entity import PROP_TO_ATTR

INSIGNIFICANT_ATTRIBUTES: set[MediaPlayerEntityStateAttribute] = {
    MediaPlayerEntityStateAttribute.MEDIA_POSITION,
    MediaPlayerEntityStateAttribute.MEDIA_POSITION_UPDATED_AT,
}

SIGNIFICANT_ATTRIBUTES: set[MediaPlayerEntityStateAttribute] = {
    MediaPlayerEntityStateAttribute.ENTITY_PICTURE_LOCAL,
    *PROP_TO_ATTR.values(),
} - INSIGNIFICANT_ATTRIBUTES

_MISSING = object()


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

    # Compare by equality, as values can be unhashable (a dict media_content_id)
    changed_attrs: set[str] = {
        attr_name
        for attr_name in (old_attrs.keys() | new_attrs.keys()) & SIGNIFICANT_ATTRIBUTES
        if old_attrs.get(attr_name, _MISSING) != new_attrs.get(attr_name, _MISSING)
    }

    for attr_name in changed_attrs:
        if attr_name != MediaPlayerEntityStateAttribute.MEDIA_VOLUME_LEVEL:
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
