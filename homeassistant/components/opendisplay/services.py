"""Service registration for the OpenDisplay integration."""

from __future__ import annotations

from collections.abc import Callable
from enum import IntEnum
from typing import Any

from opendisplay import DitherMode, FitMode, RefreshMode, Rotation
import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service
from homeassistant.helpers.selector import MediaSelector, MediaSelectorConfig
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN


def _str_to_enum(enum_class: type[IntEnum]) -> Callable[[str], Any]:
    """Return a validator that converts a lowercase enum name string to an enum member."""
    members = {m.name.lower(): m for m in enum_class}

    def validate(value: str) -> IntEnum:
        if (result := members.get(value)) is None:
            raise vol.Invalid(f"Invalid value: {value}")
        return result

    return validate


SCHEMA_UPLOAD_IMAGE: VolDictType = {
    vol.Required("image"): MediaSelector(MediaSelectorConfig(accept=["image/*"])),
    vol.Optional("rotation", default=Rotation.ROTATE_0): vol.All(
        vol.Coerce(int), vol.Coerce(Rotation)
    ),
    vol.Optional("dither_mode", default="burkes"): _str_to_enum(DitherMode),
    vol.Optional("refresh_mode", default="full"): _str_to_enum(RefreshMode),
    vol.Optional("fit_mode", default="contain"): _str_to_enum(FitMode),
    vol.Optional("tone_compression"): vol.All(
        vol.Coerce(float), vol.Range(min=0.0, max=1.0)
    ),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register OpenDisplay services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "upload_image",
        entity_domain="image",
        schema=SCHEMA_UPLOAD_IMAGE,
        func="async_upload_image",
    )
