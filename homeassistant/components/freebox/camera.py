"""Support for Freebox cameras."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import CameraEntityFeature
from homeassistant.components.ffmpeg.camera import (
    CONF_EXTRA_ARGUMENTS,
    CONF_INPUT,
    DEFAULT_ARGUMENTS,
    FFmpegCamera,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_ACTIVATION,
    ATTR_DETECTION,
    ATTR_DISK,
    ATTR_FLIP,
    ATTR_QUALITY,
    ATTR_RTSP,
    ATTR_SENSITIVITY,
    ATTR_SOUND_DETECTION,
    ATTR_SOUND_TRIGGER,
    ATTR_THRESHOLD,
    ATTR_TIMESTAMP,
    ATTR_VOLUME,
    DOMAIN,
)
from .home_base import FreeboxHomeBaseClass
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up cameras."""
    router = hass.data[DOMAIN][entry.unique_id]
    tracked: set = set()

    @callback
    def update_callback():
        add_entities(hass, router, async_add_entities, tracked)

    router.listeners.append(
        async_dispatcher_connect(hass, router.signal_home_device_new, update_callback)
    )
    update_callback()

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "flip",
        {},
        "async_flip",
    )


@callback
def add_entities(hass: HomeAssistant, router, async_add_entities, tracked):
    """Add new cameras from the router."""
    new_tracked = []

    for nodeid, node in router.home_devices.items():
        if (node["category"] != Platform.CAMERA) or (nodeid in tracked):
            continue
        new_tracked.append(FreeboxCamera(hass, router, node))
        tracked.add(nodeid)

    if new_tracked:
        async_add_entities(new_tracked, True)


class FreeboxCamera(FreeboxHomeBaseClass, FFmpegCamera):
    """Representation of a Freebox camera."""

    def __init__(
        self, hass: HomeAssistant, router: FreeboxRouter, node: dict[str, Any]
    ) -> None:
        """Initialize a camera."""

        super().__init__(hass, router, node)
        self._flip: Any
        device_info = {
            CONF_NAME: node["label"].strip(),
            CONF_INPUT: node["props"]["Stream"],
            CONF_EXTRA_ARGUMENTS: DEFAULT_ARGUMENTS,
        }
        FFmpegCamera.__init__(self, hass, device_info)

        self._supported_features = (
            CameraEntityFeature.ON_OFF | CameraEntityFeature.STREAM
        )

        self._command_motion_detection = self.get_command_id(
            node["type"]["endpoints"], ATTR_DETECTION
        )
        self._high_quality_video = self.get_command_id(
            node["show_endpoints"], ATTR_QUALITY
        )
        self._command_flip = self.get_command_id(node["show_endpoints"], ATTR_FLIP)
        self._motion_threshold = self.get_command_id(
            node["show_endpoints"], ATTR_THRESHOLD
        )
        self._motion_sensitivity = self.get_command_id(
            node["show_endpoints"], ATTR_SENSITIVITY
        )
        self._activation_with_alarm = self.get_command_id(
            node["show_endpoints"], ATTR_ACTIVATION
        )
        self._timestamp = self.get_command_id(node["show_endpoints"], ATTR_TIMESTAMP)
        self._mic_volume = self.get_command_id(node["show_endpoints"], ATTR_VOLUME)
        self._sound_detection = self.get_command_id(
            node["show_endpoints"], ATTR_SOUND_DETECTION
        )
        self._sound_trigger = self.get_command_id(
            node["show_endpoints"], ATTR_SOUND_TRIGGER
        )
        self._rstp = self.get_command_id(node["show_endpoints"], ATTR_RTSP)
        self._disk = self.get_command_id(node["show_endpoints"], ATTR_DISK)

        self.update_node(node)

    @property
    def flip(self) -> bool:
        """Return flip."""
        return self._flip

    async def async_flip(self, entity: FreeboxCamera) -> None:
        """Flip the camera stream."""
        self._flip = not entity.flip
        await entity.set_home_endpoint_value(entity._command_flip, entity.flip)

    @property
    def motion_detection_enabled(self) -> bool:
        """Return the camera motion detection status."""
        return self._attr_motion_detection_enabled

    async def async_enable_motion_detection(self) -> None:
        """Enable motion detection in the camera."""
        await self.set_home_endpoint_value(self._command_motion_detection, True)
        self._attr_motion_detection_enabled = True

    async def async_disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""
        await self.set_home_endpoint_value(self._command_motion_detection, False)
        self._attr_motion_detection_enabled = False

    async def async_update_signal(self) -> None:
        """Update the camera node."""
        self.update_node(self._router.home_devices[self._id])

    def update_node(self, node):
        """Update params."""
        self._name = node["label"].strip()

        # Get status
        if self._node["status"] == "active":
            self._attr_is_streaming = True
        else:
            self._attr_is_streaming = False
        # Parse all endpoints values & needed commands
        for endpoint in filter(
            lambda x: (x["ep_type"] == "signal"), node["show_endpoints"]
        ):
            if endpoint["name"] == ATTR_DETECTION:
                self._attr_motion_detection_enabled = endpoint["value"]
            elif endpoint["name"] == ATTR_ACTIVATION:
                self._activation_with_alarm = endpoint["value"]
            elif endpoint["name"] == ATTR_QUALITY:
                self._high_quality_video = endpoint["value"]
            elif endpoint["name"] == ATTR_SENSITIVITY:
                self._motion_sensitivity = endpoint["value"]
            elif endpoint["name"] == ATTR_THRESHOLD:
                self._motion_threshold = endpoint["value"]
            elif endpoint["name"] == ATTR_FLIP:
                self._flip = endpoint["value"]
            elif endpoint["name"] == ATTR_TIMESTAMP:
                self._timestamp = endpoint["value"]
            elif endpoint["name"] == ATTR_VOLUME:
                self._volume_micro = endpoint["value"]
            elif endpoint["name"] == ATTR_SOUND_DETECTION:
                self._sound_detection = endpoint["value"]
            elif endpoint["name"] == ATTR_SOUND_TRIGGER:
                self._sound_trigger = endpoint["value"]
            elif endpoint["name"] == ATTR_RTSP:
                self._rtsp = endpoint["value"]
            elif endpoint["name"] == ATTR_DISK:
                self._disk = endpoint["value"]
