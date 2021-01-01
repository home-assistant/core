"""This component provides basic support for Foscam IP cameras."""
import asyncio
import logging

from libpyfoscam import FoscamCamera
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, SUPPORT_STREAM, Camera
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv, entity_platform

from .const import DATA as FOSCAM_DATA, ENTITIES as FOSCAM_ENTITIES

_LOGGER = logging.getLogger(__name__)

CONF_IP = "ip"
CONF_RTSP_PORT = "rtsp_port"

DEFAULT_NAME = "Foscam Camera"
DEFAULT_PORT = 88

SERVICE_PTZ = "ptz"
ATTR_MOVEMENT = "movement"
ATTR_TRAVELTIME = "travel_time"

DEFAULT_TRAVELTIME = 0.125

DIR_UP = "up"
DIR_DOWN = "down"
DIR_LEFT = "left"
DIR_RIGHT = "right"

DIR_TOPLEFT = "top_left"
DIR_TOPRIGHT = "top_right"
DIR_BOTTOMLEFT = "bottom_left"
DIR_BOTTOMRIGHT = "bottom_right"

MOVEMENT_ATTRS = {
    DIR_UP: "ptz_move_up",
    DIR_DOWN: "ptz_move_down",
    DIR_LEFT: "ptz_move_left",
    DIR_RIGHT: "ptz_move_right",
    DIR_TOPLEFT: "ptz_move_top_left",
    DIR_TOPRIGHT: "ptz_move_top_right",
    DIR_BOTTOMLEFT: "ptz_move_bottom_left",
    DIR_BOTTOMRIGHT: "ptz_move_bottom_right",
}

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
    platform = entity_platform.current_platform.get()
    assert platform is not None
    platform.async_register_entity_service(
        "ptz",
        {
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
        },
        "async_perform_ptz",
    )

    camera = FoscamCamera(
        config[CONF_IP],
        config[CONF_PORT],
        config[CONF_USERNAME],
        config[CONF_PASSWORD],
        verbose=False,
    )

    rtsp_port = config.get(CONF_RTSP_PORT)
    if not rtsp_port:
        ret, response = await hass.async_add_executor_job(camera.get_port_info)

        if ret == 0:
            rtsp_port = response.get("rtspPort") or response.get("mediaPort")

    ret, response = await hass.async_add_executor_job(camera.get_motion_detect_config)

    motion_status = False
    if ret != 0 and response == 1:
        motion_status = True

    async_add_entities(
        [
            HassFoscamCamera(
                camera,
                config[CONF_NAME],
                config[CONF_USERNAME],
                config[CONF_PASSWORD],
                rtsp_port,
                motion_status,
            )
        ]
    )


class HassFoscamCamera(Camera):
    """An implementation of a Foscam IP camera."""

    def __init__(self, camera, name, username, password, rtsp_port, motion_status):
        """Initialize a Foscam camera."""
        super().__init__()

        self._foscam_session = camera
        self._name = name
        self._username = username
        self._password = password
        self._rtsp_port = rtsp_port
        self._motion_status = motion_status

    async def async_added_to_hass(self):
        """Handle entity addition to hass."""
        entities = self.hass.data.setdefault(FOSCAM_DATA, {}).setdefault(
            FOSCAM_ENTITIES, []
        )
        entities.append(self)

    def camera_image(self):
        """Return a still image response from the camera."""
        # Send the request to snap a picture and return raw jpg data
        # Handle exception if host is not reachable or url failed
        result, response = self._foscam_session.snap_picture_2()
        if result != 0:
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
            return f"rtsp://{self._username}:{self._password}@{self._foscam_session.host}:{self._rtsp_port}/videoMain"
        return None

    @property
    def motion_detection_enabled(self):
        """Camera Motion Detection Status."""
        return self._motion_status

    def enable_motion_detection(self):
        """Enable motion detection in camera."""
        try:
            ret = self._foscam_session.enable_motion_detection()

            if ret != 0:
                return

            self._motion_status = True
        except TypeError:
            _LOGGER.debug("Communication problem")

    def disable_motion_detection(self):
        """Disable motion detection."""
        try:
            ret = self._foscam_session.disable_motion_detection()

            if ret != 0:
                return

            self._motion_status = False
        except TypeError:
            _LOGGER.debug("Communication problem")

    async def async_perform_ptz(self, movement, travel_time):
        """Perform a PTZ action on the camera."""
        _LOGGER.debug("PTZ action '%s' on %s", movement, self._name)

        movement_function = getattr(self._foscam_session, MOVEMENT_ATTRS[movement])

        ret, _ = await self.hass.async_add_executor_job(movement_function)

        if ret != 0:
            _LOGGER.error("Error moving %s '%s': %s", movement, self._name, ret)
            return

        await asyncio.sleep(travel_time)

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
