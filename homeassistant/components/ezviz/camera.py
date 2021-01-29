"""Support ezviz camera devices."""
import asyncio
from datetime import timedelta
import logging
from typing import Callable, List

from haffmpeg.tools import IMAGE_JPEG, ImageFrame
from pyezviz.DeviceSwitchType import DeviceSwitchType
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, SUPPORT_STREAM, Camera
from homeassistant.components.ffmpeg import DATA_FFMPEG

# from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_CAMERAS,
    ATTR_DIRECTION,
    ATTR_ENABLE,
    ATTR_INFRARED_LIGHT,
    ATTR_LEVEL,
    ATTR_LIGHT,
    ATTR_MOBILE_TRACKING,
    ATTR_PRIVACY,
    ATTR_SLEEP,
    ATTR_SOUND,
    ATTR_SPEED,
    ATTR_SWITCH,
    ATTR_TYPE,
    CONF_FFMPEG_ARGUMENTS,
    DATA_COORDINATOR,
    DEFAULT_CAMERA_USERNAME,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_RTSP_PORT,
    DIR_DOWN,
    DIR_LEFT,
    DIR_RIGHT,
    DIR_UP,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import EzvizDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_SESSION_RENEW = timedelta(seconds=90)

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_FFMPEG_ARGUMENTS),
    PLATFORM_SCHEMA.extend(
        {
            vol.Optional(
                CONF_FFMPEG_ARGUMENTS, default=DEFAULT_FFMPEG_ARGUMENTS
            ): cv.string
        }
    ),
)


