"""Support for Modbus lights."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.const import CONF_BRIGHTNESS, CONF_COLOR_TEMP, CONF_LIGHTS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import get_hub
from .const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_WRITE_REGISTER,
    CONF_COLOR_TEMP_KELVIN,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    DEFAULT_BRIGHTNESS,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    MAX_BRIGHTNESS,
    MODBUS_MAX,
    MODBUS_MIN,
)
from .entity import BaseSwitch
from .modbus import ModbusHub

PARALLEL_UPDATES = 1


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Read configuration and create Modbus lights."""
    if discovery_info is None or not (lights := discovery_info[CONF_LIGHTS]):
        return
    hub = get_hub(hass, discovery_info[CONF_NAME])
    async_add_entities(ModbusLight(hass, hub, config) for config in lights)


class ModbusLight(BaseSwitch, LightEntity):
    """Class representing a Modbus light with dimming support."""

    def __init__(
        self, hass: HomeAssistant, hub: ModbusHub, config: dict[str, Any]
    ) -> None:
        """Initialize the Modbus light entity."""
        super().__init__(hass, hub, config)
        self._brightness: int = DEFAULT_BRIGHTNESS
        self._brightness_address: int | None = config.get(CONF_BRIGHTNESS)
        self._color_temp_address: int | None = config.get(CONF_COLOR_TEMP)
        self._color_temp_kelvin: int | None = None

        # Determine color mode dynamically
        self._attr_color_mode = self._detect_color_mode(config=config)
        self._attr_supported_color_modes = {self._attr_color_mode}

        # Set min/max kelvin values if the mode is COLOR_TEMP
        if self._attr_color_mode == ColorMode.COLOR_TEMP:
            self._attr_min_color_temp_kelvin = config.get(
                CONF_MIN_TEMP, DEFAULT_MIN_KELVIN
            )
            self._attr_max_color_temp_kelvin = config.get(
                CONF_MAX_TEMP, DEFAULT_MAX_KELVIN
            )

    @staticmethod
    def _detect_color_mode(config: dict[str, any]) -> ColorMode:
        """Determine the appropriate color mode for the light based on configuration."""
        if CONF_COLOR_TEMP in config:
            return ColorMode.COLOR_TEMP
        if CONF_BRIGHTNESS in config:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def brightness(self) -> int:
        """Return the current brightness level (0-255)."""
        return self._brightness

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the current color temperature in Kelvin."""
        return self._color_temp_kelvin

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn light on and set brightness if provided."""
        await self.async_turn(self.command_on)
        await asyncio.sleep(0.01)
        if CONF_BRIGHTNESS in kwargs:
            await self.async_set_brightness(
                kwargs.get(CONF_BRIGHTNESS, self._brightness)
            )

        if CONF_COLOR_TEMP_KELVIN in kwargs:
            await self.async_set_color_temp(
                kwargs.get(CONF_COLOR_TEMP_KELVIN, self._color_temp_kelvin)
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        await self.async_turn(self._command_off)

    async def async_set_brightness(self, brightness: int) -> None:
        """Set the brightness of the light."""
        if self._brightness_address:
            conv_brightness = await self._convert_brightness_to_modbus(
                brightness=brightness
            )
            await self._hub.async_pb_call(
                unit=self._slave,
                address=self._brightness_address,
                value=conv_brightness,
                use_call=CALL_TYPE_WRITE_REGISTER,
            )

            self._brightness = brightness

    async def async_set_color_temp(self, color_temp_kelvin: int) -> None:
        """Send Modbus command to set color temperature."""
        if self._color_temp_address:
            conv_color_temp_kelvin = await self._convert_color_temp_to_modbus(
                kelvin=color_temp_kelvin
            )
            await self._hub.async_pb_call(
                unit=self._slave,
                address=self._color_temp_address,
                value=conv_color_temp_kelvin,
                use_call=CALL_TYPE_WRITE_REGISTER,
            )
            self._color_temp_kelvin = color_temp_kelvin

    async def _async_update(self) -> None:
        await super()._async_update()
        """Update the entity state, including brightness and color temperature."""
        if self._brightness_address:
            brightness_result = await self._hub.async_pb_call(
                unit=self._slave,
                value=1,
                address=self._brightness_address,
                use_call=CALL_TYPE_REGISTER_HOLDING,
            )
            if brightness_result.registers:
                self._brightness = await self.percent_to_brightness(
                    brightness_result.registers[0]
                )

        if self._color_temp_address:
            color_result = await self._hub.async_pb_call(
                unit=self._slave,
                value=1,
                address=self._color_temp_address,
                use_call=CALL_TYPE_REGISTER_HOLDING,
            )
            if color_result.registers:
                self._color_temp_kelvin = await self.percent_to_temperature(
                    color_result.registers[0]
                )

    @staticmethod
    async def percent_to_brightness(percent: int) -> int:
        """Convert Modbus scale (0-100) to the brightness (0-255)."""
        return round(percent / MODBUS_MAX * MAX_BRIGHTNESS)

    async def percent_to_temperature(self, percent: int) -> int:
        """Convert Modbus scale (0-100) to the color temperature in Kelvin (2000-7000 К)."""
        return round(
            self._attr_min_color_temp_kelvin
            + (
                percent
                / MODBUS_MAX
                * (self._attr_max_color_temp_kelvin - self._attr_min_color_temp_kelvin)
            )
        )

    @staticmethod
    async def _convert_brightness_to_modbus(brightness: int) -> int:
        """Convert brightness (0-255) to Modbus scale (0-100)."""
        return round(brightness / MAX_BRIGHTNESS * MODBUS_MAX)

    @staticmethod
    async def _convert_color_temp_to_modbus(kelvin: int) -> int:
        """Convert color temperature from Kelvin to the Modbus scale (0-100)."""
        return round(
            MODBUS_MIN
            + (kelvin - DEFAULT_MIN_KELVIN)
            * (MODBUS_MAX - MODBUS_MIN)
            / (DEFAULT_MAX_KELVIN - DEFAULT_MIN_KELVIN)
        )
