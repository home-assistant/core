"""Support for Synology DSM cameras."""
from __future__ import annotations

import logging

from synology_dsm.api.surveillance_station import SynoCamera, SynoSurveillanceStation
from synology_dsm.exceptions import (
    SynologyDSMAPIErrorException,
    SynologyDSMRequestException,
)

from homeassistant.components.camera import SUPPORT_STREAM, Camera
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import SynoApi, SynologyDSMBaseEntity
from .const import COORDINATOR_CAMERAS, DOMAIN, ENTITY_ENABLE, SYNO_API

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Synology NAS cameras."""

    data = hass.data[DOMAIN][entry.unique_id]
    api: SynoApi = data[SYNO_API]

    if SynoSurveillanceStation.CAMERA_API_KEY not in api.dsm.apis:
        return

    # initial data fetch
    coordinator: DataUpdateCoordinator[dict[str, dict[str, SynoCamera]]] = data[
        COORDINATOR_CAMERAS
    ]
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        SynoDSMCamera(api, coordinator, camera_id)
        for camera_id in coordinator.data["cameras"]
    )


class SynoDSMCamera(SynologyDSMBaseEntity, Camera):
    """Representation a Synology camera."""

    coordinator: DataUpdateCoordinator[dict[str, dict[str, SynoCamera]]]

    def __init__(
        self,
        api: SynoApi,
        coordinator: DataUpdateCoordinator[dict[str, dict[str, SynoCamera]]],
        camera_id: str,
    ) -> None:
        """Initialize a Synology camera."""
        super().__init__(
            api,
            f"{SynoSurveillanceStation.CAMERA_API_KEY}:{camera_id}",
            {
                ATTR_NAME: coordinator.data["cameras"][camera_id].name,
                ENTITY_ENABLE: coordinator.data["cameras"][camera_id].is_enabled,
                ATTR_DEVICE_CLASS: None,
                ATTR_ICON: None,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_STATE_CLASS: None,
            },
            coordinator,
        )
        Camera.__init__(self)
        self._camera_id = camera_id

    @property
    def camera_data(self) -> SynoCamera:
        """Camera data."""
        return self.coordinator.data["cameras"][self._camera_id]

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return {
            "identifiers": {
                (
                    DOMAIN,
                    f"{self._api.information.serial}_{self.camera_data.id}",
                )
            },
            "name": self.camera_data.name,
            "model": self.camera_data.model,
            "via_device": (
                DOMAIN,
                f"{self._api.information.serial}_{SynoSurveillanceStation.INFO_API_KEY}",
            ),
        }

    @property
    def available(self) -> bool:
        """Return the availability of the camera."""
        return self.camera_data.is_enabled and self.coordinator.last_update_success

    @property
    def supported_features(self) -> int:
        """Return supported features of this camera."""
        return SUPPORT_STREAM

    @property
    def is_recording(self) -> bool:
        """Return true if the device is recording."""
        return self.camera_data.is_recording  # type: ignore[no-any-return]

    @property
    def motion_detection_enabled(self) -> bool:
        """Return the camera motion detection status."""
        return self.camera_data.is_motion_detection_enabled  # type: ignore[no-any-return]

    def camera_image(self) -> bytes | None:
        """Return bytes of camera image."""
        _LOGGER.debug(
            "SynoDSMCamera.camera_image(%s)",
            self.camera_data.name,
        )
        if not self.available:
            return None
        try:
            return self._api.surveillance_station.get_camera_image(self._camera_id)  # type: ignore[no-any-return]
        except (
            SynologyDSMAPIErrorException,
            SynologyDSMRequestException,
            ConnectionRefusedError,
        ) as err:
            _LOGGER.debug(
                "SynoDSMCamera.camera_image(%s) - Exception:%s",
                self.camera_data.name,
                err,
            )
            return None

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        _LOGGER.debug(
            "SynoDSMCamera.stream_source(%s)",
            self.camera_data.name,
        )
        if not self.available:
            return None
        return self.camera_data.live_view.rtsp  # type: ignore[no-any-return]

    def enable_motion_detection(self) -> None:
        """Enable motion detection in the camera."""
        _LOGGER.debug(
            "SynoDSMCamera.enable_motion_detection(%s)",
            self.camera_data.name,
        )
        self._api.surveillance_station.enable_motion_detection(self._camera_id)

    def disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""
        _LOGGER.debug(
            "SynoDSMCamera.disable_motion_detection(%s)",
            self.camera_data.name,
        )
        self._api.surveillance_station.disable_motion_detection(self._camera_id)
