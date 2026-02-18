"""Support for OpenDisplay image entities."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import timedelta
import logging
from pathlib import Path
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
    prepare_image,
)
from PIL import Image as PILImage

from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_register_callback,
)
from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.image import ImageEntity
from homeassistant.components.media_source import async_resolve_media
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.network import get_url
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from . import OpenDisplayConfigEntry
from .const import CANCEL_SETTLE_DELAY, DOMAIN, STORAGE_DIR
from .entity import (
    OpenDisplayEntity,
    OpenDisplayImageExtraStoredData,
    delete_stored_image,
    image_to_bytes,
    load_image,
    load_image_from_bytes,
    read_stored_image,
    write_stored_image,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenDisplayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenDisplay image entities."""
    async_add_entities([OpenDisplayImageEntity(hass, entry)])


class OpenDisplayImageEntity(OpenDisplayEntity, ImageEntity, RestoreEntity):
    """Input entity for an OpenDisplay e-paper display.

    Acts as an input entity: setting an image updates the entity state
    immediately (with a processed/dithered preview), then syncs to the
    physical display via BLE in the background.
    """

    _attr_content_type = "image/png"

    def __init__(self, hass: HomeAssistant, entry: OpenDisplayConfigEntry) -> None:
        """Initialize the image entity."""
        OpenDisplayEntity.__init__(self, entry)
        ImageEntity.__init__(self, hass)
        self._entry = entry
        self._current_image: bytes | None = None
        self._upload_task: asyncio.Task[None] | None = None
        self._pending_upload: (
            tuple[tuple[bytes, bytes | None, PILImage.Image], RefreshMode] | None
        ) = None

    def _get_storage_path(self) -> Path:
        """Return the path for storing the image on disk."""
        return Path(
            self.hass.config.path(".storage", STORAGE_DIR, f"{self._address}.png")
        )

    async def async_added_to_hass(self) -> None:
        """Restore the last image state on startup."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_register_callback(
                self.hass,
                self._async_on_device_seen,
                BluetoothCallbackMatcher(address=self._address, connectable=True),
                BluetoothScanningMode.PASSIVE,
            )
        )

        if (extra_data := await self.async_get_last_extra_data()) is None:
            return

        restored = OpenDisplayImageExtraStoredData.from_dict(extra_data.as_dict())
        if restored is None:
            return

        if restored.image_last_updated:
            self._attr_image_last_updated = dt_util.parse_datetime(
                restored.image_last_updated
            )

        if restored.has_stored_image:
            self._current_image = await self.hass.async_add_executor_job(
                read_stored_image, self._get_storage_path()
            )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up stored image file on entity removal."""
        await self.hass.async_add_executor_job(
            delete_stored_image, self._get_storage_path()
        )

    @property
    def extra_restore_state_data(self) -> OpenDisplayImageExtraStoredData:
        """Return entity-specific state data to be restored."""
        return OpenDisplayImageExtraStoredData(
            image_last_updated=(
                self._attr_image_last_updated.isoformat()
                if self._attr_image_last_updated
                else None
            ),
            has_stored_image=self._current_image is not None,
        )

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return self._current_image

    async def async_upload_image(self, **kwargs: Any) -> None:
        """Handle the upload_image entity service call.

        Phase 1: Resolve media, process image offline, update entity state.
        Phase 2: Upload to the device via BLE in a background task.
        """
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
                load_image, str(media.path)
            )
        else:
            pil_image = await self._async_download_and_load_image(media.url)

        # Phase 1: Process image offline (no BLE needed)
        prepared_data = await self.hass.async_add_executor_job(
            prepare_image,
            pil_image,
            self._entry.runtime_data.device_config,
            None,  # capabilities (extracted from config)
            True,  # use_measured_palettes
            None,  # panel_ic_type (extracted from config)
            dither_mode,
            True,  # compress
            tone_compression,
            fit_mode,
            rotation,
        )

        # Update entity state immediately with processed preview
        _, _, processed_image = prepared_data
        image_bytes = await self.hass.async_add_executor_job(
            image_to_bytes, processed_image
        )
        self._current_image = image_bytes
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

        # Persist to disk for restoration after restart
        try:
            await self.hass.async_add_executor_job(
                write_stored_image, self._get_storage_path(), image_bytes
            )
        except OSError:
            _LOGGER.warning("Failed to persist image to storage")

        # Track the prepared data for automatic retry on BLE failure
        self._pending_upload = (prepared_data, refresh_mode)

        # Cancel any in-flight upload before starting the new one
        if self._upload_task and not self._upload_task.done():
            self._upload_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._upload_task
            # Brief delay to let the device reset after BLE disconnect
            await asyncio.sleep(CANCEL_SETTLE_DELAY)

        # Phase 2: Upload to the device via BLE in the background
        self._upload_task = self._entry.async_create_background_task(
            self.hass,
            self._async_ble_upload(prepared_data, refresh_mode),
            f"opendisplay_upload_{self._address}",
        )

    async def _async_ble_upload(
        self,
        prepared_data: tuple[bytes, bytes | None, PILImage.Image],
        refresh_mode: RefreshMode,
    ) -> None:
        """Upload pre-processed image to device via BLE."""
        ble_device = async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        if ble_device is None:
            _LOGGER.debug(
                "BLE device %s not in range, will retry when device is seen",
                self._address,
            )
            return

        try:
            async with OpenDisplayDevice(
                mac_address=self._address,
                ble_device=ble_device,
                config=self._entry.runtime_data.device_config,
            ) as device:
                await device.upload_prepared_image(
                    prepared_data, refresh_mode=refresh_mode
                )
            self._pending_upload = None
        except (BLEConnectionError, BLETimeoutError) as err:
            _LOGGER.warning(
                "Failed to sync image to %s, will retry when device is seen: %s",
                self._address,
                err,
            )
        except OpenDisplayError as err:
            _LOGGER.warning(
                "Upload error for %s, will retry when device is seen: %s",
                self._address,
                err,
            )

    @callback
    def _async_on_device_seen(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Retry a pending upload when the device becomes connectable."""
        if self._pending_upload is None:
            return
        if self._upload_task and not self._upload_task.done():
            return
        prepared_data, refresh_mode = self._pending_upload
        self._upload_task = self._entry.async_create_background_task(
            self.hass,
            self._async_ble_upload(prepared_data, refresh_mode),
            f"opendisplay_upload_{self._address}",
        )

    async def _async_download_and_load_image(self, url: str) -> PILImage.Image:
        """Download an image from a HA internal URL and return a PIL Image."""
        signed_path = async_sign_path(
            self.hass, url, timedelta(minutes=1), use_content_user=True
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
        return await self.hass.async_add_executor_job(load_image_from_bytes, data)