async def async_setup_entry(
    hass, entry, async_add_entities: Callable[[List[Entity], bool], None]
) -> None:
    """Set up Ezviz cameras based on a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    conf_cameras = hass.data[DOMAIN]["config"][ATTR_CAMERAS]
    ffmpeg_arguments = entry.options.get(
        CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS
    )
    camera_entities = []

    """Setup Services"""

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        "ezviz_ptz",
        {
            vol.Required(ATTR_DIRECTION): vol.In(
                [DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT]
            ),
            vol.Required(ATTR_SPEED): cv.positive_int,
        },
        "perform_ezviz_ptz",
    )

    platform.async_register_entity_service(
        "ezviz_switch_set",
        {
            vol.Required(ATTR_SWITCH): vol.In(
                [
                    ATTR_LIGHT,
                    ATTR_SOUND,
                    ATTR_INFRARED_LIGHT,
                    ATTR_PRIVACY,
                    ATTR_SLEEP,
                    ATTR_MOBILE_TRACKING,
                ]
            ),
            vol.Required(ATTR_ENABLE): cv.positive_int,
        },
        "perform_ezviz_switch_set",
    )

    platform.async_register_entity_service(
        "ezviz_wake_device", {}, "perform_ezviz_wake_device"
    )

    platform.async_register_entity_service(
        "ezviz_alarm_sound",
        {vol.Required(ATTR_LEVEL): cv.positive_int},
        "perform_ezviz_alarm_sound",
    )

    platform.async_register_entity_service(
        "ezviz_set_alarm_detection_sensibility",
        {
            vol.Required(ATTR_LEVEL): cv.positive_int,
            vol.Required(ATTR_TYPE): cv.positive_int,
        },
        "perform_ezviz_set_alarm_detection_sensibility",
    )

    for idx, camera in enumerate(coordinator.data):

        # There seem to be a bug related to localRtspPort in Ezviz API...
        local_rtsp_port = DEFAULT_RTSP_PORT
        if camera["local_rtsp_port"] != 0:
            local_rtsp_port = camera["local_rtsp_port"]

        if camera["serial"] in conf_cameras:
            camera_username = conf_cameras[camera["serial"]][CONF_USERNAME]
            camera_password = conf_cameras[camera["serial"]][CONF_PASSWORD]
            camera_rtsp_stream = f"rtsp://{camera_username}:{camera_password}@{camera['local_ip']}:{local_rtsp_port}{ffmpeg_arguments}"
            _LOGGER.debug(
                "Camera %s source stream: %s", camera["serial"], camera_rtsp_stream
            )

        else:
            camera_username = DEFAULT_CAMERA_USERNAME
            camera_password = ""
            camera_rtsp_stream = ""
            _LOGGER.info(
                "Found camera with serial %s without configuration. Add it to configuration.yaml to see the camera stream",
                camera["serial"],
            )

        camera_entities.append(
            EzvizCamera(
                hass,
                coordinator,
                idx,
                camera_username,
                camera_password,
                camera_rtsp_stream,
                local_rtsp_port,
                ffmpeg_arguments,
            )
        )

    async_add_entities(camera_entities)


class EzvizCamera(CoordinatorEntity, Camera, RestoreEntity):
    """An implementation of a Ezviz security camera."""

    def __init__(
        self,
        hass,
        coordinator,
        idx,
        camera_username,
        camera_password,
        camera_rtsp_stream,
        local_rtsp_port,
        ffmpeg_arguments,
    ):
        """Initialize a Ezviz security camera."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self._username = camera_username
        self._password = camera_password
        self._rtsp_stream = camera_rtsp_stream
        self._idx = idx
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._local_rtsp_port = local_rtsp_port
        self._ffmpeg_arguments = ffmpeg_arguments

        self._serial = self.coordinator.data[self._idx]["serial"]
        self._name = self.coordinator.data[self._idx]["name"]
        self._local_ip = self.coordinator.data[self._idx]["local_ip"]

    @property
    def extra_state_attributes(self):
        """Return the Ezviz-specific camera state attributes."""
        return {
            # Camera firmware version
            "sw_version": self.coordinator.data[self._idx]["version"],
            # Camera firmware version update available?
            "upgrade_available": self.coordinator.data[self._idx]["upgrade_available"],
            # if privacy == true, the device closed the lid or did a 180� tilt
            "privacy": self.coordinator.data[self._idx]["privacy"],
            # if sleep == true, the device is sleeping?
            "sleep": self.coordinator.data[self._idx]["sleep"],
            # is the camera listening ?
            "audio": self.coordinator.data[self._idx]["audio"],
            # infrared led on ?
            "ir_led": self.coordinator.data[self._idx]["ir_led"],
            # state led on  ?
            "state_led": self.coordinator.data[self._idx]["state_led"],
            # if true, the camera will move automatically to follow movements
            "follow_move": self.coordinator.data[self._idx]["follow_move"],
            # if true, notification schedule(s) are configured
            "alarm_schedules_enabled": self.coordinator.data[self._idx][
                "alarm_schedules_enabled"
            ],
            # if true, if some movement is detected, the camera makes some sound
            "alarm_sound_mod": self.coordinator.data[self._idx]["alarm_sound_mod"],
            # are the camera's stored videos/images encrypted?
            "encrypted": self.coordinator.data[self._idx]["encrypted"],
            # camera's local ip on local network
            "local_ip": self.coordinator.data[self._idx]["local_ip"],
            # camera's battery level if battery camera
            "battery_level": self.coordinator.data[self._idx]["battery_level"],
            # PIR sensor of camera. 0=open ir, and 1=closed ir
            "PIR_Status": self.coordinator.data[self._idx]["PIR_Status"],
            # from 1 to 6 or 1-100, the higher is the sensibility, the more it will detect small movements
            "detection_sensibility": self.coordinator.data[self._idx][
                "detection_sensibility"
            ],
            # last alarm trigger date and time
            "Last alarm triggered": self.coordinator.data[self._idx]["last_alarm_time"],
            # Seconds from alarm last trigger
            "Seconds_last_trigger": self.coordinator.data[self._idx][
                "Seconds_Last_Trigger"
            ],
            # Calculated motion trigger from alarm last trigger
            "motion_sensor": self.coordinator.data[self._idx]["Motion_Trigger"],
            # image of last event that triggered alarm
            "Last alarm image url": self.coordinator.data[self._idx]["last_alarm_pic"],
            # RTSP Stream
            "RTSP stream": self._rtsp_stream,
        }

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.data[self._idx]["status"]

    @property
    def supported_features(self):
        """Return supported features."""
        if self._rtsp_stream:
            return SUPPORT_STREAM
        return 0

    @property
    def name(self):
        """Return the name of this device."""
        return self._name

    @property
    def model(self):
        """Return the model of this device."""
        return self.coordinator.data[self._idx]["device_sub_category"]

    @property
    def brand(self):
        """Return the manufacturer of this device."""
        return MANUFACTURER

    @property
    def is_on(self):
        """Return true if on."""
        if self.coordinator.data[self._idx]["status"] == "1":
            return True
        else:
            return False

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self.coordinator.data[self._idx]["alarm_notify"]

    @property
    def motion_detection_enabled(self):
        """Camera Motion Detection Status."""
        return self.coordinator.data[self._idx]["alarm_notify"]

    def enable_motion_detection(self):
        """Enable motion detection in camera."""
        try:
            self.coordinator.EzvizClient.data_report(self._serial, 1)

        except TypeError:
            _LOGGER.debug("Communication problem")

    def disable_motion_detection(self):
        """Disable motion detection."""
        try:
            self.coordinator.EzvizClient.data_report(self._serial, 0)

        except TypeError:
            _LOGGER.debug("Communication problem")

    @property
    def unique_id(self):
        """Return the name of this camera."""
        return self._serial

    async def async_camera_image(self):
        """Return a frame from the camera stream."""
        ffmpeg = ImageFrame(self._ffmpeg.binary)

        image = await asyncio.shield(
            ffmpeg.get_image(
                self._rtsp_stream,
                output_format=IMAGE_JPEG,
                extra_cmd=self._ffmpeg_arguments,
            )
        )
        return image

    async def stream_source(self):
        """Return the stream source."""
        local_ip = self.coordinator.data[self._idx]["local_ip"]
        if self._local_rtsp_port:
            rtsp_stream_source = (
                f"rtsp://{self._username}:{self._password}@"
                f"{local_ip}:{self._local_rtsp_port}{self._ffmpeg_arguments}"
            )
            _LOGGER.debug(
                "Camera %s source stream: %s", self._serial, rtsp_stream_source
            )
            self._rtsp_stream = rtsp_stream_source
            return rtsp_stream_source
        return None

    def perform_ezviz_ptz(self, direction, speed):
        """Perform a PTZ action on the camera."""
        _LOGGER.debug("PTZ action '%s' on %s", direction, self._name)

        self.coordinator.EzvizClient.ptzControl(
            str(direction).upper(), self._serial, "START", speed
        )
        self.coordinator.EzvizClient.ptzControl(
            str(direction).upper(), self._serial, "STOP", speed
        )

    def perform_ezviz_switch_set(self, switch, enable):
        """Change a device switch on the camera."""
        _LOGGER.debug("Set EZVIZ Switch '%s' on %s", switch, self._name)
        service_switch = getattr(DeviceSwitchType, switch)

        self.coordinator.EzvizClient.switch_status(
            self._serial, service_switch.value, enable
        )

    def perform_ezviz_wake_device(self):
        """Basically wakes the camera by querying the device."""
        _LOGGER.debug("Wake camera '%s' on %s", self._name)

        self.coordinator.EzvizClient.get_detection_sensibility(self._serial)

    def perform_ezviz_alarm_sound(self, level):
        """Enable/Disable movement sound alarm."""
        _LOGGER.debug("Set alarm sound on camera '%s' on %s", self._name)

        self.coordinator.EzvizClient.alarm_sound(self._serial, level, 1)

    def perform_ezviz_set_alarm_detection_sensibility(self, level, type):
        """Set camera detection sensibility level service."""
        _LOGGER.debug(
            "Set detection sensibility level on camera '%s' on %s", self._name
        )

        self.coordinator.EzvizClient.detection_sensibility(self._serial, level, type)
