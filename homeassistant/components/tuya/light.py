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
    DOMAIN as DEVICE_DOMAIN,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import TuyaHaEntity
from .const import (
    DOMAIN,
    TUYA_DEVICE_MANAGER,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_DEVICES,
    TUYA_HA_TUYA_MAP,
)

_LOGGER = logging.getLogger(__name__)


# Light(dj)
# https://developer.tuya.com/en/docs/iot/f?id=K9i5ql3v98hn3
DPCODE_SWITCH = "switch_led"
DPCODE_WORK_MODE = "work_mode"
DPCODE_BRIGHT_VALUE = "bright_value"
DPCODE_TEMP_VALUE = "temp_value"
DPCODE_COLOUR_DATA = "colour_data"
DPCODE_COLOUR_DATA_V2 = "colour_data_v2"
DPCODE_LIGHT = "light"

MIREDS_MAX = 500
MIREDS_MIN = 153

HSV_HA_HUE_MIN = 0
HSV_HA_HUE_MAX = 360
HSV_HA_SATURATION_MIN = 0
HSV_HA_SATURATION_MAX = 100

WORK_MODE_WHITE = "white"
WORK_MODE_COLOUR = "colour"

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
    _LOGGER.debug("light init")

    hass.data[DOMAIN][entry.entry_id][TUYA_HA_TUYA_MAP][
        DEVICE_DOMAIN
    ] = TUYA_SUPPORT_TYPE

    @callback
    def async_discover_device(dev_ids: list[str]):
        """Discover and add a discovered tuya light."""
        _LOGGER.debug("light add-> %s", dev_ids)
        if not dev_ids:
            return
        entities = _setup_entities(hass, entry, dev_ids)
        async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, TUYA_DISCOVERY_NEW.format(DEVICE_DOMAIN), async_discover_device
        )
    )

    device_manager = hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE_MANAGER]
    device_ids = []
    for (device_id, device) in device_manager.device_map.items():
        if device.category in TUYA_SUPPORT_TYPE:
            device_ids.append(device_id)
    async_discover_device(device_ids)


def _setup_entities(
    hass, entry: ConfigEntry, device_ids: list[str]
) -> list[TuyaHaLight]:
    """Set up Tuya Light device."""
    device_manager = hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE_MANAGER]
    entities = []
    for device_id in device_ids:
        device = device_manager.device_map[device_id]
        if device is None:
            continue

        tuya_ha_light = TuyaHaLight(device, device_manager)
        entities.append(tuya_ha_light)
        hass.data[DOMAIN][entry.entry_id][TUYA_HA_DEVICES].add(
            tuya_ha_light.tuya_device.id
        )

    return entities


