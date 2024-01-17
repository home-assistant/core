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

from .const import ATTR_DETECTION, DOMAIN, FreeboxHomeCategory
from .home_base import FreeboxHomeEntity
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up cameras."""
    router: FreeboxRouter = hass.data[DOMAIN][entry.unique_id]
    tracked: set[str] = set()

    @callback
    def update_callback() -> None:
        add_entities(hass, router, async_add_entities, tracked)

    router.listeners.append(
        async_dispatcher_connect(hass, router.signal_home_device_new, update_callback)
    )
    update_callback()

    entity_platform.async_get_current_platform()


@callback
def add_entities(
    hass: HomeAssistant,
    router: FreeboxRouter,
    async_add_entities: AddEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add new cameras from the router."""
    new_tracked: list[FreeboxCamera] = []

    for nodeid, node in router.home_devices.items():
        if (node["category"] != FreeboxHomeCategory.CAMERA) or (nodeid in tracked):
            continue
        new_tracked.append(FreeboxCamera(hass, router, node))
        tracked.add(nodeid)

    if new_tracked:
        async_add_entities(new_tracked, True)


class FreeboxCamera(FreeboxHomeEntity, FFmpegCamera):
    """Representation of a Freebox camera."""

    def __init__(
        self, hass: HomeAssistant, router: FreeboxRouter, node: dict[str, Any]
    ) -> None:
        """Initialize a camera."""

        super().__init__(hass, router, node)
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
            node["type"]["endpoints"], "slot", ATTR_DETECTION
        )
        self._attr_extra_state_attributes = {}
        self.update_node(node)

    async def async_enable_motion_detection(self) -> None:
        """Enable motion detection in the camera."""
        if await self.set_home_endpoint_value(self._command_motion_detection, True):
            self._attr_motion_detection_enabled = True

    async def async_disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""
        if await self.set_home_endpoint_value(self._command_motion_detection, False):
            self._attr_motion_detection_enabled = False

    async def async_update_signal(self) -> None:
        """Update the camera node."""
        self.update_node(self._router.home_devices[self._id])
        self.async_write_ha_state()

    def update_node(self, node: dict[str, Any]) -> None:
        """Update params."""
        self._name = node["label"].strip()

        # Get status
        if self._node["status"] == "active":
            self._attr_is_streaming = True
        else:
            self._attr_is_streaming = False

        # Parse all endpoints values
        for endpoint in filter(
            lambda x: (x["ep_type"] == "signal"), node["show_endpoints"]
        ):
            self._attr_extra_state_attributes[endpoint["name"]] = endpoint["value"]

        # Get motion detection status
        self._attr_motion_detection_enabled = self._attr_extra_state_attributes[
            ATTR_DETECTION
        ]
