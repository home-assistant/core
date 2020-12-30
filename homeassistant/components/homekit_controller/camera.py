"""Support for Homekit cameras."""
from aiohomekit.model.services import ServicesTypes

from homeassistant.components.camera import Camera
from homeassistant.core import callback

from . import KNOWN_DEVICES, AccessoryEntity


class HomeKitCamera(AccessoryEntity, Camera):
    """Representation of a Homekit camera."""

    # content_type = "image/jpeg"

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return []

    @property
    def state(self):
        """Return the current state of the camera."""
        return "idle"

    async def async_camera_image(self):
        """Return a jpeg with the current camera snapshot."""
        return await self._accessory.pairing.image(
            self._aid,
            640,
            480,
        )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit sensors."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_accessory(accessory):
        stream_mgmt = accessory.services.first(
            service_type=ServicesTypes.CAMERA_RTP_STREAM_MANAGEMENT
        )
        if not stream_mgmt:
            return

        info = {"aid": accessory.aid, "iid": stream_mgmt.iid}
        async_add_entities([HomeKitCamera(conn, info)], True)
        return True

    conn.add_accessory_factory(async_add_accessory)
