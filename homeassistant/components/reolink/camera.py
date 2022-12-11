"""This component provides support for Reolink IP cameras."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    HOST,
    SERVICE_PTZ_CONTROL,
    SERVICE_SET_BACKLIGHT,
    SERVICE_SET_DAYNIGHT,
    SERVICE_SET_SENSITIVITY,
    SUPPORT_PTZ,
)
from .entity import ReolinkCoordinatorEntity
from .host import ReolinkHost

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Set up a Reolink IP Camera."""
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_SENSITIVITY,
        {
            vol.Required("sensitivity"): cv.positive_int,
            vol.Optional("preset"): cv.positive_int,
        },
        SERVICE_SET_SENSITIVITY,
    )

    platform.async_register_entity_service(
        SERVICE_SET_DAYNIGHT,
        {vol.Required("mode"): cv.string},
        SERVICE_SET_DAYNIGHT,
    )

    platform.async_register_entity_service(
        SERVICE_SET_BACKLIGHT,
        {vol.Required("mode"): cv.string},
        SERVICE_SET_BACKLIGHT,
    )

    platform.async_register_entity_service(
        SERVICE_PTZ_CONTROL,
        {
            vol.Required("command"): cv.string,
            vol.Optional("preset"): cv.positive_int,
            vol.Optional("speed"): cv.positive_int,
        },
        SERVICE_PTZ_CONTROL,
        [SUPPORT_PTZ],
    )

    host: ReolinkHost = hass.data[DOMAIN][config_entry.entry_id][HOST]

    cameras = []
    for channel in host.api.channels:
        streams = ["sub", "main", "snapshots"]
        if host.api.protocol == "rtmp":
            streams.append("ext")

        for stream in streams:
            cameras.append(ReolinkCamera(hass, config_entry, channel, stream))

    async_add_devices(cameras, update_before_add=True)


class ReolinkCamera(ReolinkCoordinatorEntity, Camera):
    """An implementation of a Reolink IP camera."""

    def __init__(self, hass, config, channel, stream):
        """Initialize Reolink camera stream."""
        ReolinkCoordinatorEntity.__init__(self, hass, config)
        Camera.__init__(self)

        self._channel = channel
        self._stream = stream

        self._attr_name = f"{self._host.api.camera_name(self._channel)} {self._stream}"
        self._attr_unique_id = (
            f"reolink_camera_{self._host.unique_id}_{self._channel}_{self._stream}"
        )
        self._attr_entity_registry_enabled_default = stream == "sub"

        self._ptz_commands = {
            "AUTO": "Auto",
            "DOWN": "Down",
            "FOCUSDEC": "FocusDec",
            "FOCUSINC": "FocusInc",
            "LEFT": "Left",
            "LEFTDOWN": "LeftDown",
            "LEFTUP": "LeftUp",
            "RIGHT": "Right",
            "RIGHTDOWN": "RightDown",
            "RIGHTUP": "RightUp",
            "STOP": "Stop",
            "TOPOS": "ToPos",
            "UP": "Up",
            "ZOOMDEC": "ZoomDec",
            "ZOOMINC": "ZoomInc",
        }
        self._daynight_modes = {
            "AUTO": "Auto",
            "COLOR": "Color",
            "BLACKANDWHITE": "Black&White",
        }

        self._backlight_modes = {
            "BACKLIGHTCONTROL": "BackLightControl",
            "DYNAMICRANGECONTROL": "DynamicRangeControl",
            "OFF": "Off",
        }

    @property
    def ptz_supported(self):
        """Supports ptz control."""
        return self._host.api.ptz_supported(self._channel)

    @property
    def supported_features(self) -> CameraEntityFeature:
        """Flag supported features."""
        features = int(CameraEntityFeature.STREAM)
        if self.ptz_supported:
            features += SUPPORT_PTZ
        return cast(CameraEntityFeature, features)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the extra state attributes."""
        attrs = {}

        if self._host.api.ptz_supported(self._channel):
            attrs["ptz_presets"] = self._host.api.ptz_presets(self._channel)

        for key, value in self._backlight_modes.items():
            if value == self._host.api.backlight_state(self._channel):
                attrs["backlight_state"] = key

        for key, value in self._daynight_modes.items():
            if value == self._host.api.daynight_state(self._channel):
                attrs["daynight_state"] = key

        if self._host.api.sensitivity_presets:
            attrs["sensitivity"] = self.get_sensitivity_presets()

        return attrs

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        return await self._host.api.get_stream_source(self._channel, self._stream)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        return await self._host.api.get_snapshot(self._channel)

    async def ptz_control(self, command, **kwargs):
        """Pass PTZ command to the camera."""
        if not self.ptz_supported:
            _LOGGER.error("PTZ is not supported on %s camera", self.name)
            return

        await self._host.api.set_ptz_command(
            self._channel, command=self._ptz_commands[command], **kwargs
        )

    def get_sensitivity_presets(self):
        """Get formatted sensitivity presets."""
        presets = []
        preset = {}

        for api_preset in self._host.api.sensitivity_presets(self._channel):
            preset["id"] = api_preset["id"]
            preset["sensitivity"] = api_preset["sensitivity"]

            time_string = f'{api_preset["beginHour"]}:{api_preset["beginMin"]}'
            begin = datetime.strptime(time_string, "%H:%M")
            preset["begin"] = begin.strftime("%H:%M")

            time_string = f'{api_preset["endHour"]}:{api_preset["endMin"]}'
            end = datetime.strptime(time_string, "%H:%M")
            preset["end"] = end.strftime("%H:%M")

            presets.append(preset.copy())

        return presets

    async def set_sensitivity(self, sensitivity, **kwargs):
        """Set the sensitivity to the camera."""
        if "preset" in kwargs:
            kwargs["preset"] += 1
        await self._host.api.set_sensitivity(self._channel, value=sensitivity, **kwargs)

    async def set_daynight(self, mode):
        """Set the day and night mode to the camera."""
        await self._host.api.set_daynight(
            self._channel, value=self._daynight_modes[mode]
        )

    async def set_backlight(self, mode):
        """Set the backlight mode to the camera."""
        await self._host.api.set_backlight(
            self._channel, value=self._backlight_modes[mode]
        )
