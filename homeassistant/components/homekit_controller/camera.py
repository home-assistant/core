"""Support for Homekit cameras."""

import asyncio
from datetime import datetime
import logging
from typing import override

from aiohomekit.model import Accessory, Transport
from aiohomekit.model.services import ServicesTypes
from yarl import URL

from homeassistant.components.camera import (
    Camera,
    CameraEntityCapabilities,
    CameraEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType

from .connection import HKDevice
from .const import KNOWN_DEVICES
from .entity import AccessoryEntity

DEFAULT_IMAGE_WIDTH = 640
DEFAULT_IMAGE_HEIGHT = 480

_LOGGER = logging.getLogger(__name__)
# Seconds before each retry of an address update, the last repeating
_ADDRESS_RETRY_DELAYS = (5, 15, 30, 60, 300)


def _address(entry: ConfigEntry) -> tuple[str | None, int | None]:
    """Return the accessory's address, which discovery keeps up to date."""
    return entry.data.get("AccessoryIP"), entry.data.get("AccessoryPort")


class HomeKitCamera(AccessoryEntity, Camera):
    """Representation of a Homekit camera."""

    # content_type = "image/jpeg"

    def __init__(self, accessory: HKDevice, devinfo: ConfigType) -> None:
        """Initialise the camera."""
        super().__init__(accessory, devinfo)
        self._address = _address(accessory.config_entry)
        self._address_attempt = 0
        self._address_task: asyncio.Task[None] | None = None
        self._cancel_address_retry: CALLBACK_TYPE | None = None
        # go2rtc's homekit:// source streams from IP accessories with aid 1
        if accessory.pairing.transport is Transport.IP and self._aid == 1:
            self._attr_supported_features = CameraEntityFeature.STREAM
            # Cameras with a speaker play audio sent on the stream (talk-back)
            if accessory.entity_map.aid(self._aid).services.first(
                service_type=ServicesTypes.SPEAKER
            ):
                self._attr_camera_entity_capabilities = CameraEntityCapabilities(
                    two_way_audio=True
                )

    @override
    async def async_added_to_hass(self) -> None:
        """Follow address changes of a streaming camera."""
        await super().async_added_to_hass()
        if CameraEntityFeature.STREAM in self.supported_features:
            self.async_on_remove(
                self._accessory.config_entry.add_update_listener(
                    self._async_entry_updated
                )
            )
            self.async_on_remove(self._stop_address_update)

    async def _async_entry_updated(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Update go2rtc's stream when discovery changed the camera's address."""
        if _address(entry) == self._address:
            return
        self._address_attempt = 0
        self._start_address_update()

    @callback
    def _async_retry_address_update(self, _now: datetime) -> None:
        """Retry giving go2rtc the camera's new address."""
        self._cancel_address_retry = None
        self._start_address_update()

    @callback
    def _start_address_update(self) -> None:
        """Start an address update, in place of any earlier attempt."""
        self._stop_address_update()
        self._address_task = self.hass.async_create_task(
            self._async_update_address(), f"{self.entity_id} address update"
        )

    @callback
    def _stop_address_update(self) -> None:
        """Cancel a running or pending address update."""
        if self._cancel_address_retry:
            self._cancel_address_retry()
            self._cancel_address_retry = None
        if self._address_task:
            self._address_task.cancel()
            self._address_task = None

    async def _async_update_address(self) -> None:
        """Give go2rtc the camera's current address, retrying until it has it.

        HLS and recording keep reading go2rtc's restream without asking for it
        again, so its source must follow the address.
        """
        address = _address(self._accessory.config_entry)
        if (lock := self._create_stream_lock) and lock.locked():
            # A stream being created may have resolved the old address
            async with lock:
                pass
        if self.stream:
            try:
                await self.async_create_stream()
            except HomeAssistantError, TimeoutError:
                # Not logged, as the error can carry the source's credentials
                if not self._address_attempt:
                    _LOGGER.warning(
                        "Unable to update the stream of %s to its new address,"
                        " retrying",
                        self.entity_id,
                    )
                delay = _ADDRESS_RETRY_DELAYS[
                    min(self._address_attempt, len(_ADDRESS_RETRY_DELAYS) - 1)
                ]
                self._address_attempt += 1
                self._address_task = None
                self._cancel_address_retry = async_call_later(
                    self.hass, delay, self._async_retry_address_update
                )
                return
            if self._address_attempt:
                _LOGGER.info(
                    "Updated the stream of %s to its new address", self.entity_id
                )
        self._address = address
        self._address_attempt = 0
        self._address_task = None

    @override
    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return []

    @override
    async def webrtc_source(self) -> str | None:
        """Return a go2rtc homekit:// source for the camera's live stream.

        FFmpeg can't open it, so the camera has no stream_source. Its WebRTC
        provider (go2rtc) can, and can restream it for FFmpeg.
        """
        if CameraEntityFeature.STREAM not in self.supported_features:
            return None
        # Unlike HKDevice.pairing_data, the entry follows address changes
        data = self._accessory.config_entry.data
        return str(
            URL.build(
                scheme="homekit",
                host=data["AccessoryIP"],
                port=data["AccessoryPort"],
                query={
                    "device_id": data["AccessoryPairingID"],
                    "device_public": data["AccessoryLTPK"],
                    "client_id": data["iOSPairingId"],
                    # go2rtc expects the 64 byte Ed25519 private key form,
                    # which is the seed followed by the public key
                    "client_private": data["iOSDeviceLTSK"] + data["iOSDeviceLTPK"],
                },
            )
        )

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a jpeg with the current camera snapshot."""
        width = width or DEFAULT_IMAGE_WIDTH
        height = height or DEFAULT_IMAGE_HEIGHT
        pairing = self._accessory.pairing
        image: bytes | None = await pairing.image(self._aid, width, height)  # type: ignore[attr-defined]
        if image is None and (width, height) != (
            DEFAULT_IMAGE_WIDTH,
            DEFAULT_IMAGE_HEIGHT,
        ):
            # The requested size is only a hint and some accessories reject
            # sizes they do not support. Retry with the default size; the camera
            # component scales the result to the requested size if needed.
            image = await pairing.image(  # type: ignore[attr-defined]
                self._aid, DEFAULT_IMAGE_WIDTH, DEFAULT_IMAGE_HEIGHT
            )
        return image


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Homekit sensors."""
    hkid: str = config_entry.data["AccessoryPairingID"]
    conn: HKDevice = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_accessory(accessory: Accessory) -> bool:
        stream_mgmt = accessory.services.first(
            service_type=ServicesTypes.CAMERA_RTP_STREAM_MANAGEMENT
        )
        if not stream_mgmt:
            return False

        info = {"aid": accessory.aid, "iid": stream_mgmt.iid}
        entity = HomeKitCamera(conn, info)
        conn.async_migrate_unique_id(
            entity.old_unique_id, entity.unique_id, Platform.CAMERA
        )
        async_add_entities([entity])
        return True

    conn.add_accessory_factory(async_add_accessory)
