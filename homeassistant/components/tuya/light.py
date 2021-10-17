"""Support for the Tuya lights."""
from __future__ import annotations

import json
import logging
from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    COLOR_MODE_ONOFF,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode

_LOGGER = logging.getLogger(__name__)

MIREDS_MAX = 500
MIREDS_MIN = 153

HSV_HA_HUE_MIN = 0
HSV_HA_HUE_MAX = 360
HSV_HA_SATURATION_MIN = 0
HSV_HA_SATURATION_MAX = 100

WORK_MODE_WHITE = "white"
WORK_MODE_COLOUR = "colour"

# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
TUYA_SUPPORT_TYPE = {
    "dj",  # Light
    "dd",  # Light strip
    "fwl",  # Ambient light
    "dc",  # Light string
    "jsq",  # Humidifier's light
    "xdd",  # Ceiling Light
    "xxj",  # Diffuser's light
    "fs",  # Fan
}

DEFAULT_HSV = {
    "h": {"min": 1, "scale": 0, "unit": "", "max": 360, "step": 1},
    "s": {"min": 1, "scale": 0, "unit": "", "max": 255, "step": 1},
    "v": {"min": 1, "scale": 0, "unit": "", "max": 255, "step": 1},
}

DEFAULT_HSV_V2 = {
    "h": {"min": 1, "scale": 0, "unit": "", "max": 360, "step": 1},
    "s": {"min": 1, "scale": 0, "unit": "", "max": 1000, "step": 1},
    "v": {"min": 1, "scale": 0, "unit": "", "max": 1000, "step": 1},
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya light dynamically through tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]):
        """Discover and add a discovered tuya light."""
        entities: list[TuyaLightEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if device and device.category in TUYA_SUPPORT_TYPE:
                entities.append(TuyaLightEntity(device, hass_data.device_manager))
        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaLightEntity(TuyaEntity, LightEntity):
    """Tuya light device."""

    def __init__(self, device: TuyaDevice, device_manager: TuyaDeviceManager) -> None:
        """Init TuyaHaLight."""
        self.dp_code_bright = DPCode.BRIGHT_VALUE
        self.dp_code_temp = DPCode.TEMP_VALUE
        self.dp_code_colour = DPCode.COLOUR_DATA

        for key in device.function:
            if key.startswith(DPCode.BRIGHT_VALUE):
                self.dp_code_bright = key
            elif key.startswith(DPCode.TEMP_VALUE):
                self.dp_code_temp = key
            elif key.startswith(DPCode.COLOUR_DATA):
                self.dp_code_colour = key

        super().__init__(device, device_manager)

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.device.status.get(DPCode.SWITCH_LED, False)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on or control the light."""
        commands = []
        work_mode = self._work_mode()
        _LOGGER.debug("light kwargs-> %s; work_mode %s", kwargs, work_mode)

        if (
            DPCode.LIGHT in self.device.status
            and DPCode.SWITCH_LED not in self.device.status
        ):
            commands += [{"code": DPCode.LIGHT, "value": True}]
        else:
            commands += [{"code": DPCode.SWITCH_LED, "value": True}]

        colour_data = self._get_hsv()
        v_range = self._tuya_hsv_v_range()
        send_colour_data = False

        if ATTR_HS_COLOR in kwargs:
            # hsv h
            colour_data["h"] = int(kwargs[ATTR_HS_COLOR][0])
            # hsv s
            ha_s = kwargs[ATTR_HS_COLOR][1]
            s_range = self._tuya_hsv_s_range()
            colour_data["s"] = int(
                self.remap(
                    ha_s,
                    HSV_HA_SATURATION_MIN,
                    HSV_HA_SATURATION_MAX,
                    s_range[0],
                    s_range[1],
                )
            )
            # hsv v
            ha_v = self.brightness
            colour_data["v"] = int(self.remap(ha_v, 0, 255, v_range[0], v_range[1]))

            commands += [
                {"code": self.dp_code_colour, "value": json.dumps(colour_data)}
            ]
            if work_mode != WORK_MODE_COLOUR:
                work_mode = WORK_MODE_COLOUR
                commands += [{"code": DPCode.WORK_MODE, "value": work_mode}]

        elif ATTR_COLOR_TEMP in kwargs:
            # temp color
            new_range = self._tuya_temp_range()
            color_temp = self.remap(
                self.max_mireds - kwargs[ATTR_COLOR_TEMP] + self.min_mireds,
                self.min_mireds,
                self.max_mireds,
                new_range[0],
                new_range[1],
            )
            commands += [{"code": self.dp_code_temp, "value": int(color_temp)}]

            # brightness
            ha_brightness = self.brightness
            new_range = self._tuya_brightness_range()
            tuya_brightness = self.remap(
                ha_brightness, 0, 255, new_range[0], new_range[1]
            )
            commands += [{"code": self.dp_code_bright, "value": int(tuya_brightness)}]

            if work_mode != WORK_MODE_WHITE:
                work_mode = WORK_MODE_WHITE
                commands += [{"code": DPCode.WORK_MODE, "value": WORK_MODE_WHITE}]

        if ATTR_BRIGHTNESS in kwargs:
            if work_mode == WORK_MODE_COLOUR:
                colour_data["v"] = int(
                    self.remap(kwargs[ATTR_BRIGHTNESS], 0, 255, v_range[0], v_range[1])
                )
                send_colour_data = True
            elif work_mode == WORK_MODE_WHITE:
                new_range = self._tuya_brightness_range()
                tuya_brightness = int(
                    self.remap(
                        kwargs[ATTR_BRIGHTNESS], 0, 255, new_range[0], new_range[1]
                    )
                )
                commands += [{"code": self.dp_code_bright, "value": tuya_brightness}]

        if send_colour_data:
            commands += [
                {"code": self.dp_code_colour, "value": json.dumps(colour_data)}
            ]

        self._send_command(commands)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        if (
            DPCode.LIGHT in self.device.status
            and DPCode.SWITCH_LED not in self.device.status
        ):
            commands = [{"code": DPCode.LIGHT, "value": False}]
        else:
            commands = [{"code": DPCode.SWITCH_LED, "value": False}]
        self._send_command(commands)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        old_range = self._tuya_brightness_range()
        brightness = self.device.status.get(self.dp_code_bright, 0)

        if self._work_mode().startswith(WORK_MODE_COLOUR):
            colour_json = self.device.status.get(self.dp_code_colour)
            if not colour_json:
                return None
            colour_data = json.loads(colour_json)
            v_range = self._tuya_hsv_v_range()
            hsv_v = colour_data.get("v", 0)
            return int(self.remap(hsv_v, v_range[0], v_range[1], 0, 255))

        return int(self.remap(brightness, old_range[0], old_range[1], 0, 255))

    def _tuya_brightness_range(self) -> tuple[int, int]:
        if self.dp_code_bright not in self.device.status:
            return 0, 255
        bright_item = self.device.function.get(self.dp_code_bright)
        if not bright_item:
            return 0, 255
        bright_value = json.loads(bright_item.values)
        return bright_value.get("min", 0), bright_value.get("max", 255)

    @property
    def color_mode(self) -> str:
        """Return the color_mode of the light."""
        work_mode = self._work_mode()
        if work_mode == WORK_MODE_WHITE:
            return COLOR_MODE_COLOR_TEMP
        return COLOR_MODE_HS

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs_color of the light."""
        colour_json = self.device.status.get(self.dp_code_colour)
        if not colour_json:
            return None
        colour_data = json.loads(colour_json)
        s_range = self._tuya_hsv_s_range()
        return colour_data.get("h", 0), self.remap(
            colour_data.get("s", 0),
            s_range[0],
            s_range[1],
            HSV_HA_SATURATION_MIN,
            HSV_HA_SATURATION_MAX,
        )

    @property
    def color_temp(self) -> int:
        """Return the color_temp of the light."""
        new_range = self._tuya_temp_range()
        tuya_color_temp = self.device.status.get(self.dp_code_temp, 0)
        return (
            self.max_mireds
            - self.remap(
                tuya_color_temp,
                new_range[0],
                new_range[1],
                self.min_mireds,
                self.max_mireds,
            )
            + self.min_mireds
        )

    @property
    def min_mireds(self) -> int:
        """Return color temperature min mireds."""
        return MIREDS_MIN

    @property
    def max_mireds(self) -> int:
        """Return color temperature max mireds."""
        return MIREDS_MAX

    def _tuya_temp_range(self) -> tuple[int, int]:
        temp_item = self.device.function.get(self.dp_code_temp)
        if not temp_item:
            return 0, 255
        temp_value = json.loads(temp_item.values)
        return temp_value.get("min", 0), temp_value.get("max", 255)

    def _tuya_hsv_s_range(self) -> tuple[int, int]:
        hsv_data_range = self._tuya_hsv_function()
        if hsv_data_range is not None:
            hsv_s = hsv_data_range.get("s", {"min": 0, "max": 255})
            return hsv_s.get("min", 0), hsv_s.get("max", 255)
        return 0, 255

    def _tuya_hsv_v_range(self) -> tuple[int, int]:
        hsv_data_range = self._tuya_hsv_function()
        if hsv_data_range is not None:
            hsv_v = hsv_data_range.get("v", {"min": 0, "max": 255})
            return hsv_v.get("min", 0), hsv_v.get("max", 255)

        return 0, 255

    def _tuya_hsv_function(self) -> dict[str, dict] | None:
        hsv_item = self.device.function.get(self.dp_code_colour)
        if not hsv_item:
            return None
        hsv_data = json.loads(hsv_item.values)
        if hsv_data:
            return hsv_data
        colour_json = self.device.status.get(self.dp_code_colour)
        if not colour_json:
            return None
        colour_data = json.loads(colour_json)
        if (
            self.dp_code_colour == DPCode.COLOUR_DATA_V2
            or colour_data.get("v", 0) > 255
            or colour_data.get("s", 0) > 255
        ):
            return DEFAULT_HSV_V2
        return DEFAULT_HSV

    def _work_mode(self) -> str:
        return self.device.status.get(DPCode.WORK_MODE, "")

    def _get_hsv(self) -> dict[str, int]:
        if (
            self.dp_code_colour not in self.device.status
            or len(self.device.status[self.dp_code_colour]) == 0
        ):
            return {"h": 0, "s": 0, "v": 0}

        return json.loads(self.device.status[self.dp_code_colour])

    @property
    def supported_color_modes(self) -> set[str] | None:
        """Flag supported color modes."""
        color_modes = [COLOR_MODE_ONOFF]
        if self.dp_code_bright in self.device.status:
            color_modes.append(COLOR_MODE_BRIGHTNESS)

        if self.dp_code_temp in self.device.status:
            color_modes.append(COLOR_MODE_COLOR_TEMP)

        if (
            self.dp_code_colour in self.device.status
            and len(self.device.status[self.dp_code_colour]) > 0
        ):
            color_modes.append(COLOR_MODE_HS)
        return set(color_modes)

    @staticmethod
    def remap(old_value, old_min, old_max, new_min, new_max):
        """Remap old_value to new_value."""
        return ((old_value - old_min) / (old_max - old_min)) * (
            new_max - new_min
        ) + new_min
