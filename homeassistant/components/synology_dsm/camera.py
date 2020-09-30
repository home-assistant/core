"""Support for Synology DSM cameras."""
from typing import Dict

from synology_dsm.api.surveillance_station import SynoSurveillanceStation

from homeassistant.components.camera import SUPPORT_STREAM, Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import SynologyDSMEntity
from .const import (
    DOMAIN,
    ENTITY_CLASS,
    ENTITY_ENABLE,
    ENTITY_ICON,
    ENTITY_NAME,
    ENTITY_UNIT,
    SYNO_API,
)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Synology NAS binary sensor."""

    api = hass.data[DOMAIN][entry.unique_id][SYNO_API]

    if SynoSurveillanceStation.CAMERA_API_KEY not in api.dsm.apis:
        return

    surveillance_station = api.surveillance_station
    await hass.async_add_executor_job(surveillance_station.update)
    cameras = surveillance_station.get_all_cameras()
    entities = [SynoDSMCamera(api, camera) for camera in cameras]

    async_add_entities(entities)


class SynoDSMCamera(SynologyDSMEntity, Camera):
    """Representation a Synology camera."""

    def __init__(self, api, camera):
        """Initialize a Synology camera."""
        super().__init__(
            api,
            f"{SynoSurveillanceStation.CAMERA_API_KEY}:{camera.id}",
            {
                ENTITY_NAME: camera.name,
                ENTITY_CLASS: None,
                ENTITY_ICON: None,
                ENTITY_ENABLE: True,
                ENTITY_UNIT: None,
            },
        )
        self._camera = camera

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self._api.information.serial, self._camera.id)},
            "name": self._camera.name,
            "model": self._camera.model,
            "via_device": (
                DOMAIN,
                self._api.information.serial,
                SynoSurveillanceStation.INFO_API_KEY,
            ),
        }

    @property
    def supported_features(self) -> int:
        """Return supported features of this camera."""
        return SUPPORT_STREAM

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self._camera.is_recording

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return self._camera.is_motion_detection_enabled

    def camera_image(self) -> bytes:
        """Return bytes of camera image."""
        return self._api.surveillance_station.get_camera_image(self._camera.id)

    async def stream_source(self) -> str:
        """Return the source of the stream."""
        return self._camera.live_view.rtsp

    def enable_motion_detection(self):
        """Enable motion detection in the camera."""
        self._api.surveillance_station.enable_motion_detection(self._camera.id)

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        self._api.surveillance_station.disable_motion_detection(self._camera.id)
