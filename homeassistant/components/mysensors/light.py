"""Support for MySensors lights."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import rgb_hex_to_rgb_list

from . import setup_mysensors_platform
from .const import MYSENSORS_DISCOVERY, DiscoveryInfo, SensorType
from .entity import MySensorsChildEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up this platform for a specific ConfigEntry(==Gateway)."""
    device_class_map: dict[SensorType, type[MySensorsChildEntity]] = {
        "S_DIMMER": MySensorsLightDimmer,
        "S_RGB_LIGHT": MySensorsLightRGB,
        "S_RGBW_LIGHT": MySensorsLightRGBW,
    }

    async def async_discover(discovery_info: DiscoveryInfo) -> None:
        """Discover and add a MySensors light."""
        setup_mysensors_platform(
            hass,
            Platform.LIGHT,
            discovery_info,
            device_class_map,
            async_add_entities=async_add_entities,
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            MYSENSORS_DISCOVERY.format(config_entry.entry_id, Platform.LIGHT),
            async_discover,
        ),
    )


class MySensorsLight(MySensorsChildEntity, LightEntity):
    """Representation of a MySensors Light child node."""

    def __init__(self, *args: Any) -> None:
        """Initialize a MySensors Light."""
        super().__init__(*args)
        self._state: bool | None = None

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return bool(self._state)

    def _turn_on_light(self) -> None:
        """Turn on light child device."""
        set_req = self.gateway.const.SetReq

        if self._state:
            return
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_LIGHT, 1, ack=1
        )

    def _turn_on_dimmer(self, **kwargs: Any) -> None:
        """Turn on dimmer child device."""
        set_req = self.gateway.const.SetReq

        if (
            ATTR_BRIGHTNESS not in kwargs
            or kwargs[ATTR_BRIGHTNESS] == self._attr_brightness
            or set_req.V_DIMMER not in self._values
        ):
            return
        brightness: int = kwargs[ATTR_BRIGHTNESS]
        percent = round(100 * brightness / 255)
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_DIMMER, percent, ack=1
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        value_type = self.gateway.const.SetReq.V_LIGHT
        self.gateway.set_child_value(self.node_id, self.child_id, value_type, 0, ack=1)

    @callback
    def _async_update_light(self) -> None:
        """Update the controller with values from light child."""
        value_type = self.gateway.const.SetReq.V_LIGHT
        self._state = self._values[value_type] == STATE_ON

    @callback
    def _async_update_dimmer(self) -> None:
        """Update the controller with values from dimmer child."""
        value_type = self.gateway.const.SetReq.V_DIMMER
        if value_type in self._values:
            self._attr_brightness = round(255 * int(self._values[value_type]) / 100)
            if self._attr_brightness == 0:
                self._state = False


class MySensorsLightDimmer(MySensorsLight):
    """Dimmer child class to MySensorsLight."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self._turn_on_light()
        self._turn_on_dimmer(**kwargs)

    @callback
    def _async_update(self) -> None:
        """Update the controller with the latest value from a sensor."""
        super()._async_update()
        self._async_update_light()
        self._async_update_dimmer()


class MySensorsLightRGB(MySensorsLight):
    """RGB child class to MySensorsLight."""

    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self._turn_on_light()
        self._turn_on_dimmer(**kwargs)
        self._turn_on_rgb(**kwargs)

    def _turn_on_rgb(self, **kwargs: Any) -> None:
        """Turn on RGB child device."""
        hex_color = self._values.get(self.value_type)
        new_rgb: tuple[int, int, int] | None = kwargs.get(ATTR_RGB_COLOR)
        if new_rgb is None:
            return
        red, green, blue = new_rgb
        hex_color = f"{red:02x}{green:02x}{blue:02x}"
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, hex_color, ack=1
        )

    @callback
    def _async_update(self) -> None:
        """Update the controller with the latest value from a sensor."""
        super()._async_update()
        self._async_update_light()
        self._async_update_dimmer()
        self._async_update_rgb_or_w()

    @callback
    def _async_update_rgb_or_w(self) -> None:
        """Update the controller with values from RGB child."""
        value = self._values[self.value_type]
        self._attr_rgb_color = cast(
            tuple[int, int, int], tuple(rgb_hex_to_rgb_list(value))
        )


class MySensorsLightRGBW(MySensorsLightRGB):
    """RGBW child class to MySensorsLightRGB."""

    _attr_supported_color_modes = {ColorMode.RGBW}
    _attr_color_mode = ColorMode.RGBW

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self._turn_on_light()
        self._turn_on_dimmer(**kwargs)
        self._turn_on_rgbw(**kwargs)

    def _turn_on_rgbw(self, **kwargs: Any) -> None:
        """Turn on RGBW child device."""
        hex_color = self._values.get(self.value_type)
        new_rgbw: tuple[int, int, int, int] | None = kwargs.get(ATTR_RGBW_COLOR)
        if new_rgbw is None:
            return
        red, green, blue, white = new_rgbw
        hex_color = f"{red:02x}{green:02x}{blue:02x}{white:02x}"
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, hex_color, ack=1
        )

    @callback
    def _async_update_rgb_or_w(self) -> None:
        """Update the controller with values from RGBW child."""
        value = self._values[self.value_type]
        self._attr_rgbw_color = cast(
            tuple[int, int, int, int], tuple(rgb_hex_to_rgb_list(value))
        )
