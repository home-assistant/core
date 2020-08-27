"""Support for Agent camera streaming."""
from datetime import timedelta
import logging

from agent import AgentError

from homeassistant.components.camera import SUPPORT_ON_OFF
from homeassistant.components.mjpeg.camera import (
    CONF_MJPEG_URL,
    CONF_STILL_IMAGE_URL,
    MjpegCamera,
    filter_urllib3_logging,
)
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.helpers import entity_platform

from .const import (
    ATTRIBUTION,
    CAMERA_SCAN_INTERVAL_SECS,
    CONNECTION,
    DOMAIN as AGENT_DOMAIN,
)

SCAN_INTERVAL = timedelta(seconds=CAMERA_SCAN_INTERVAL_SECS)

_LOGGER = logging.getLogger(__name__)

_DEV_EN_ALT = "enable_alerts"
_DEV_DS_ALT = "disable_alerts"
_DEV_EN_REC = "start_recording"
_DEV_DS_REC = "stop_recording"
_DEV_SNAP = "snapshot"

CAMERA_SERVICES = {
    _DEV_EN_ALT: "async_enable_alerts",
    _DEV_DS_ALT: "async_disable_alerts",
    _DEV_EN_REC: "async_start_recording",
    _DEV_DS_REC: "async_stop_recording",
    _DEV_SNAP: "async_snapshot",
}


async def async_setup_entry(
    hass, config_entry, async_add_entities, discovery_info=None
):
    """Set up the Agent cameras."""
    filter_urllib3_logging()
    cameras = []

    server = hass.data[AGENT_DOMAIN][config_entry.entry_id][CONNECTION]
    if not server.devices:
        _LOGGER.warning("Could not fetch cameras from Agent server")
        return

    for device in server.devices:
        if device.typeID == 2:
            camera = AgentCamera(device)
            cameras.append(camera)

    async_add_entities(cameras)

    platform = entity_platform.current_platform.get()
    for service, method in CAMERA_SERVICES.items():
        platform.async_register_entity_service(service, {}, method)


class AgentCamera(MjpegCamera):
    """Representation of an Agent Device Stream."""

    def __init__(self, device):
        """Initialize as a subclass of MjpegCamera."""
        self._servername = device.client.name
        self.server_url = device.client._server_url

        device_info = {
            CONF_NAME: device.name,
            CONF_MJPEG_URL: f"{self.server_url}{device.mjpeg_image_url}&size={device.mjpegStreamWidth}x{device.mjpegStreamHeight}",
            CONF_STILL_IMAGE_URL: f"{self.server_url}{device.still_image_url}&size={device.mjpegStreamWidth}x{device.mjpegStreamHeight}",
        }
        self.device = device
        self._removed = False
        self._name = f"{self._servername} {device.name}"
        self._unique_id = f"{device._client.unique}_{device.typeID}_{device.id}"
        super().__init__(device_info)

    @property
    def device_info(self):
        """Return the device info for adding the entity to the agent object."""
        return {
            "identifiers": {(AGENT_DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "Agent",
            "model": "Camera",
            "sw_version": self.device.client.version,
        }

    async def async_update(self):
        """Update our state from the Agent API."""
        try:
            await self.device.update()
            if self._removed:
                _LOGGER.debug("%s reacquired", self._name)
            self._removed = False
        except AgentError:
            if self.device.client.is_available:  # server still available - camera error
                if not self._removed:
                    _LOGGER.error("%s lost", self._name)
                    self._removed = True

    @property
    def device_state_attributes(self):
        """Return the Agent DVR camera state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "editable": False,
            "enabled": self.is_on,
            "connected": self.connected,
            "detected": self.is_detected,
            "alerted": self.is_alerted,
            "has_ptz": self.device.has_ptz,
            "alerts_enabled": self.device.alerts_active,
        }

    @property
    def should_poll(self) -> bool:
        """Update the state periodically."""
        return True

    @property
    def is_recording(self) -> bool:
        """Return whether the monitor is recording."""
        return self.device.recording

    @property
    def is_alerted(self) -> bool:
        """Return whether the monitor has alerted."""
        return self.device.alerted

    @property
    def is_detected(self) -> bool:
        """Return whether the monitor has alerted."""
        return self.device.detected

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.client.is_available

    @property
    def connected(self) -> bool:
        """Return True if entity is connected."""
        return self.device.connected

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return SUPPORT_ON_OFF

    @property
    def is_on(self) -> bool:
        """Return true if on."""
        return self.device.online

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        if self.is_on:
            return "mdi:camcorder"
        return "mdi:camcorder-off"

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return self.device.detector_active

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this agent object."""
        return self._unique_id

    async def async_enable_alerts(self):
        """Enable alerts."""
        await self.device.alerts_on()

    async def async_disable_alerts(self):
        """Disable alerts."""
        await self.device.alerts_off()

    async def async_enable_motion_detection(self):
        """Enable motion detection."""
        await self.device.detector_on()

    async def async_disable_motion_detection(self):
        """Disable motion detection."""
        await self.device.detector_off()

    async def async_start_recording(self):
        """Start recording."""
        await self.device.record()

    async def async_stop_recording(self):
        """Stop recording."""
        await self.device.record_stop()

    async def async_turn_on(self):
        """Enable the camera."""
        await self.device.enable()

    async def async_snapshot(self):
        """Take a snapshot."""
        await self.device.snapshot()

    async def async_turn_off(self):
        """Disable the camera."""
        await self.device.disable()
