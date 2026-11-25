"""Support for Homekit cameras."""

from typing import override

from aiohomekit.model import Accessory, Transport
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.characteristics.structs import SupportedVideoStreamConfiguration
from aiohomekit.model.services import ServicesTypes
from yarl import URL

from homeassistant.components.camera import (
    Camera,
    CameraEntityCapabilities,
    CameraEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .connection import HKDevice
from .const import KNOWN_DEVICES
from .entity import AccessoryEntity

DEFAULT_IMAGE_WIDTH = 640
DEFAULT_IMAGE_HEIGHT = 480


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
            # The address may have changed before the listener was added, while
            # the camera registered with its WebRTC provider
            await self._async_entry_updated(self.hass, self._accessory.config_entry)

    async def _async_entry_updated(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Pass a new address from discovery on to the WebRTC provider.

        HLS and recording keep reading the provider's restream without asking
        for it again, so the restream must follow the address.
        """
        if (address := _address(entry)) != self._address:
            self._address = address
            self.async_webrtc_source_changed()

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
        # Some accessories never answer a size they don't list, so the request
        # times out before the fallback below can run. Ask for a listed size;
        # the camera component scales the result to the requested size.
        if (sizes := self._listed_sizes()) and (width, height) not in sizes:
            width, height = _snapshot_size(sizes, width, height)
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

    def _listed_sizes(self) -> set[tuple[int, int]]:
        """Return the video sizes the camera lists for its streams."""
        sizes: set[tuple[int, int]] = set()
        for service in self.accessory.services.filter(
            service_type=ServicesTypes.CAMERA_RTP_STREAM_MANAGEMENT
        ):
            if not service.has(
                CharacteristicsTypes.SUPPORTED_VIDEO_STREAM_CONFIGURATION
            ):
                continue
            config = service[
                CharacteristicsTypes.SUPPORTED_VIDEO_STREAM_CONFIGURATION
            ].value
            if not isinstance(config, SupportedVideoStreamConfiguration):
                continue
            sizes.update(
                (attrs.width, attrs.height)
                for codec in config.config or ()
                for attrs in codec.video_attrs or ()
                if attrs.width and attrs.height
            )
        return sizes


def _snapshot_size(
    sizes: set[tuple[int, int]], width: int, height: int
) -> tuple[int, int]:
    """Return the smallest listed size in the camera's shape covering the request.

    The camera's shape is that of its largest size. Without a covering size,
    that largest size is used.
    """
    native_width, native_height = max(sizes, key=lambda size: size[0] * size[1])
    covering = [
        (size_width, size_height)
        for size_width, size_height in sizes
        if size_width * native_height == size_height * native_width
        and size_width >= width
        and size_height >= height
    ]
    if not covering:
        return native_width, native_height
    return min(covering, key=lambda size: size[0] * size[1])


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
