"""This component provides basic support for Foscam IP cameras."""
import asyncio

from libpyfoscam import FoscamCamera
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, SUPPORT_STREAM, Camera
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv, entity_platform

from .const import (
    CONF_RTSP_PORT,
    CONF_STREAM,
    DOMAIN,
    LOGGER,
    SERVICE_PTZ,
    SERVICE_PTZ_PRESET,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required("ip"): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_NAME, default="Foscam Camera"): cv.string,
        vol.Optional(CONF_PORT, default=88): cv.port,
        vol.Optional(CONF_RTSP_PORT): cv.port,
    }
)

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

DEFAULT_TRAVELTIME = 0.125

ATTR_MOVEMENT = "movement"
ATTR_TRAVELTIME = "travel_time"
ATTR_PRESET_NAME = "preset_name"

PTZ_GOTO_PRESET_COMMAND = "ptz_goto_preset"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a Foscam IP Camera."""
    LOGGER.warning(
        "Loading foscam via platform config is deprecated, it will be automatically imported. Please remove it afterwards."
    )

    config_new = {
        CONF_NAME: config[CONF_NAME],
        CONF_HOST: config["ip"],
        CONF_PORT: config[CONF_PORT],
        CONF_USERNAME: config[CONF_USERNAME],
        CONF_PASSWORD: config[CONF_PASSWORD],
        CONF_STREAM: "Main",
        CONF_RTSP_PORT: config.get(CONF_RTSP_PORT, 554),
    }

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config_new
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a Foscam IP camera from a config entry."""
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        SERVICE_PTZ,
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

    platform.async_register_entity_service(
        SERVICE_PTZ_PRESET,
        {
            vol.Required(ATTR_PRESET_NAME): cv.string,
        },
        "async_perform_ptz_preset",
    )

    camera = FoscamCamera(
        config_entry.data[CONF_HOST],
        config_entry.data[CONF_PORT],
        config_entry.data[CONF_USERNAME],
        config_entry.data[CONF_PASSWORD],
        verbose=False,
    )

    async_add_entities([HassFoscamCamera(camera, config_entry)])


class HassFoscamCamera(Camera):
    """An implementation of a Foscam IP camera."""

    def __init__(self, camera, config_entry):
        """Initialize a Foscam camera."""
        super().__init__()

        self._foscam_session = camera
        self._name = config_entry.title
        self._username = config_entry.data[CONF_USERNAME]
        self._password = config_entry.data[CONF_PASSWORD]
        self._stream = config_entry.data[CONF_STREAM]
        self._unique_id = config_entry.entry_id
        self._rtsp_port = config_entry.data[CONF_RTSP_PORT]
        self._motion_status = False

    async def async_added_to_hass(self):
        """Handle entity addition to hass."""
        # Get motion detection status
        ret, response = await self.hass.async_add_executor_job(
            self._foscam_session.get_motion_detect_config
        )

        if ret == -3:
            LOGGER.info(
                "Can't get motion detection status, camera %s configured with non-admin user",
                self._name,
            )

        elif ret != 0:
            LOGGER.error(
                "Error getting motion detection status of %s: %s", self._name, ret
            )

        else:
            self._motion_status = response == 1

    @property
    def unique_id(self):
        """Return the entity unique ID."""
        return self._unique_id

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

        return None

    async def stream_source(self):
        """Return the stream source."""
        if self._rtsp_port:
            return f"rtsp://{self._username}:{self._password}@{self._foscam_session.host}:{self._rtsp_port}/video{self._stream}"

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
                if ret == -3:
                    LOGGER.info(
                        "Can't set motion detection status, camera %s configured with non-admin user",
                        self._name,
                    )
                return

            self._motion_status = True
        except TypeError:
            LOGGER.debug(
                "Failed enabling motion detection on '%s'. Is it supported by the device?",
                self._name,
            )

    def disable_motion_detection(self):
        """Disable motion detection."""
        try:
            ret = self._foscam_session.disable_motion_detection()

            if ret != 0:
                if ret == -3:
                    LOGGER.info(
                        "Can't set motion detection status, camera %s configured with non-admin user",
                        self._name,
                    )
                return

            self._motion_status = False
        except TypeError:
            LOGGER.debug(
                "Failed disabling motion detection on '%s'. Is it supported by the device?",
                self._name,
            )

    async def async_perform_ptz(self, movement, travel_time):
        """Perform a PTZ action on the camera."""
        LOGGER.debug("PTZ action '%s' on %s", movement, self._name)

        movement_function = getattr(self._foscam_session, MOVEMENT_ATTRS[movement])

        ret, _ = await self.hass.async_add_executor_job(movement_function)

        if ret != 0:
            LOGGER.error("Error moving %s '%s': %s", movement, self._name, ret)
            return

        await asyncio.sleep(travel_time)

        ret, _ = await self.hass.async_add_executor_job(
            self._foscam_session.ptz_stop_run
        )

        if ret != 0:
            LOGGER.error("Error stopping movement on '%s': %s", self._name, ret)
            return

    async def async_perform_ptz_preset(self, preset_name):
        """Perform a PTZ preset action on the camera."""
        LOGGER.debug("PTZ preset '%s' on %s", preset_name, self._name)

        preset_function = getattr(self._foscam_session, PTZ_GOTO_PRESET_COMMAND)

        ret, _ = await self.hass.async_add_executor_job(preset_function, preset_name)

        if ret != 0:
            LOGGER.error(
                "Error moving to preset %s on '%s': %s", preset_name, self._name, ret
            )
            return

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
