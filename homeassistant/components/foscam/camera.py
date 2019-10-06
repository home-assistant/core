"""This component provides basic support for Foscam IP cameras."""
import logging
from asyncio import sleep

import voluptuous as vol

from homeassistant.components.camera import Camera, PLATFORM_SCHEMA, SUPPORT_STREAM
from homeassistant.const import (
    CONF_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_PORT,
    ATTR_ENTITY_ID,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_extract_entity_ids

from libpyfoscam import FoscamCamera


_LOGGER = logging.getLogger(__name__)

CONF_IP = "ip"
CONF_RTSP_PORT = "rtsp_port"

DEFAULT_NAME = "Foscam Camera"
DEFAULT_PORT = 88

FOSCAM_COMM_ERROR = -8

DOMAIN = "foscam"

SERVICE_PTZ = "ptz"
ATTR_MOVEMENT = "movement"
ATTR_TRAVELTIME = "travel_time"

DEFAULT_TRAVELTIME = 0.125

DIR_UP = "UP"
DIR_DOWN = "DOWN"
DIR_LEFT = "LEFT"
DIR_RIGHT = "RIGHT"

DIR_TOPLEFT = "TOP_LEFT"
DIR_TOPRIGHT = "TOP_RIGHT"
DIR_BOTTOMLEFT = "BOTTOM_LEFT"
DIR_BOTTOMRIGHT = "BOTTOM_RIGHT"

FOSCAM_DATA = "foscam"
ENTITIES = "entities"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_RTSP_PORT): cv.port,
    }
)

SERVICE_PTZ_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_MOVEMENT): vol.In(
            [
                DIR_UP,
                DIR_DOWN,
                DIR_LEFT,
                DIR_RIGHT,
                DIR_TOPLEFT,
                DIR_TOPRIGHT,
                DIR_BOTTOMLEFT,
                DIR_BOTTOMRIGHT,
            ]
        ),
        vol.Optional(ATTR_TRAVELTIME, default=DEFAULT_TRAVELTIME): cv.small_float,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a Foscam IP Camera."""

    async def async_handle_ptz(service):
        """Handle PTZ service call."""
        movement = service.data[ATTR_MOVEMENT]
        travel_time = service.data[ATTR_TRAVELTIME]
        entity_ids = await async_extract_entity_ids(hass, service)

        if not entity_ids:
            return

        _LOGGER.debug("Moving '%s' camera(s): %s", movement, entity_ids)

        all_cameras = hass.data[FOSCAM_DATA][ENTITIES]
        target_cameras = [
            camera for camera in all_cameras if camera.entity_id in entity_ids
        ]

        for camera in target_cameras:
            await camera.async_perform_ptz(movement, travel_time)

    hass.services.async_register(
        DOMAIN, SERVICE_PTZ, async_handle_ptz, schema=SERVICE_PTZ_SCHEMA
    )

    async_add_entities([FoscamCam(config)])


class FoscamCam(Camera):
    """An implementation of a Foscam IP camera."""

    def __init__(self, device_info):
        """Initialize a Foscam camera."""
        super().__init__()

        ip_address = device_info[CONF_IP]
        port = device_info[CONF_PORT]
        self._username = device_info[CONF_USERNAME]
        self._password = device_info[CONF_PASSWORD]
        self._name = device_info[CONF_NAME]
        self._motion_status = False

        self._foscam_session = FoscamCamera(
            ip_address, port, self._username, self._password, verbose=False
        )

        self._rtsp_port = device_info.get(CONF_RTSP_PORT)
        if not self._rtsp_port:
            result, response = self._foscam_session.get_port_info()
            if result == 0:
                self._rtsp_port = response.get("rtspPort") or response.get("mediaPort")

    async def async_added_to_hass(self):
        """Handle entity addition to hass."""
        self.hass.data.setdefault(FOSCAM_DATA, {})
        self.hass.data[FOSCAM_DATA].setdefault(ENTITIES, [])
        self.hass.data[FOSCAM_DATA][ENTITIES].append(self)

    def camera_image(self):
        """Return a still image response from the camera."""
        # Send the request to snap a picture and return raw jpg data
        # Handle exception if host is not reachable or url failed
        result, response = self._foscam_session.snap_picture_2()
        if result == FOSCAM_COMM_ERROR:
            return None

        return response

    @property
    def supported_features(self):
        """Return supported features."""
        if self._rtsp_port:
            return SUPPORT_STREAM
        return 0

    async def stream_source(self):
        """Return the stream source."""
        if self._rtsp_port:
            return "rtsp://{}:{}@{}:{}/videoMain".format(
                self._username,
                self._password,
                self._foscam_session.host,
                self._rtsp_port,
            )
        return None

    @property
    def motion_detection_enabled(self):
        """Camera Motion Detection Status."""
        return self._motion_status

    def enable_motion_detection(self):
        """Enable motion detection in camera."""
        try:
            ret = self._foscam_session.enable_motion_detection()
            self._motion_status = ret == FOSCAM_COMM_ERROR
        except TypeError:
            _LOGGER.debug("Communication problem")
            self._motion_status = False

    def disable_motion_detection(self):
        """Disable motion detection."""
        try:
            ret = self._foscam_session.disable_motion_detection()
            self._motion_status = ret == FOSCAM_COMM_ERROR
        except TypeError:
            _LOGGER.debug("Communication problem")
            self._motion_status = False

    async def async_perform_ptz(self, movement, travel_time):
        """Perform a PTZ action on the camera."""
        _LOGGER.debug("PTZ action '%s' on %s", movement, self._name)

        ret, _ = await self.hass.async_add_executor_job(
            {
                DIR_UP: self._foscam_session.ptz_move_up,
                DIR_DOWN: self._foscam_session.ptz_move_down,
                DIR_LEFT: self._foscam_session.ptz_move_left,
                DIR_RIGHT: self._foscam_session.ptz_move_right,
                DIR_TOPLEFT: self._foscam_session.ptz_move_top_left,
                DIR_TOPRIGHT: self._foscam_session.ptz_move_top_right,
                DIR_BOTTOMLEFT: self._foscam_session.ptz_move_bottom_left,
                DIR_BOTTOMRIGHT: self._foscam_session.ptz_move_bottom_right,
            }[movement]
        )

        if ret != 0:
            _LOGGER.error("Error moving %s '%s': %s", movement, self._name, ret)
            return

        await sleep(travel_time)

        ret, _ = await self.hass.async_add_executor_job(
            self._foscam_session.ptz_stop_run
        )

        if ret != 0:
            _LOGGER.error("Error stopping movement on '%s': %s", self._name, ret)
            return

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