class TuyaHaLight(TuyaHaEntity, LightEntity):
    """Tuya light device."""

    def __init__(self, device: TuyaDevice, device_manager: TuyaDeviceManager) -> None:
        """Init TuyaHaLight."""
        self.dp_code_bright = DPCODE_BRIGHT_VALUE
        self.dp_code_temp = DPCODE_TEMP_VALUE
        self.dp_code_colour = DPCODE_COLOUR_DATA

        for key in device.function:
            if key.startswith(DPCODE_BRIGHT_VALUE):
                self.dp_code_bright = key
            elif key.startswith(DPCODE_TEMP_VALUE):
                self.dp_code_temp = key
            elif key.startswith(DPCODE_COLOUR_DATA):
                self.dp_code_colour = key

        super().__init__(device, device_manager)

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.tuya_device.status.get(DPCODE_SWITCH, False)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on or control the light."""
        commands = []
        _LOGGER.debug("light kwargs-> %s", kwargs)

        if (
            DPCODE_LIGHT in self.tuya_device.status
            and DPCODE_SWITCH not in self.tuya_device.status
        ):
            commands += [{"code": DPCODE_LIGHT, "value": True}]
        else:
            commands += [{"code": DPCODE_SWITCH, "value": True}]

        if ATTR_BRIGHTNESS in kwargs:
            if self._work_mode().startswith(WORK_MODE_COLOUR):
                colour_data = self._get_hsv()
                v_range = self._tuya_hsv_v_range()
                colour_data["v"] = int(
                    self.remap(kwargs[ATTR_BRIGHTNESS], 0, 255, v_range[0], v_range[1])
                )
                commands += [
                    {"code": self.dp_code_colour, "value": json.dumps(colour_data)}
                ]
            else:
                new_range = self._tuya_brightness_range()
                tuya_brightness = int(
                    self.remap(
                        kwargs[ATTR_BRIGHTNESS], 0, 255, new_range[0], new_range[1]
                    )
                )
                commands += [{"code": self.dp_code_bright, "value": tuya_brightness}]

        if ATTR_HS_COLOR in kwargs:
            colour_data = self._get_hsv()
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
            v_range = self._tuya_hsv_v_range()
            colour_data["v"] = int(self.remap(ha_v, 0, 255, v_range[0], v_range[1]))

            commands += [
                {"code": self.dp_code_colour, "value": json.dumps(colour_data)}
            ]
            if self.tuya_device.status[DPCODE_WORK_MODE] != "colour":
                commands += [{"code": DPCODE_WORK_MODE, "value": "colour"}]

        if ATTR_COLOR_TEMP in kwargs:
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

            if self.tuya_device.status[DPCODE_WORK_MODE] != "white":
                commands += [{"code": DPCODE_WORK_MODE, "value": "white"}]

        self._send_command(commands)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        if (
            DPCODE_LIGHT in self.tuya_device.status
            and DPCODE_SWITCH not in self.tuya_device.status
        ):
            commands = [{"code": DPCODE_LIGHT, "value": False}]
        else:
            commands = [{"code": DPCODE_SWITCH, "value": False}]
        self._send_command(commands)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        old_range = self._tuya_brightness_range()
        brightness = self.tuya_device.status.get(self.dp_code_bright, 0)

        if self._work_mode().startswith(WORK_MODE_COLOUR):
            colour_json = self.tuya_device.status.get(self.dp_code_colour)
            if not colour_json:
                return None
            colour_data = json.loads(colour_json)
            v_range = self._tuya_hsv_v_range()
            hsv_v = colour_data.get("v", 0)
            return int(self.remap(hsv_v, v_range[0], v_range[1], 0, 255))

        return int(self.remap(brightness, old_range[0], old_range[1], 0, 255))

    def _tuya_brightness_range(self) -> tuple[int, int]:
        if self.dp_code_bright not in self.tuya_device.status:
            return 0, 255
        bright_item = self.tuya_device.function.get(self.dp_code_bright)
        if not bright_item:
            return 0, 255
        bright_value = json.loads(bright_item.values)
        return bright_value.get("min", 0), bright_value.get("max", 255)

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs_color of the light."""
        colour_json = self.tuya_device.status.get(self.dp_code_colour)
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
        tuya_color_temp = self.tuya_device.status.get(self.dp_code_temp, 0)
        ha_color_temp = (
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
        return ha_color_temp

    @property
    def min_mireds(self) -> int:
        """Return color temperature min mireds."""
        return MIREDS_MIN

    @property
    def max_mireds(self) -> int:
        """Return color temperature max mireds."""
        return MIREDS_MAX

    def _tuya_temp_range(self) -> tuple[int, int]:
        temp_item = self.tuya_device.function.get(self.dp_code_temp)
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
        hsv_item = self.tuya_device.function.get(self.dp_code_colour)
        if not hsv_item:
            return None
        hsv_data = json.loads(hsv_item.values)
        if hsv_data:
            return hsv_data
        colour_json = self.tuya_device.status.get(self.dp_code_colour)
        if not colour_json:
            return None
        colour_data = json.loads(colour_json)
        if (
            self.dp_code_colour == DPCODE_COLOUR_DATA_V2
            or colour_data.get("v", 0) > 255
            or colour_data.get("s", 0) > 255
        ):
            return DEFAULT_HSV_V2
        return DEFAULT_HSV

    def _work_mode(self) -> str:
        return self.tuya_device.status.get(DPCODE_WORK_MODE, "")

    def _get_hsv(self) -> dict[str, int]:
        return json.loads(self.tuya_device.status[self.dp_code_colour])

    @property
    def supported_color_modes(self) -> set[str] | None:
        """Flag supported color modes."""
        color_modes = [COLOR_MODE_ONOFF]
        if self.dp_code_bright in self.tuya_device.status:
            color_modes.append(COLOR_MODE_BRIGHTNESS)

        if self.dp_code_temp in self.tuya_device.status:
            color_modes.append(COLOR_MODE_COLOR_TEMP)

        if (
            self.dp_code_colour in self.tuya_device.status
            and len(self.tuya_device.status[self.dp_code_colour]) > 0
        ):
            color_modes.append(COLOR_MODE_HS)
        return set(color_modes)
