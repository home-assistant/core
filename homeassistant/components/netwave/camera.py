"""The NetWave camera component."""
import logging
import time

from netwave import NetwaveCamera as NetwaveCameraAPI
import requests
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ID,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv

from ...config_entries import ConfigEntry
from ...helpers import entity_platform
from ...helpers.typing import HomeAssistantType
from .const import (
    ATTR_BRIGHTNESS,
    ATTR_CONTRAST,
    ATTR_MODE,
    ATTR_MOVE_DURATION,
    ATTR_ORIENTATION,
    ATTR_PARAMETER,
    ATTR_RESOLUTION,
    ATTR_VALUE,
    COMMAND_FACTORY_RESET_CAMERA,
    COMMAND_MOVE_CENTER,
    COMMAND_MOVE_DOWN,
    COMMAND_MOVE_DOWN_LEFT,
    COMMAND_MOVE_DOWN_RIGHT,
    COMMAND_MOVE_LEFT,
    COMMAND_MOVE_RIGHT,
    COMMAND_MOVE_UP,
    COMMAND_MOVE_UP_LEFT,
    COMMAND_MOVE_UP_RIGHT,
    COMMAND_PATROL_HORIZONTAL,
    COMMAND_PATROL_VERTICAL,
    COMMAND_PELCO_PATROL_HORIZONTAL,
    COMMAND_PELCO_STOP_PATROL_HORIZONTAL,
    COMMAND_RECALL_PRESET,
    COMMAND_RESTART_CAMERA,
    COMMAND_SET_PRESET,
    COMMAND_STOP_MOVEMENT,
    COMMAND_STOP_PATROL_HORIZONTAL,
    COMMAND_STOP_PATROL_VERTICAL,
    COMMAND_TURN_IO_OFF,
    COMMAND_TURN_IO_ON,
    CONF_FRAMERATE,
    CONF_HORIZONTAL_MIRROR,
    CONF_MOVE_DURATION,
    CONF_VERTICAL_MIRROR,
    DEFAULT_FRAMERATE,
    DEFAULT_MOVE_DURATION,
    DEFAULT_NAME,
    DEFAULT_PASSWORD,
    DEFAULT_PRESET,
    DEFAULT_TIMEOUT,
    DEFAULT_USERNAME,
    PARAMETER_BRIGHTNESS,
    PARAMETER_CONTRAST,
    PARAMETER_MODE,
    PARAMETER_ORIENTATION,
    PARAMETER_RESOLUTION,
    SERVICE_COMMAND,
    SERVICE_INFO,
    SERVICE_PARAMETER,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_VERTICAL_MIRROR, default=False): cv.boolean,
        vol.Optional(CONF_HORIZONTAL_MIRROR, default=False): cv.boolean,
        vol.Optional(CONF_FRAMERATE, default=DEFAULT_FRAMERATE): cv.positive_int,
        vol.Optional(CONF_MOVE_DURATION, default=DEFAULT_MOVE_DURATION): vol.Any(
            int, float
        ),
    }
)

SERVICE_COMMAND_SCHEMA = {
    vol.Required(ATTR_COMMAND): vol.In(
        [
            COMMAND_STOP_MOVEMENT,
            COMMAND_MOVE_LEFT,
            COMMAND_MOVE_RIGHT,
            COMMAND_MOVE_UP,
            COMMAND_MOVE_DOWN,
            COMMAND_MOVE_UP_LEFT,
            COMMAND_MOVE_UP_RIGHT,
            COMMAND_MOVE_DOWN_LEFT,
            COMMAND_MOVE_DOWN_RIGHT,
            COMMAND_MOVE_CENTER,
            COMMAND_PATROL_VERTICAL,
            COMMAND_STOP_PATROL_VERTICAL,
            COMMAND_PATROL_HORIZONTAL,
            COMMAND_STOP_PATROL_HORIZONTAL,
            COMMAND_PELCO_PATROL_HORIZONTAL,
            COMMAND_PELCO_STOP_PATROL_HORIZONTAL,
            COMMAND_TURN_IO_ON,
            COMMAND_TURN_IO_OFF,
            COMMAND_SET_PRESET,
            COMMAND_RECALL_PRESET,
            COMMAND_RESTART_CAMERA,
            COMMAND_FACTORY_RESET_CAMERA,
        ]
    ),
    vol.Optional(ATTR_PARAMETER, default=DEFAULT_PRESET): vol.Range(1, 15),
    vol.Optional(ATTR_MOVE_DURATION, default=None): vol.Any(int, float, None),
}

SERVICE_PARAMETER_SCHEMA = {
    vol.Required(ATTR_PARAMETER): vol.In(
        [
            PARAMETER_BRIGHTNESS,
            PARAMETER_CONTRAST,
            PARAMETER_MODE,
            PARAMETER_ORIENTATION,
            PARAMETER_RESOLUTION,
        ]
    ),
    vol.Required(ATTR_VALUE): vol.Or(cv.string, cv.positive_int),
}


async def _async_setup_camera(hass, config, async_add_entities, entry=None):
    """Set up camera."""
    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_COMMAND, SERVICE_COMMAND_SCHEMA, "send_command"
    )
    platform.async_register_entity_service(
        SERVICE_PARAMETER, SERVICE_PARAMETER_SCHEMA, "send_parameter"
    )
    platform.async_register_entity_service(SERVICE_INFO, {}, "update_info")

    camera = NetwaveCamera(config)

    if entry is not None:

        async def update_listener(hass, entry):
            await camera.update_listener(entry)

        def listener_ref():
            return update_listener

        entry.update_listeners = [listener_ref]

    async_add_entities([camera], True)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up a NetWave camera from config-flow."""
    _LOGGER.debug(
        "Create camera from config-flow, config: %s, options: %s",
        entry.data,
        entry.options,
    )
    config = entry.data.copy()
    config.update(entry.options)
    await _async_setup_camera(hass, entry.data, async_add_entities, entry)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a NetWave camera from config file."""
    _LOGGER.debug("Create camera from config file: %s", config)
    await _async_setup_camera(hass, config, async_add_entities)


