"""Support for OpenDisplay image entities."""

from __future__ import annotations

from datetime import timedelta
import io
from typing import Any

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

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.image import ImageEntity
from homeassistant.components.media_source import async_resolve_media
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.network import get_url
from homeassistant.util import dt as dt_util

from . import OpenDisplayConfigEntry
from .const import DOMAIN
from .entity import OpenDisplayEntity


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


def _image_to_bytes(image: PILImage.Image) -> bytes:
    """Convert a PIL Image to PNG bytes."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenDisplayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenDisplay image entities."""
    async_add_entities([OpenDisplayImageEntity(hass, entry)])


class OpenDisplayImageEntity(OpenDisplayEntity, ImageEntity):
    """Representation of an OpenDisplay e-paper display."""

    _attr_content_type = "image/png"

    def __init__(self, hass: HomeAssistant, entry: OpenDisplayConfigEntry) -> None:
        """Initialize the image entity."""
        OpenDisplayEntity.__init__(self, entry)
        ImageEntity.__init__(self, hass)
        self._entry = entry
        self._current_image: bytes | None = None

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return self._current_image

    async def async_upload_image(self, **kwargs: Any) -> None:
        """Handle the upload_image entity service call."""
        image_data: dict = kwargs["image"]
        rotation: Rotation = kwargs.get("rotation", Rotation.ROTATE_0)
        dither_mode: DitherMode = kwargs.get("dither_mode", DitherMode.BURKES)
        refresh_mode: RefreshMode = kwargs.get("refresh_mode", RefreshMode.FULL)
        fit_mode: FitMode = kwargs.get("fit_mode", FitMode.CONTAIN)
        tone_compression: float | str = kwargs.get("tone_compression", "auto")

        # Resolve media source
        source_media_id = image_data["media_content_id"]
        media = await async_resolve_media(self.hass, source_media_id, None)

        # Load image from a local path or a remote URL
        if media.path is not None:
            pil_image = await self.hass.async_add_executor_job(
                _load_image, str(media.path)
            )
        else:
            pil_image = await self._async_download_and_load_image(media.url)

        # Resolve BLE device
        ble_device = async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        if ble_device is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={"address": self._address},
            )

        # Upload to the device
        try:
            async with OpenDisplayDevice(
                mac_address=self._address,
                ble_device=ble_device,
                use_measured_palettes=True,
                config=self._entry.runtime_data.device_config,
            ) as device:
                processed_image = await device.upload_image(
                    pil_image,
                    refresh_mode=refresh_mode,
                    rotate=rotation,
                    dither_mode=dither_mode,
                    fit=fit_mode,
                    tone_compression=tone_compression,
                )
        except (BLEConnectionError, BLETimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except OpenDisplayError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="upload_error",
                translation_placeholders={"error": str(err)},
            ) from err

        # Store processed image as a preview
        image_bytes = await self.hass.async_add_executor_job(
            _image_to_bytes, processed_image
        )
        self._current_image = image_bytes
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    async def _async_download_and_load_image(self, url: str) -> PILImage.Image:
        """Download an image from a HA internal URL and return a PIL Image."""
        signed_path = async_sign_path(
            self.hass, url, timedelta(minutes=5), use_content_user=True
        )
        full_url = get_url(self.hass) + signed_path
        session = async_get_clientsession(self.hass, verify_ssl=False)

        try:
            resp = await session.get(full_url)
            resp.raise_for_status()
        except Exception as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="media_download_error",
                translation_placeholders={"error": str(err)},
            ) from err

        data = await resp.read()
        return await self.hass.async_add_executor_job(_load_image_from_bytes, data)
