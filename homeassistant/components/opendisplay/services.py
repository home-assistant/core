"""Service registration for the OpenDisplay integration."""

from __future__ import annotations

from opendisplay import DitherMode, FitMode, RefreshMode, Rotation
import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service
from homeassistant.helpers.selector import MediaSelector, MediaSelectorConfig
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN

SCHEMA_UPLOAD_IMAGE: VolDictType = {
    vol.Required("image"): MediaSelector(MediaSelectorConfig(accept=["image/*"])),
    vol.Optional("rotation", default=Rotation.ROTATE_0): vol.All(
        vol.Coerce(int), vol.Coerce(Rotation)
    ),
    vol.Optional("dither_mode", default=DitherMode.BURKES): vol.All(
        vol.Coerce(int), vol.Coerce(DitherMode)
    ),
    vol.Optional("refresh_mode", default=RefreshMode.FULL): vol.All(
        vol.Coerce(int), vol.Coerce(RefreshMode)
    ),
    vol.Optional("fit_mode", default=FitMode.CONTAIN): vol.All(
        vol.Coerce(int), vol.Coerce(FitMode)
    ),
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
