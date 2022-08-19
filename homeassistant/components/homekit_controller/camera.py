"""Support for Homekit cameras."""
from __future__ import annotations

from aiohomekit.model import Accessory
from aiohomekit.model.services import ServicesTypes

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KNOWN_DEVICES
from .entity import AccessoryEntity


class HomeKitCamera(AccessoryEntity, Camera):
    """Representation of a Homekit camera."""

    # content_type = "image/jpeg"

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return []

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a jpeg with the current camera snapshot."""
        return await self._accessory.pairing.image(  # type: ignore[attr-defined]
            self._aid,
            width or 640,
            height or 480,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit sensors."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_accessory(accessory: Accessory) -> bool:
        stream_mgmt = accessory.services.first(
            service_type=ServicesTypes.CAMERA_RTP_STREAM_MANAGEMENT
        )
        if not stream_mgmt:
            return False

        info = {"aid": accessory.aid, "iid": stream_mgmt.iid}
        async_add_entities([HomeKitCamera(conn, info)], True)
        return True

    conn.add_accessory_factory(async_add_accessory)