class NetwaveCamera(Camera):
    """Representation of a NetWave camera."""

    def __init__(self, config):
        """Initialize Netwave camera."""

        self._info = None
        self._last_image = None
        self._setup(config)

        super().__init__()

    def _setup(self, config):
        """Set up the camera."""
        self._name = config[CONF_NAME]
        self._info = None
        self._orientation = (
            int(config[CONF_VERTICAL_MIRROR]) + int(config[CONF_HORIZONTAL_MIRROR]) * 2
        )
        self._camera = NetwaveCameraAPI(
            config[CONF_ADDRESS],
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            config[CONF_TIMEOUT],
        )
        self._frame_interval = 1 / config[CONF_FRAMERATE]
        self._move_duration = config[CONF_MOVE_DURATION]

    async def async_added_to_hass(self):
        """Register camera with integration."""

    @property
    def should_poll(self):
        """Poll to update video settings."""
        return True

    @property
    def frame_interval(self):
        """Return the interval between frames of the stream."""
        return self._frame_interval

    def camera_image(self):
        """Return bytes of camera image."""
        try:
            self._last_image = self._camera.get_snapshot()
        except requests.Timeout:
            _LOGGER.error("Timeout getting camera image from %s", self._name)
        except requests.RequestException as err:
            _LOGGER.error("Error updating image from camera %s: %s", self.name, err)
        return self._last_image

    @property
    def unique_id(self):
        """Get the camera's unique id."""
        if self.camera_info is None:
            _LOGGER.warning(
                "Unique ID was retrieved before camera connection, will instead use %s instead",
                self._name,
            )
            return self.name
        return self.camera_info[ATTR_ID]

    @property
    def name(self):
        """Return the name of this device."""
        return self._name

    def update(self):
        """Update camera values."""
        try:
            if self.camera_info is None:
                self._camera.update_info()
                self._camera.update_video_settings()
                self._camera.set_orientation(self._orientation)
                self._info = self._camera.get_info()
            else:
                self._camera.update_video_settings()
        except requests.Timeout:
            _LOGGER.error("Timeout getting values from %s", self._name)
        except requests.RequestException as err:
            _LOGGER.error("Error updating values from camera %s: %s", self.name, err)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        attributes = super().state_attributes
        if self.camera_info is not None:
            attributes[ATTR_BRIGHTNESS] = self.brightness
            attributes[ATTR_CONTRAST] = self.contrast
            attributes[ATTR_MODE] = self.mode
            attributes[ATTR_RESOLUTION] = self.resolution
            attributes[ATTR_ORIENTATION] = self.orientation
        return attributes

    @property
    def brightness(self):
        """Return the camera's brightness."""
        return self._camera.get_brightness()

    @property
    def contrast(self):
        """Return the camera's contrast."""
        return self._camera.get_contrast()

    @property
    def resolution(self):
        """Return the camera's resolution."""
        return self._camera.get_resolution()

    @property
    def mode(self):
        """Return the camera's mode."""
        return self._camera.get_mode()

    @property
    def orientation(self):
        """Return the camera's orientation."""
        return self._camera.get_orientation()

    @property
    def move_duration(self):
        """Return the duration of movement commands."""
        return self._move_duration

    @property
    def camera_info(self):
        """Return a dictionary of the camera's info."""
        return self._info

    def send_command(self, command, parameter, move_duration):
        """Send a command to the camera."""
        _LOGGER.debug(
            "Sending command %s %sto camera %s",
            command,
            ": " + str(parameter) if "preset" in command else "",
            self.name,
        )
        func = getattr(self._camera, command)
        try:
            if "preset" in command:
                func(int(parameter))
            else:
                func()
            duration = self.move_duration if move_duration is None else move_duration
            if "move_" in command and "center" not in command and duration > 0:
                time.sleep(duration)
                self._camera.stop_movement()
        except requests.Timeout:
            _LOGGER.error("Timeout sending command %s", self._name)
        except requests.RequestException as err:
            _LOGGER.error("Error sending command to camera %s: %s", self.name, err)

    def send_parameter(self, parameter, value):
        """Update a parameter on the camera."""
        _LOGGER.debug(
            "Updating parameter %s to %s for camera %s", parameter, value, self._name
        )
        try:
            getattr(self._camera, "set_" + parameter)(int(value))
        except requests.Timeout:
            _LOGGER.error("Timeout sending parameter to %s", self._name)
        except requests.RequestException as err:
            _LOGGER.error("Error sending parameter to camera %s: %s", self.name, err)

    def get_info(self):
        """Update and return general info for camera."""
        _LOGGER.debug("Updating info for camera %s", self.name)
        try:
            self.update_info()
        except requests.Timeout:
            _LOGGER.error("Timeout getting info from %s", self._name)
        except requests.RequestException as err:
            _LOGGER.error("Error updating info from camera %s: %s", self.name, err)
        self._info = self._camera.get_info()

    def update_info(self):
        """Update info for camera."""
        self._camera.update_info()

    async def update_listener(self, entry):
        """Update options."""
        config = entry.data.copy()
        config.update(entry.options)
        self._setup(config)
        await self.hass.async_add_executor_job(self.update)
