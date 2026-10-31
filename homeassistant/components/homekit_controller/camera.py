"""Support for Homekit cameras."""

from typing import override

from aiohomekit.model import Accessory
from aiohomekit.model.services import ServicesTypes

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .connection import HKDevice
from .const import KNOWN_DEVICES
from .entity import AccessoryEntity

DEFAULT_IMAGE_WIDTH = 640
DEFAULT_IMAGE_HEIGHT = 480


class HomeKitCamera(AccessoryEntity, Camera):
    """Representation of a Homekit camera."""

    # content_type = "image/jpeg"

    @override
    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return []

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
