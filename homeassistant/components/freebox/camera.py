import logging
import json
import asyncio
import aiohttp
import async_timeout
import collections

from typing import Dict
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers import config_validation as cv, entity_platform, service

from homeassistant.components.ffmpeg.camera import (
    FFmpegCamera,
    CONF_INPUT,
    CONF_EXTRA_ARGUMENTS,
    DEFAULT_ARGUMENTS
)

from homeassistant.components.camera import (
    DEFAULT_CONTENT_TYPE,
    PLATFORM_SCHEMA,
    SUPPORT_STREAM,
    SUPPORT_ON_OFF,
    Camera,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)

from homeassistant.components.generic.camera import (
    CONF_CONTENT_TYPE,
    CONF_LIMIT_REFETCH_TO_URL_CHANGE,
    CONF_STILL_IMAGE_URL,
    CONF_STREAM_SOURCE,
    CONF_FRAMERATE
)

from .base_class import FreeboxHomeBaseClass
from .const import DOMAIN, VALUE_NOT_SET
from .router import FreeboxRouter


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities) -> None:
    router = hass.data[DOMAIN][entry.unique_id]
    tracked = set()

    @callback
    def update_callback():
        add_entities(hass, router, async_add_entities, tracked)

    router.listeners.append(async_dispatcher_connect(hass, router.signal_home_device_new, update_callback))
    update_callback()

    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service("flip",{},"async_flip",)


@callback
def add_entities(hass, router, async_add_entities, tracked):
    """Add new cover from the router."""
    new_tracked = []

    for nodeId, node in router.home_devices.items():
        if (node["category"]!="camera") or (nodeId in tracked):
            continue
        new_tracked.append(FreeboxCamera(hass, router, node))
        tracked.add(nodeId)

    if new_tracked:
        async_add_entities(new_tracked, True)



class FreeboxCamera(FreeboxHomeBaseClass, FFmpegCamera):
    def __init__(self, hass, router, node):
        """Initialize a camera."""
        super().__init__(hass, router, node)

        device_info = {CONF_NAME: node["label"].strip(),CONF_INPUT: node["props"]["Stream"],CONF_EXTRA_ARGUMENTS: DEFAULT_ARGUMENTS }
        FFmpegCamera.__init__(self, hass, device_info)
        
        self._supported_features        = SUPPORT_STREAM
        self._command_flip              = self.get_command_id(node['show_endpoints'], "slot", "flip")
        self._command_motion_detection  = self.get_command_id(node['type']['endpoints'], "slot", "detection")

        self.update_node()

    async def async_flip(entity):
        entity._flip = not entity._flip
        await entity.set_home_endpoint_value(entity._command_flip, {"value": entity._flip})

    @property
    def state_attributes(self):
        """Return the camera state attributes."""
        attr = super().state_attributes
        attr["motion_detection"]        = self.motion_detection_enabled
        attr["high_quality_video"]      = self._high_quality_video
        attr["flip_video"]              = self._flip
        attr["motion_threshold"]        = self._motion_threshold
        attr["motion_sensitivity"]      = self._motion_sensitivity
        attr["activation_with_alarm"]   = self._activation_with_alarm
        attr["timestamp"]           = self._timestamp
        attr["volume_microphone"]   = self._volume_micro
        attr["sound_detection"]     = self._sound_detection
        attr["sound_trigger"]       = self._sound_trigger
        attr["rtsp"]                = self._rtsp
        attr["disk"]                = self._disk
        return attr

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return self._motion_detection_enabled

    async def async_enable_motion_detection(self):
        """Enable motion detection in the camera."""
        await self.set_home_endpoint_value(self._command_motion_detection, {"value": True})
        self._motion_detection_enabled = True

    async def async_disable_motion_detection(self):
        """Disable motion detection in camera."""
        await self.set_home_endpoint_value(self._command_motion_detection, {"value": False})
        self._motion_detection_enabled = False

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    async def async_update_node(self):
        self.update_node()


    def update_node(self):

        # Get status
        if( self._node["status"] == "active"):
            self.is_streaming = True
        else:
            self.is_streaming = False

        #self.is_recording?

        # Parse all endpoints values & needed commands
        for endpoint in filter(lambda x:(x["ep_type"] == "signal"), self._node['show_endpoints']):
            if( endpoint["name"] == "detection" ):
                self._motion_detection_enabled = endpoint["value"]
            elif( endpoint["name"] == "activation" ):
                self._activation_with_alarm = endpoint["value"]
            elif( endpoint["name"] == "quality" ):
                self._high_quality_video = endpoint["value"]
            elif( endpoint["name"] == "sensitivity" ):
                self._motion_sensitivity = endpoint["value"]
            elif( endpoint["name"] == "threshold" ):
                self._motion_threshold = endpoint["value"]
            elif( endpoint["name"] == "flip" ):
                self._flip = endpoint["value"]
            elif( endpoint["name"] == "timestamp" ):
                self._timestamp = endpoint["value"]
            elif( endpoint["name"] == "volume" ):
                self._volume_micro = endpoint["value"]
            elif( endpoint["name"] == "sound_detection" ):
                self._sound_detection = endpoint["value"]
            elif( endpoint["name"] == "sound_trigger" ):
                self._sound_trigger = endpoint["value"]
            elif( endpoint["name"] == "rtsp" ):
                self._rtsp = endpoint["value"]
            elif( endpoint["name"] == "disk" ):
                self._disk = endpoint["value"]
