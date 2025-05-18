"""Component providing basic support for Foscam IP cameras."""

from __future__ import annotations

import asyncio

import voluptuous as vol

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_RTSP_PORT, CONF_STREAM, LOGGER, SERVICE_PTZ, SERVICE_PTZ_PRESET
from .coordinator import FoscamConfigEntry, FoscamCoordinator
from .entity import FoscamEntity

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FoscamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a Foscam IP camera from a config entry."""
    platform = entity_platform.async_get_current_platform()
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

    coordinator = config_entry.runtime_data

    async_add_entities([HassFoscamCamera(coordinator, config_entry)])


class HassFoscamCamera(FoscamEntity, Camera):
    """An implementation of a Foscam IP camera."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: FoscamCoordinator,
        config_entry: FoscamConfigEntry,
    ) -> None:
        """Initialize a Foscam camera."""
        super().__init__(coordinator, config_entry.entry_id)
        Camera.__init__(self)

        self._foscam_session = coordinator.session
        self._username = config_entry.data[CONF_USERNAME]
        self._password = config_entry.data[CONF_PASSWORD]
        self._stream = config_entry.data[CONF_STREAM]
        self._attr_unique_id = config_entry.entry_id
        self._rtsp_port = config_entry.data[CONF_RTSP_PORT]
        if self._rtsp_port:
            self._attr_supported_features = CameraEntityFeature.STREAM

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to hass."""
        # Get motion detection status

        await super().async_added_to_hass()

        ret, response = await self.hass.async_add_executor_job(
            self._foscam_session.get_motion_detect_config
        )

        if ret == -3:
            LOGGER.warning(
                (
                    "Can't get motion detection status, camera %s configured with"
                    " non-admin user"
                ),
                self.name,
            )

        elif ret != 0:
            LOGGER.error(
                "Error getting motion detection status of %s: %s", self.name, ret
            )

        else:
            self._attr_motion_detection_enabled = response == 1

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        # Send the request to snap a picture and return raw jpg data
        # Handle exception if host is not reachable or url failed
        result, response = self._foscam_session.snap_picture_2()
        if result != 0:
            return None

        return response

    async def stream_source(self) -> str | None:
        """Return the stream source."""
        if self._rtsp_port:
            return f"rtsp://{self._username}:{self._password}@{self._foscam_session.host}:{self._rtsp_port}/video{self._stream}"

        return None

    def enable_motion_detection(self) -> None:
        """Enable motion detection in camera."""
        try:
            ret = self._foscam_session.enable_motion_detection()

            if ret != 0:
                if ret == -3:
                    LOGGER.warning(
                        (
                            "Can't set motion detection status, camera %s configured"
                            " with non-admin user"
                        ),
                        self.name,
                    )
                return

            self._attr_motion_detection_enabled = True
        except TypeError:
            LOGGER.debug(
                (
                    "Failed enabling motion detection on '%s'. Is it supported by the"
                    " device?"
                ),
                self.name,
            )

    def disable_motion_detection(self) -> None:
        """Disable motion detection."""
        try:
            ret = self._foscam_session.disable_motion_detection()

            if ret != 0:
                if ret == -3:
                    LOGGER.warning(
                        (
                            "Can't set motion detection status, camera %s configured"
                            " with non-admin user"
                        ),
                        self.name,
                    )
                return

            self._attr_motion_detection_enabled = False
        except TypeError:
            LOGGER.debug(
                (
                    "Failed disabling motion detection on '%s'. Is it supported by the"
                    " device?"
                ),
                self.name,
            )

    async def async_perform_ptz(self, movement, travel_time):
        """Perform a PTZ action on the camera."""
        LOGGER.debug("PTZ action '%s' on %s", movement, self.name)

        movement_function = getattr(self._foscam_session, MOVEMENT_ATTRS[movement])

        ret, _ = await self.hass.async_add_executor_job(movement_function)

        if ret != 0:
            LOGGER.error("Error moving %s '%s': %s", movement, self.name, ret)
            return

        await asyncio.sleep(travel_time)

        ret, _ = await self.hass.async_add_executor_job(
            self._foscam_session.ptz_stop_run
        )

        if ret != 0:
            LOGGER.error("Error stopping movement on '%s': %s", self.name, ret)
            return

    async def async_perform_ptz_preset(self, preset_name):
        """Perform a PTZ preset action on the camera."""
        LOGGER.debug("PTZ preset '%s' on %s", preset_name, self.name)

        preset_function = getattr(self._foscam_session, PTZ_GOTO_PRESET_COMMAND)

        ret, _ = await self.hass.async_add_executor_job(preset_function, preset_name)

        if ret != 0:
            LOGGER.error(
                "Error moving to preset %s on '%s': %s", preset_name, self.name, ret
            )
            return
