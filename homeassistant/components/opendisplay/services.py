"""Service registration for the OpenDisplay integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from enum import IntEnum
import io
from typing import TYPE_CHECKING, Any

import aiohttp
from opendisplay import (
    BLEConnectionError,
    BLETimeoutError,
    DitherMode,
    FitMode,
    OpenDisplayDevice,
    OpenDisplayError,
    RefreshMode,
    Rotation,
)
from PIL import Image as PILImage, ImageOps
import voluptuous as vol

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.media_source import async_resolve_media
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url
from homeassistant.helpers.selector import MediaSelector, MediaSelectorConfig

if TYPE_CHECKING:
    from . import OpenDisplayConfigEntry

from .const import DOMAIN


def _str_to_enum(enum_class: type[IntEnum]) -> Callable[[str], Any]:
    """Return a validator that converts a lowercase enum name string to an enum member."""
    members = {m.name.lower(): m for m in enum_class}

    def validate(value: str) -> IntEnum:
        if (result := members.get(value)) is None:
            raise vol.Invalid(f"Invalid value: {value}")
        return result

    return validate


SCHEMA_UPLOAD_IMAGE = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
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
)


def _get_entry_for_device(call: ServiceCall) -> OpenDisplayConfigEntry:
    """Return the config entry for the device targeted by a service call."""
    device_id: str = call.data[ATTR_DEVICE_ID]
    device_registry = dr.async_get(call.hass)

    if (device := device_registry.async_get(device_id)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device_id",
            translation_placeholders={"device_id": device_id},
        )

    mac_address = next(
        (ident[1] for ident in device.identifiers if ident[0] == DOMAIN), None
    )
    entry: OpenDisplayConfigEntry | None = (
        call.hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, mac_address)
        if mac_address is not None
        else None
    )

    if entry is None or entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"device_id": device_id},
        )

    return entry


def _load_image(path: str) -> PILImage.Image:
    """Load an image from disk and apply EXIF orientation."""
    image = PILImage.open(path)
    image.load()
    return ImageOps.exif_transpose(image)


def _load_image_from_bytes(data: bytes) -> PILImage.Image:
    """Load an image from bytes and apply EXIF orientation."""
    image = PILImage.open(io.BytesIO(data))
    image.load()
    return ImageOps.exif_transpose(image)


async def _async_download_image(hass: HomeAssistant, url: str) -> PILImage.Image:
    """Download an image from a URL and return a PIL Image."""
    if not url.startswith(("http://", "https://")):
        url = get_url(hass) + async_sign_path(
            hass, url, timedelta(minutes=5), use_content_user=True
        )
    session = async_get_clientsession(hass, verify_ssl=False)
    try:
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.read()
    except aiohttp.ClientError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="media_download_error",
            translation_placeholders={"error": str(err)},
        ) from err

    return await hass.async_add_executor_job(_load_image_from_bytes, data)


async def _async_upload_image(call: ServiceCall) -> None:
    """Handle the upload_image service call."""
    entry = _get_entry_for_device(call)
    address = entry.unique_id
    assert address is not None

    image_data: dict[str, Any] = call.data["image"]
    rotation: Rotation = call.data.get("rotation", Rotation.ROTATE_0)
    dither_mode: DitherMode = call.data.get("dither_mode", DitherMode.BURKES)
    refresh_mode: RefreshMode = call.data.get("refresh_mode", RefreshMode.FULL)
    fit_mode: FitMode = call.data.get("fit_mode", FitMode.CONTAIN)
    tone_compression: float | str = call.data.get("tone_compression", "auto")

    ble_device = async_ble_device_from_address(call.hass, address, connectable=True)
    if ble_device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"device_id": call.data[ATTR_DEVICE_ID]},
        )

    media = await async_resolve_media(call.hass, image_data["media_content_id"], None)

    if media.path is not None:
        pil_image = await call.hass.async_add_executor_job(_load_image, str(media.path))
    else:
        pil_image = await _async_download_image(call.hass, media.url)

    try:
        async with OpenDisplayDevice(
            mac_address=address,
            ble_device=ble_device,
            config=entry.runtime_data.device_config,
        ) as device:
            await device.upload_image(
                pil_image,
                refresh_mode=refresh_mode,
                dither_mode=dither_mode,
                tone_compression=tone_compression,
                fit=fit_mode,
                rotate=rotation,
            )
    except (BLEConnectionError, BLETimeoutError, OpenDisplayError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="upload_error",
            translation_placeholders={"error": str(err)},
        ) from err


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register OpenDisplay services."""
    hass.services.async_register(
        DOMAIN,
        "upload_image",
        _async_upload_image,
        schema=SCHEMA_UPLOAD_IMAGE,
    )
