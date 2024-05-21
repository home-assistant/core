"""Support for Duwi Smart Light."""

from __future__ import annotations

import json
import logging
from typing import Any

from duwi_smarthome_sdk.api.control import ControlClient
from duwi_smarthome_sdk.const.status import Code
from duwi_smarthome_sdk.model.req.device_control import ControlDevice

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import APP_VERSION, CLIENT_MODEL, CLIENT_VERSION, DOMAIN, MANUFACTURER
from .util import debounce, persist_messages_with_status_code

# Initialize logger
_LOGGER = logging.getLogger(__name__)
# Define the light types supported by this integration
DUWI_LIGHT_TYPES = ["On", "Dim", "Temp", "DimTemp", "RGB", "RGBW", "RGBCW"]
# Define the color modes supported by various light types.
SUPPORTED_COLOR_MODES = {
    "On": [ColorMode.ONOFF],
    "Dim": [ColorMode.BRIGHTNESS],
    "Temp": [ColorMode.COLOR_TEMP],
    "DimTemp": [ColorMode.COLOR_TEMP],
    "RGB": [ColorMode.HS],
    "RGBW": [ColorMode.HS],
    "RGBCW": [ColorMode.HS],
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Asynchronously set up Duwi devices as Home Assistant entities based on a configuration entry."""

    # Extract the instance id from the provided config entry.
    instance_id = config_entry.entry_id

    # Access house-specific information if available.
    if DOMAIN in hass.data and "house_no" in hass.data[DOMAIN][instance_id]:
        devices = hass.data[DOMAIN][instance_id]["devices"].get("LIGHT")

        # Proceed if there are light devices available.
        if devices is not None:
            for device_type in DUWI_LIGHT_TYPES:
                # Check if current device type is available in the devices dictionary.
                if device_type in devices:
                    for device in devices[device_type]:
                        # Create and adjust the device's effect list.
                        effect_list = device.value.get("effectList", {})
                        effect_list_keys = list(effect_list.keys())
                        effect_list_keys.insert(0, "None")
                        device_effect_list = effect_list_keys if effect_list else None

                        # Compile common attributes for each device entity.
                        common_attributes = {
                            "hass": hass,
                            "instance_id": instance_id,
                            "unique_id": device.device_no,
                            "device_name": device.device_name,
                            "device_no": device.device_no,
                            "house_no": device.house_no,
                            "room_name": device.room_name,
                            "floor_name": device.floor_name,
                            "terminal_sequence": device.terminal_sequence,
                            "route_num": device.route_num,
                            "light_type": device_type,
                            "effect_list": device_effect_list,
                            "effect_map": device.value.get("effectList", None),
                            "state": device.value.get("switch", "off") == "on",
                            "available": device.value.get("online", False),
                            "supported_color_modes": SUPPORTED_COLOR_MODES[device_type],
                        }

                        # Append device-specific attributes according to its type.
                        if device_type in ["Dim", "DimTemp"]:
                            common_attributes["brightness"] = int(
                                device.value.get("light", 0) / 100 * 255
                            )

                        if device_type in ["Temp", "DimTemp", "RGBCW"]:
                            color_temp_range = device.value.get(
                                "color_temp_range", {"min": 3000, "max": 6000}
                            )
                            min_ct, max_ct = color_temp_range.get(
                                "min", 3000
                            ), color_temp_range.get("max", 6000)
                            common_attributes["color_temp_range"] = [min_ct, max_ct]
                            common_attributes["ct"] = calculate_color_temperature(
                                device, min_ct, max_ct
                            )

                        if device_type in ["RGB", "RGBW", "RGBCW"]:
                            hs_color = extract_hs_color(device)
                            common_attributes["hs_color"] = hs_color
                            common_attributes["brightness"] = extract_brightness(device)
                            common_attributes["is_color_light"] = True

                        # Add the device as a new entity in Home Assistant.
                        async_add_entities([DuwiLight(**common_attributes)])


def calculate_color_temperature(device, min_ct, max_ct):
    """Calculate and return the color temperature value."""
    # Insert logic for color temperature calculation here.
    return (
        (
            (500 - 153)
            * ((max_ct - int(device.value.get("color_temp", 0))) / (max_ct - min_ct))
            + 153
        )
        if device.value.get("color_temp")
        else 0
    )


def extract_hs_color(device):
    """Extract and return the HS color."""
    color_info = device.value.get("color", {"h": 0, "s": 0, "v": 0})
    return color_info["h"], color_info["s"]


def extract_brightness(device):
    """Extract and return the brightness."""
    color_info = device.value.get("color", {"h": 0, "s": 0, "v": 0})
    return int(color_info.get("v", 0) / 100 * 255)


class DuwiLight(LightEntity):
    """Initialize the DuwiLight entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        instance_id: str,
        unique_id: str,
        device_name: str,
        device_no: str,
        house_no: str,
        floor_name: str,
        room_name: str,
        light_type: str,
        terminal_sequence: str,
        route_num: str,
        state: bool,
        is_color_light: bool = False,
        available: bool = False,
        brightness: int | None = None,
        ct: int | None = None,
        color_temp_range: list[int] | None = None,
        effect_list: list[str] | None = None,
        effect_map: dict[str, str] | None = None,
        effect: str | None = None,
        hs_color: tuple[int, int] | None = None,
        rgb_color: tuple[int, int] | None = None,
        rgbw_color: tuple[int, int, int, int] | None = None,
        rgbww_color: tuple[int, int, int, int, int] | None = None,
        supported_color_modes: set[ColorMode] | None = None,
    ) -> None:
        """Initialize the light."""
        self._device_no = device_no
        self._terminal_sequence = terminal_sequence
        self._route_num = route_num
        self._is_color_light = is_color_light
        self._house_no = house_no
        self._type = light_type
        self._color_temp_range = color_temp_range
        self._floor_name = floor_name
        self._room_name = room_name

        self._instance_id = instance_id
        self._available = available
        self._brightness = brightness
        self._ct = ct
        self._effect = effect
        self._effect_list = effect_list
        self._effect_map = effect_map
        self._hs_color = hs_color
        self._rgbw_color = rgbw_color
        self._rgbww_color = rgbww_color
        self._state = state
        self._unique_id = unique_id
        if hs_color:
            self._color_mode = ColorMode.HS
        elif rgb_color:
            self._color_mode = ColorMode.RGB
        elif rgbw_color:
            self._color_mode = ColorMode.RGBW
        elif rgbww_color:
            self._color_mode = ColorMode.RGBWW
        elif ct:
            self._color_mode = ColorMode.COLOR_TEMP
        elif brightness:
            self._color_mode = ColorMode.BRIGHTNESS
        else:
            self._color_mode = ColorMode.ONOFF
        self._supported_color_modes = supported_color_modes
        self._color_modes = supported_color_modes
        if self._effect_list is not None:
            self._attr_supported_features |= LightEntityFeature.EFFECT
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer=MANUFACTURER,
            name=(
                self._room_name + " "
                if self._room_name is not None and self._room_name != ""
                else ""
            )
            + device_name,
            suggested_area=(
                self._floor_name + " " + self._room_name
                if self._room_name is not None and self._room_name != ""
                else "default room"
            ),
        )
        self.hass = hass
        self.cc = ControlClient(
            app_key=self.hass.data[DOMAIN][instance_id]["app_key"],
            app_secret=self.hass.data[DOMAIN][instance_id]["app_secret"],
            access_token=self.hass.data[DOMAIN][instance_id]["access_token"],
            app_version=APP_VERSION,
            client_version=CLIENT_VERSION,
            client_model=CLIENT_MODEL,
        )
        self.cd = ControlDevice(
            device_no=self._device_no,
            house_no=self._house_no,
        )
        # 存入全局的实体id
        self.entity_id = f"light.duwi_{device_no}"
        self.hass.data[DOMAIN][instance_id][unique_id] = {
            "device_no": self._device_no,
            "color_temp_range": self._color_temp_range,
            "update_device_state": self.update_device_state,
        }

        if self.hass.data[DOMAIN][instance_id].get(self._terminal_sequence) is None:
            self.hass.data[DOMAIN][instance_id][self._terminal_sequence] = {}
        self.hass.data[DOMAIN][instance_id].setdefault("slave", {}).setdefault(
            self._terminal_sequence, {}
        )[self._device_no] = self.update_device_state

    @property
    def unique_id(self) -> str:
        """Return unique ID for light."""
        return self._unique_id

    @property
    def available(self) -> bool:
        """Return availability."""
        return self._available

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        return self._color_mode

    @property
    def hs_color(self) -> tuple[int, int] | None:
        """Return the hs color value."""
        return self._hs_color

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgbw color value."""
        return self._rgbw_color

    @property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the rgbww color value."""
        return self._rgbww_color

    @property
    def color_temp(self) -> int:
        """Return the CT color temperature."""
        return self._ct

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self._effect_list

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._effect

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._state

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        return self._color_modes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        self._state = True
        self._effect = "None"
        if ATTR_BRIGHTNESS in kwargs:
            # Set brightness from kwargs if present
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            if self._is_color_light:
                # If it's a color light, adjust the color brightness accordingly
                self.cd.add_param_info(
                    "color",
                    {
                        "h": self.hs_color[0],
                        "s": self.hs_color[1],
                        "v": int(round(self._brightness / 255 * 100)),
                    },
                )
            else:
                # If it's not a color light, just set the light brightness
                self.cd.add_param_info(
                    "light", int(round(self._brightness / 255 * 100))
                )

        if ATTR_COLOR_TEMP in kwargs:
            # Handle setting of color temperature
            self._color_mode = ColorMode.COLOR_TEMP
            self._ct = kwargs[ATTR_COLOR_TEMP]
            # Perform appropriate conversion to device's color temperature
            self.cd.add_param_info(
                "color_temp",
                int(
                    (
                        self._color_temp_range[1]
                        - int(
                            (
                                (self._ct - 153)
                                * (
                                    self._color_temp_range[1]
                                    - self._color_temp_range[0]
                                )
                                / (500 - 153)
                            )
                        )
                    )
                    // 100.0
                    * 100
                ),
            )

        if ATTR_EFFECT in kwargs:
            # Set effect based on the chosen effect name
            self._effect = kwargs[ATTR_EFFECT]
            if self._effect != "None":
                effect_data = json.loads(self._effect_map[self._effect])
                if "light" in effect_data:
                    # Adjust brightness based on effect data
                    self._brightness = int(round(effect_data["light"] / 100 * 255))
                    self.cd.add_param_info("light", effect_data["light"])
                if "color_temp" in effect_data:
                    # Adjust color temperature based on effect data
                    self._ct = self.convert_to_ha_color_temp(effect_data["color_temp"])
                    self.cd.add_param_info("color_temp", effect_data["color_temp"])
                if "color" in effect_data:
                    # Adjust HS color based on effect data
                    self._hs_color = (
                        effect_data["color"]["h"],
                        effect_data["color"]["s"],
                    )
                    self._brightness = int(round(effect_data["color"]["v"] / 100 * 255))
                    self.cd.add_param_info("color", effect_data["color"])

        if ATTR_HS_COLOR in kwargs:
            # Directly set HS color from arguments
            self._color_mode = ColorMode.HS
            self._hs_color = kwargs[ATTR_HS_COLOR]
            self.cd.add_param_info(
                "color",
                {
                    "h": self._hs_color[0],
                    "s": self._hs_color[1],
                    "v": int(round(self._brightness / 255 * 100)),
                },
            )

        if not kwargs.get("is_scheduled", False):
            # Inform Home Assistant to update state
            if len(self.cd.commands) == 0:
                self.cd.add_param_info("switch", "on")
            status = await self.cc.control(self.cd)
            # If the request was successful, update the state
            if status == Code.SUCCESS.value:
                self.async_write_ha_state()
            else:
                await persist_messages_with_status_code(hass=self.hass, status=status)
        else:
            await self.async_write_ha_state_with_debounce()

        self.cd.remove_param_info()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._state = False

        # Update Home Assistant about the new state after disabling polling
        self.cd.add_param_info("switch", "off")

        if not kwargs.get("is_scheduled", False):
            status = await self.cc.control(self.cd)
            if status == Code.SUCCESS.value:
                self.async_write_ha_state()
            else:
                await persist_messages_with_status_code(hass=self.hass, status=status)
        else:
            await self.async_write_ha_state_with_debounce()
        self.cd.remove_param_info()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the light's current state."""
        if self._state:
            await self.async_turn_off(**kwargs)
        else:
            await self.async_turn_on(**kwargs)

    async def update_device_state(
        self, action: str = None, is_scheduled: bool = True, **kwargs: Any
    ):
        """Update the device state."""
        kwargs["is_scheduled"] = is_scheduled
        if action == "turn_on":
            await self.async_turn_on(**kwargs)
        elif action == "turn_off":
            await self.async_turn_off(**kwargs)
        elif action == "toggle":
            await self.async_toggle(**kwargs)
        else:
            if "available" in kwargs:
                self._available = kwargs["available"]
                self.async_write_ha_state()

    def convert_to_ha_color_temp(self, duwi_ct):
        """Convert device-specific color temperature to HA color temperature."""
        if not self._color_temp_range:
            self._color_temp_range = [3000, 6000]
        return (
            (
                (500 - 153)
                * (
                    (self._color_temp_range[1] - duwi_ct)
                    / (self._color_temp_range[1] - self._color_temp_range[0])
                )
                + 153
            )
            if duwi_ct
            else 0
        )

    # def convert_to_ha_color_temp(self, duwi_ct):
    #     """Convert device-specific color temperature to HA color temperature."""
    #     if not self._color_temp_range:
    #         self._color_temp_range = [3000, 6000]
    #     return ((500 - 153) * ((self._color_temp_range[1] - duwi_ct) / (
    #             self._color_temp_range[1] - self._color_temp_range[0])) + 153) if duwi_ct else 0

    @debounce(0.5)
    async def async_write_ha_state_with_debounce(self):
        self.async_write_ha_state()
