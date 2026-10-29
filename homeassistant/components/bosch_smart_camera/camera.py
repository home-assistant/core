"""Camera platform for the Bosch Smart Camera integration."""

import asyncio
from dataclasses import replace
from typing import override

from bosch_shc_camera_client.cameras import Camera as CameraData, CameraModel

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.stream import CONF_RTSP_TRANSPORT, Stream
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BoschCameraConfigEntry, BoschCameraCoordinator

PARALLEL_UPDATES = 0

# Wait between attempts to give a preloaded stream a new session.
REOPEN_INTERVAL = 30

MODEL_NAMES = {
    CameraModel.EYES_OUTDOOR: "Eyes Outdoor",
    CameraModel.INDOOR_360: "360° Indoor",
    CameraModel.EYES_OUTDOOR_II: "Eyes Outdoor II",
    CameraModel.EYES_INDOOR_II: "Eyes Indoor II",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoschCameraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the cameras of the account."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new_cameras() -> None:
        # Forget removed cameras so one that comes back gets a new entity.
        known.intersection_update(coordinator.data)
        new = set(coordinator.data) - known
        known.update(new)
        async_add_entities(BoschCamera(coordinator, camera_id) for camera_id in new)

    entry.async_on_unload(coordinator.async_add_listener(_add_new_cameras))
    _add_new_cameras()


class BoschCamera(CoordinatorEntity[BoschCameraCoordinator], Camera):
    """A camera of the account, showing the image of its latest event."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, coordinator: BoschCameraCoordinator, camera_id: str) -> None:
        """Initialize the camera."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self._camera_id = camera_id
        self._reopen_task: asyncio.Task[None] | None = None
        # The TLS proxy only speaks TCP.
        self.stream_options[CONF_RTSP_TRANSPORT] = "tcp"
        self._attr_unique_id = camera_id
        data = self._camera_data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera_id)},
            manufacturer="Bosch",
            model=MODEL_NAMES.get(data.model, data.hardware_version or None),
            name=data.title,
            sw_version=data.firmware_version,
        )

    @property
    def _camera_data(self) -> CameraData:
        """Return the latest data of this camera."""
        return self.coordinator.data[self._camera_id]

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the image of the latest event."""
        return await self.coordinator.async_get_snapshot(self._camera_id)

    @override
    async def stream_source(self) -> str | None:
        """Return the address of the live stream."""
        return await self.coordinator.live_sessions.async_get_url(
            self._camera_id, self._is_streaming, self._session_changed
        )

    @override
    async def async_refresh_providers(self, *, write_state: bool = True) -> None:
        """Skip provider discovery, it would open a live session for every camera."""

    def _is_streaming(self) -> bool:
        """Return whether a viewer is using the stream."""
        stream = self.stream
        return stream is not None and (
            bool(stream.outputs()) or stream.dynamic_stream_settings.preload_stream
        )

    @callback
    def _session_changed(self, url: str | None) -> None:
        """Follow a renewed session, or release the stream of an ended one."""
        if (stream := self.stream) is None:
            return
        if url:
            stream.update_source(url)
        elif stream.dynamic_stream_settings.preload_stream:
            # A preloaded worker keeps running after stop(), so it moves on.
            if self._reopen_task is None or self._reopen_task.done():
                self._reopen_task = (
                    self.coordinator.config_entry.async_create_background_task(
                        self.hass, self._async_reopen(stream), f"{DOMAIN} reopen"
                    )
                )
        else:
            self.stream = None
            self.coordinator.config_entry.async_create_task(self.hass, stream.stop())

    async def _async_reopen(self, stream: Stream) -> None:
        """Point a preloaded stream at a new session, retrying until it opens."""
        while self.stream is stream and stream.dynamic_stream_settings.preload_stream:
            try:
                source = await self.stream_source()
            except HomeAssistantError, TimeoutError:
                await asyncio.sleep(REOPEN_INTERVAL)
                continue
            stream.update_source(str(source))
            return
        if self.stream is stream:
            self.stream = None
            await stream.stop()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Stop the stream, its worker keeps retrying a closed proxy otherwise."""
        if self._reopen_task:
            self._reopen_task.cancel()
            await asyncio.wait([self._reopen_task])
        if (stream := self.stream) is not None:
            # The settings object is cached per entity, so only the stream's copy changes.
            stream.dynamic_stream_settings = replace(
                stream.dynamic_stream_settings, preload_stream=False
            )
            self.stream = None
            await stream.stop()
        # Closed last: a running worker would reopen the session otherwise.
        await self.coordinator.live_sessions.async_close(self._camera_id)

    @property
    @override
    def available(self) -> bool:
        """Return whether the camera is part of the latest camera list."""
        return super().available and self._camera_id in self.coordinator.data
