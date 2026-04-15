"""Template helper functions for Home Assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NoReturn, overload

import voluptuous as vol

from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

from .context import template_cv

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_SENTINEL = object()


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


@overload
def forgiving_boolean(value: Any) -> bool | object: ...


@overload
def forgiving_boolean[_T](value: Any, default: _T) -> bool | _T: ...


def forgiving_boolean[_T](
    value: Any, default: _T | object = _SENTINEL
) -> bool | _T | object:
    """Try to convert value to a boolean."""
    try:
        return cv.boolean(value)
    except vol.Invalid:
        if default is _SENTINEL:
            raise_no_default("bool", value)
        return default


def result_as_boolean(template_result: Any | None) -> bool:
    """Convert the template result to a boolean.

    True/not 0/'1'/'true'/'yes'/'on'/'enable' are considered truthy
    False/0/None/'0'/'false'/'no'/'off'/'disable' are considered falsy
    All other values are falsy
    """
    if template_result is None:
        return False

    return forgiving_boolean(template_result, default=False)
