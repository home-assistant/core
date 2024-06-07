"""Support for Synology DSM cameras."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from synology_dsm.api.surveillance_station import SynoCamera, SynoSurveillanceStation
from synology_dsm.exceptions import (
    SynologyDSMAPIErrorException,
    SynologyDSMRequestException,
)

from homeassistant.components.camera import (
    Camera,
    CameraEntityDescription,
    CameraEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SynoApi
from .const import (
    CONF_SNAPSHOT_QUALITY,
    DEFAULT_SNAPSHOT_QUALITY,
    DOMAIN,
    SIGNAL_CAMERA_SOURCE_CHANGED,
)
from .coordinator import SynologyDSMCameraUpdateCoordinator
from .entity import SynologyDSMBaseEntity, SynologyDSMEntityDescription
from .models import SynologyDSMData

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SynologyDSMCameraEntityDescription(
    CameraEntityDescription, SynologyDSMEntityDescription
):
    """Describes Synology DSM camera entity."""

    camera_id: int


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Synology NAS cameras."""
    data: SynologyDSMData = hass.data[DOMAIN][entry.unique_id]
    if coordinator := data.coordinator_cameras:
        async_add_entities(
            SynoDSMCamera(data.api, coordinator, camera_id)
            for camera_id in coordinator.data["cameras"]
        )


class SynoDSMCamera(SynologyDSMBaseEntity[SynologyDSMCameraUpdateCoordinator], Camera):
    """Representation a Synology camera."""

    _attr_supported_features = CameraEntityFeature.STREAM
    entity_description: SynologyDSMCameraEntityDescription

    def __init__(
        self,
        api: SynoApi,
        coordinator: SynologyDSMCameraUpdateCoordinator,
        camera_id: int,
    ) -> None:
        """Initialize a Synology camera."""
        description = SynologyDSMCameraEntityDescription(
            api_key=SynoSurveillanceStation.CAMERA_API_KEY,
            key=str(camera_id),
            camera_id=camera_id,
            name=None,
            entity_registry_enabled_default=coordinator.data["cameras"][
                camera_id
            ].is_enabled,
        )
        self.snapshot_quality = api._entry.options.get(  # noqa: SLF001
            CONF_SNAPSHOT_QUALITY, DEFAULT_SNAPSHOT_QUALITY
        )
        super().__init__(api, coordinator, description)
        Camera.__init__(self)

    @property
    def camera_data(self) -> SynoCamera:
        """Camera data."""
        return self.coordinator.data["cameras"][self.entity_description.camera_id]

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        information = self._api.information
        assert information is not None
        return DeviceInfo(
            identifiers={(DOMAIN, f"{information.serial}_{self.camera_data.id}")},
            name=self.camera_data.name,
            model=self.camera_data.model,
            via_device=(
                DOMAIN,
                f"{information.serial}_{SynoSurveillanceStation.INFO_API_KEY}",
            ),
        )

    @property
    def available(self) -> bool:
        """Return the availability of the camera."""
        return self.camera_data.is_enabled and super().available

    @property
    def is_recording(self) -> bool:
        """Return true if the device is recording."""
        return self.camera_data.is_recording

    @property
    def motion_detection_enabled(self) -> bool:
        """Return the camera motion detection status."""
        return bool(self.camera_data.is_motion_detection_enabled)

    def _listen_source_updates(self) -> None:
        """Listen for camera source changed events."""

        @callback
        def _handle_signal(url: str) -> None:
            if self.stream:
                _LOGGER.debug("Update stream URL for camera %s", self.camera_data.name)
                self.stream.update_source(url)

        assert self.platform.config_entry
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_CAMERA_SOURCE_CHANGED}_{self.platform.config_entry.entry_id}_{self.camera_data.id}",
                _handle_signal,
            )
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to signal."""
        self._listen_source_updates()
        await super().async_added_to_hass()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        _LOGGER.debug(
            "SynoDSMCamera.camera_image(%s)",
            self.camera_data.name,
        )
        if not self.available:
            return None
        assert self._api.surveillance_station is not None
        try:
            return await self._api.surveillance_station.get_camera_image(
                self.entity_description.camera_id, self.snapshot_quality
            )
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

        return self.camera_data.live_view.rtsp

    async def async_enable_motion_detection(self) -> None:
        """Enable motion detection in the camera."""
        _LOGGER.debug(
            "SynoDSMCamera.enable_motion_detection(%s)",
            self.camera_data.name,
        )
        assert self._api.surveillance_station is not None
        await self._api.surveillance_station.enable_motion_detection(
            self.entity_description.camera_id
        )

    async def async_disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""
        _LOGGER.debug(
            "SynoDSMCamera.disable_motion_detection(%s)",
            self.camera_data.name,
        )
        assert self._api.surveillance_station is not None
        await self._api.surveillance_station.disable_motion_detection(
            self.entity_description.camera_id
        )
