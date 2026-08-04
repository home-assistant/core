"""Support for Agent DVR camera streaming."""

import logging

from homeassistant.components.camera import CameraEntityFeature
from homeassistant.components.mjpeg import MjpegCamera, filter_urllib3_logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AgentDVRConfigEntry
from .const import (
    ATTR_GROUPS,
    ATTR_LOCATION,
    ATTR_PTZ_TYPE,
    ATTRIBUTION,
    DEVICE_TYPE_CAMERA,
    DOMAIN,
)
from .coordinator import AgentDVRDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AgentDVRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Agent DVR cameras.

    The snapshot/recording/alerts services are registered once for the
    whole camera platform in services.py (async_setup), not per config
    entry here.
    """
    filter_urllib3_logging()
    data = entry.runtime_data
    coordinator = data.coordinator

    async_add_entities(
        AgentDVRCamera(coordinator, data.client, oid_ot, data.unique_id)
        for oid_ot, device in coordinator.data["devices"].items()
        if device["typeID"] == DEVICE_TYPE_CAMERA
    )


class AgentDVRCamera(CoordinatorEntity[AgentDVRDataUpdateCoordinator], MjpegCamera):
    """Representation of an Agent DVR camera, backed by the shared coordinator."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = CameraEntityFeature.ON_OFF

    def __init__(
        self,
        coordinator: AgentDVRDataUpdateCoordinator,
        client,
        oid_ot: str,
        server_unique_id: str,
    ) -> None:
        """Initialize as a subclass of MjpegCamera."""
        CoordinatorEntity.__init__(self, coordinator)
        self._client = client
        self._oid_ot = oid_ot
        device = coordinator.data["devices"][oid_ot]
        self._oid = int(device["id"])
        self._ot = int(device["typeID"])

        self._attr_unique_id = f"{server_unique_id}_{self._ot}_{self._oid}"

        size = ""
        data = device.get("data", {})
        width = data.get("mjpegStreamWidth")
        height = data.get("mjpegStreamHeight")
        if width and height:
            size = f"&size={width}x{height}"

        status = coordinator.data.get("status", {})
        MjpegCamera.__init__(
            self,
            name=device["name"],
            mjpeg_url=f"{client.media_url('mjpeg', self._oid)}{size}",
            still_image_url=f"{client.media_url('still', self._oid)}{size}",
            authentication=client.auth_type,
            username=client.username,
            password=client.password,
            unique_id=self._attr_unique_id,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, self._attr_unique_id)},
                manufacturer="Agent",
                model="Camera",
                name=f"{status.get('name', 'Agent DVR')} {device['name']}",
                sw_version=status.get("version"),
            ),
        )

    @property
    def _device(self) -> dict:
        return self.coordinator.data["devices"].get(self._oid_ot, {})

    @property
    def _data(self) -> dict:
        return self._device.get("data", {})

    @property
    def available(self) -> bool:
        """Return True if the camera is still present in the last poll."""
        return super().available and bool(self._device)

    @property
    def is_on(self) -> bool:
        """Return true if the camera is enabled."""
        return bool(self._data.get("online"))

    @property
    def is_recording(self) -> bool:
        """Return whether the monitor is recording."""
        return bool(self._data.get("recording"))

    @property
    def motion_detection_enabled(self) -> bool:
        """Return the camera motion detection status."""
        return bool(self._data.get("detectorActive"))

    @property
    def icon(self) -> str:
        """Return an icon reflecting the on/off state."""
        return "mdi:camcorder" if self.is_on else "mdi:camcorder-off"

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional camera state attributes."""
        device = self._device
        data = self._data
        locations = self.coordinator.data.get("locations", [])
        location_index = device.get("locationIndex", -1)
        location_name = (
            locations[location_index]["name"]
            if 0 <= location_index < len(locations)
            else None
        )
        return {
            "editable": False,
            "enabled": data.get("online"),
            "connected": data.get("connected"),
            "detected": data.get("detected"),
            "alerted": data.get("alerted"),
            "alerts_enabled": data.get("alertsActive"),
            "has_ptz": data.get("ptztype", "") not in ("", None),
            ATTR_PTZ_TYPE: data.get("ptztype"),
            ATTR_LOCATION: location_name,
            ATTR_GROUPS: device.get("groups"),
        }

    async def async_turn_on(self) -> None:
        """Enable the camera."""
        await self._client.switch_on(self._oid, self._ot)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Disable the camera."""
        await self._client.switch_off(self._oid, self._ot)
        await self.coordinator.async_request_refresh()

    async def async_enable_motion_detection(self) -> None:
        """Enable motion detection."""
        await self._client.detector_on(self._oid, self._ot)
        await self.coordinator.async_request_refresh()

    async def async_disable_motion_detection(self) -> None:
        """Disable motion detection."""
        await self._client.detector_off(self._oid, self._ot)
        await self.coordinator.async_request_refresh()

    async def async_enable_alerts(self) -> None:
        """Enable alerts."""
        await self._client.alerts_on(self._oid, self._ot)
        await self.coordinator.async_request_refresh()

    async def async_disable_alerts(self) -> None:
        """Disable alerts."""
        await self._client.alerts_off(self._oid, self._ot)
        await self.coordinator.async_request_refresh()

    async def async_start_recording(self) -> None:
        """Start recording."""
        await self._client.record_start(self._oid, self._ot)
        await self.coordinator.async_request_refresh()

    async def async_stop_recording(self) -> None:
        """Stop recording."""
        await self._client.record_stop(self._oid, self._ot)
        await self.coordinator.async_request_refresh()

    async def async_snapshot(self) -> None:
        """Take a snapshot."""
        await self._client.snapshot(self._oid, self._ot)
