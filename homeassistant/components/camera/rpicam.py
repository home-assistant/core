"""
Support for RPI Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.rpicam/
"""

import logging
import json
import voluptuous as vol
from homeassistant.components import mqtt
from homeassistant.components.camera import \
    PLATFORM_SCHEMA, DEFAULT_CONTENT_TYPE, DOMAIN
from homeassistant.core import callback
from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_AUTHENTICATION,
    HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION,
    CONF_VERIFY_SSL, ATTR_ENTITY_ID)

from homeassistant.components.camera.generic import GenericCamera

from homeassistant.helpers import config_validation as cv
# from homeassistant.util.async_ import run_coroutine_threadsafe
from homeassistant.helpers.service import extract_entity_ids

DEPENDENCIES = ['mqtt']

_LOGGER = logging.getLogger(__name__)

CONF_CONTENT_TYPE = 'content_type'
CONF_LIMIT_REFETCH_TO_URL_CHANGE = 'limit_refetch_to_url_change'
CONF_STILL_IMAGE_URL = 'still_image_url'
CONF_FRAMERATE = 'framerate'

DEFAULT_NAME = 'rpicam'
RPICAM_DATA = 'rpicam'
ENTITIES = "entities"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STILL_IMAGE_URL): cv.template,
    vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION):
        vol.In([HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]),
    vol.Optional(CONF_LIMIT_REFETCH_TO_URL_CHANGE, default=False): cv.boolean,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_CONTENT_TYPE, default=DEFAULT_CONTENT_TYPE): cv.string,
    vol.Optional(CONF_FRAMERATE, default=2): cv.positive_int,
    vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
})

#
# Video ON service
#
SERVICE_REC_VIDEO_ON = "rpi_video_on"
ATTR_DURATION = "duration"
DURATION_NONE = None

SERVICE_REC_VIDEO_ON_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
    ATTR_DURATION: cv.positive_int
})
#######################

#
# Video OFF service
#
SERVICE_REC_VIDEO_OFF = "rpi_video_off"

SERVICE_REC_VIDEO_OFF_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids
})
#######################

#
# Image service params
#
SERVICE_REC_IMAGE = "rpi_image"

SERVICE_REC_IMAGE_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids
})
#######################

#
# Exposure mode service
#
SERVICE_EXPOSURE_MODE = "rpi_exposure_mode"
ATTR_MODE = "mode"
MODE_NONE = None

SERVICE_EXPOSURE_MODE_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
    ATTR_MODE: cv.string
})
#######################

#
# Pan/Tilt service
#
SERVICE_PANTILT = "rpi_set_pantilt"
ATTR_VIEW = "view"
ATTR_PAN = "pan"
ATTR_TILT = "tilt"
PT_NONE = None

SERVICE_PANTILT_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
    ATTR_VIEW: cv.string,
    ATTR_PAN: cv.positive_int,
    ATTR_TILT: cv.positive_int
})
#######################

STATUSES = ('halted', 'image', 'md_ready', 'md_video',
            'ready', 'timelapse', 'video')
INACTIVE_STATUSES = ('halted', 'Unknown', None)
ACTIVE_STATUSES = ('image', 'md_ready', 'md_video',
                   'ready', 'timelapse', 'video')
