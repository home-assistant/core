"""Template helper functions for Home Assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NoReturn

import voluptuous as vol

from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from .context import template_cv

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def raise_no_default(function: str, value: Any) -> NoReturn:
    """Raise ValueError when no default is specified for template functions."""
    template, action = template_cv.get() or ("", "rendering or compiling")
    raise ValueError(
        f"Template error: {function} got invalid input '{value}' when {action} template"
        f" '{template}' but no default was specified"
    )


def resolve_area_id(hass: HomeAssistant, lookup_value: Any) -> str | None:
    """Resolve lookup value to an area ID.

    Accepts area name, area alias, device ID, or entity ID.
    Returns the area ID or None if not found.
    """
    area_reg = ar.async_get(hass)
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    lookup_str = str(lookup_value)

    # Check if it's an area name
    if area := area_reg.async_get_area_by_name(lookup_str):
        return area.id

    # Check if it's an area alias
    areas_list = area_reg.async_get_areas_by_alias(lookup_str)
    if areas_list:
        return areas_list[0].id

    # Import here, not at top-level to avoid circular import
    from homeassistant.helpers import config_validation as cv  # noqa: PLC0415

    # Check if it's an entity ID
    try:
        cv.entity_id(lookup_value)
    except vol.Invalid:
        pass
    else:
        if entity := ent_reg.async_get(lookup_value):
            # If entity has an area ID, return that
            if entity.area_id:
                return entity.area_id
            # If entity has a device ID, return the area ID for the device
            if entity.device_id and (device := dev_reg.async_get(entity.device_id)):
                return device.area_id

    # Check if it's a device ID
    if device := dev_reg.async_get(lookup_value):
        return device.area_id

    return None