RECORDING_STATUSES = ('image', 'md_video', 'timelapse', 'video')
MOTION_STATUSES = ('md_ready', 'md_video')
EXPOSURE_MODES = (
    "off",
    "auto",
    "night",
    "nightpreview",
    "backlight",
    "spotlight",
    "sports",
    "snow",
    "beach",
    "verylong",
    "fixedfps",
    "antishake",
    "fireworks"
)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Rpicam platform setup."""
    def _get_cameras(service, all_if_no_id=False):
        """Get camera list for service.

        Set all_if_no_id to return the full list of cameras
        if no entity_id is supplied.
        If all_in_no_id is false, entity_id needs to be specified.
        """
        target_cameras = []
        all_cameras = hass.data[RPICAM_DATA][ENTITIES]
        entity_ids = extract_entity_ids(hass, service)
        if not entity_ids and all_if_no_id:
            target_cameras = all_cameras
        else:
            target_cameras = [camera for camera in all_cameras
                              if camera.entity_id in entity_ids]
        return target_cameras

    def handle_video_on(service):
        duration = service.data.get(ATTR_DURATION, None)
        for camera in _get_cameras(service, all_if_no_id=True):
            camera.record_video_on(duration)

    def handle_video_off(service):
        for camera in _get_cameras(service, all_if_no_id=True):
            camera.record_video_off()

    def handle_image(service):
        for camera in _get_cameras(service, all_if_no_id=True):
            camera.record_image()

    def handle_exposure_mode(service):
        mode = service.data.get(ATTR_MODE, None)
        for camera in _get_cameras(service, all_if_no_id=True):
            camera.change_exposure_mode(mode)

    def handle_pantilt(service):
        """Handle pan/tilt service call."""
        view = service.data.get(ATTR_VIEW, None)
        pan = service.data.get(ATTR_PAN, None)
        tilt = service.data.get(ATTR_TILT, None)

        for camera in _get_cameras(service, all_if_no_id=False):
            camera.set_pantilt(view, pan, tilt)

    hass.services.async_register(DOMAIN, SERVICE_REC_VIDEO_ON,
                                 handle_video_on,
                                 schema=SERVICE_REC_VIDEO_ON_SCHEMA)

    hass.services.async_register(DOMAIN, SERVICE_REC_VIDEO_OFF,
                                 handle_video_off,
                                 schema=SERVICE_REC_VIDEO_OFF_SCHEMA)

    hass.services.async_register(DOMAIN, SERVICE_REC_IMAGE,
                                 handle_image,
                                 schema=SERVICE_REC_IMAGE_SCHEMA)

    hass.services.async_register(DOMAIN, SERVICE_EXPOSURE_MODE,
                                 handle_exposure_mode,
                                 schema=SERVICE_EXPOSURE_MODE_SCHEMA)

    hass.services.async_register(DOMAIN, SERVICE_PANTILT,
                                 handle_pantilt,
                                 schema=SERVICE_PANTILT_SCHEMA)

    async_add_entities([RpiCam(hass, config)])


class RpiCam(GenericCamera):
    """Raspberry PI camera support based rpi-cam-mqtt."""

    def __init__(self, hass, device_info):
        """Initialize an rpicam camera."""
        super().__init__(hass, device_info)
        self.cam = device_info.get(CONF_NAME)
        _LOGGER.debug("Rpicam config found for \"%s\"", self.cam)
        self._cmd_topic = "rpicam/{}".format(self.cam)
        self._status_topic = "rpicam/{}/status".format(self.cam)
        self._ptcmd_topic = "rpicam/{}/pt".format(self.cam)

        self._qos = 1
        self.rpi_status = None

    @property
    def state(self):
        """Return the camera state."""
        return self.rpi_status

    @property
    def is_on(self):
        """Return true if on."""
        return bool(self.rpi_status in ACTIVE_STATUSES)

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return bool(self.rpi_status in RECORDING_STATUSES)

    def turn_off(self):
        """Turn off camera."""
        mqtt.publish(self.hass, self._cmd_topic, 'ru 0', self._qos)

    def turn_on(self):
        """Turn on camera."""
        mqtt.publish(self.hass, self._cmd_topic, 'ru 1', self._qos)

    def enable_motion_detection(self):
        """Enable motion detection in the camera."""
        mqtt.publish(self.hass, self._cmd_topic, 'md 1', self._qos)

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        mqtt.publish(self.hass, self._cmd_topic, 'md 0', self._qos)

    @property
    def brand(self):
        """Return the camera brand."""
        return "Raspberry Pi"

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        ret = None
        if self.rpi_status in MOTION_STATUSES:
            ret = True
        return ret

    @property
    def model(self):
        """Return the camera model."""
        return "RpiCam"

    async def async_added_to_hass(self):
        """Handle rpicam entity addition to hass."""
        if RPICAM_DATA not in self.hass.data:
            self.hass.data[RPICAM_DATA] = {}
            self.hass.data[RPICAM_DATA][ENTITIES] = []

        self.hass.data[RPICAM_DATA][ENTITIES].append(self)

        # Subscribe to status topic when entities get added to hass.
        @callback
        def message_received(topic, payload, qos):
            """Handle new MQTT messages."""
            _LOGGER.debug(
                "Status %s published for %s on %s (qos: %s)",
                payload,
                self.cam,
                topic,
                qos
            )
            self.rpi_status = payload.decode()

        await mqtt.async_subscribe(
            self.hass, self._status_topic, message_received, self._qos, None)

    def record_video_on(self, duration=None):
        """Start video recording. Specify duration to stop after n seconds."""
        video_on_cmd = 'ca 1'
        if duration:
            video_on_cmd = "{} {}".format(video_on_cmd, duration)
        mqtt.publish(self.hass, self._cmd_topic, video_on_cmd, self._qos)

    def record_video_off(self):
        """Stop video recording."""
        mqtt.publish(self.hass, self._cmd_topic, 'ca 0', self._qos)

    def record_image(self):
        """Take a picture."""
        mqtt.publish(self.hass, self._cmd_topic, 'im 1', self._qos)

    def change_exposure_mode(self, mode):
        """Set exposure mode."""
        if mode in EXPOSURE_MODES:
            exp_mode_cmd = "em {}".format(mode)
            mqtt.publish(self.hass, self._cmd_topic, exp_mode_cmd, self._qos)

    def set_pantilt(self, view=None, pan=None, tilt=None):
        """Publish a pantilt command."""
        pt_cmd = {'view': None,
                  'pan': None,
                  'tilt': None}

        if view:
            # Search in list of available views
            # and send view command if found
            pt_cmd['view'] = view
        else:
            if pan:
                pt_cmd['pan'] = pan
            if tilt:
                pt_cmd['tilt'] = tilt
        pt_cmd = json.dumps(pt_cmd, indent=4)
        mqtt.publish(self.hass, self._ptcmd_topic, pt_cmd, self._qos)
