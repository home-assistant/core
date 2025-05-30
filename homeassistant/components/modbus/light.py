"""Support for Modbus lights."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_LIGHTS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import get_hub
from .const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_WRITE_REGISTER,
    CONF_BRIGHTNESS_REGISTER,
    CONF_COLOR_TEMP_REGISTER,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    LIGHT_DEFAULT_MAX_KELVIN,
    LIGHT_DEFAULT_MIN_KELVIN,
    LIGHT_MAX_BRIGHTNESS,
    LIGHT_MODBUS_INVALID_VALUE,
    LIGHT_MODBUS_SCALE_MAX,
    LIGHT_MODBUS_SCALE_MIN,
)
from .entity import BaseSwitch
from .modbus import ModbusHub

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


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
    """Class representing a Modbus light."""

    def __init__(
        self, hass: HomeAssistant, hub: ModbusHub, config: dict[str, Any]
    ) -> None:
        """Initialize the Modbus light entity."""
        super().__init__(hass, hub, config)
        self._brightness_address: int | None = config.get(CONF_BRIGHTNESS_REGISTER)
        self._color_temp_address: int | None = config.get(CONF_COLOR_TEMP_REGISTER)

        # Determine color mode dynamically
        self._attr_color_mode = self._detect_color_mode(config)
        self._attr_supported_color_modes = {self._attr_color_mode}

        # Set min/max kelvin values if the mode is COLOR_TEMP
        if self._attr_color_mode == ColorMode.COLOR_TEMP:
            self._attr_min_color_temp_kelvin = config.get(
                CONF_MIN_TEMP, LIGHT_DEFAULT_MIN_KELVIN
            )
            self._attr_max_color_temp_kelvin = config.get(
                CONF_MAX_TEMP, LIGHT_DEFAULT_MAX_KELVIN
            )

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is None:
            return

        if (brightness := state.attributes.get(ATTR_BRIGHTNESS)) is not None:
            self._attr_brightness = brightness

        if (color_temp := state.attributes.get(ATTR_COLOR_TEMP_KELVIN)) is not None:
            self._attr_color_temp_kelvin = color_temp

    @staticmethod
    def _detect_color_mode(config: dict[str, Any]) -> ColorMode:
        """Determine the appropriate color mode for the light based on configuration."""
        if CONF_COLOR_TEMP_REGISTER in config:
            return ColorMode.COLOR_TEMP
        if CONF_BRIGHTNESS_REGISTER in config:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn light on and set brightness if provided."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness and isinstance(brightness, int):
            await self.async_set_brightness(brightness)
        color_temp = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        if color_temp and isinstance(color_temp, int):
            await self.async_set_color_temp(color_temp)
        await self.async_turn(self.command_on)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        await self.async_turn(self._command_off)

    async def async_set_brightness(self, brightness: int) -> None:
        """Set the brightness of the light."""
        if not self._brightness_address:
            return

        conv_brightness = self._convert_brightness_to_modbus(brightness)

        await self._hub.async_pb_call(
            unit=self._slave,
            address=self._brightness_address,
            value=conv_brightness,
            use_call=CALL_TYPE_WRITE_REGISTER,
        )
        if not self._verify_active:
            self._attr_brightness = brightness

    async def async_set_color_temp(self, color_temp_kelvin: int) -> None:
        """Send Modbus command to set color temperature."""
        if not self._color_temp_address:
            return

        conv_color_temp_kelvin = self._convert_color_temp_to_modbus(color_temp_kelvin)

        await self._hub.async_pb_call(
            unit=self._slave,
            address=self._color_temp_address,
            value=conv_color_temp_kelvin,
            use_call=CALL_TYPE_WRITE_REGISTER,
        )
        if not self._verify_active:
            self._attr_color_temp_kelvin = color_temp_kelvin

    async def _async_update(self) -> None:
        """Update the entity state, including brightness and color temperature."""
        await super()._async_update()

        if not self._verify_active:
            return

        if self._brightness_address:
            brightness_result = await self._hub.async_pb_call(
                unit=self._slave,
                value=1,
                address=self._brightness_address,
                use_call=CALL_TYPE_REGISTER_HOLDING,
            )

            if (
                brightness_result
                and brightness_result.registers
                and brightness_result.registers[0] != LIGHT_MODBUS_INVALID_VALUE
            ):
                self._attr_brightness = self._convert_modbus_percent_to_brightness(
                    brightness_result.registers[0]
                )

        if self._color_temp_address:
            color_result = await self._hub.async_pb_call(
                unit=self._slave,
                value=1,
                address=self._color_temp_address,
                use_call=CALL_TYPE_REGISTER_HOLDING,
            )
            if (
                color_result
                and color_result.registers
                and color_result.registers[0] != LIGHT_MODBUS_INVALID_VALUE
            ):
                self._attr_color_temp_kelvin = (
                    self._convert_modbus_percent_to_temperature(
                        color_result.registers[0]
                    )
                )

    @staticmethod
    def _convert_modbus_percent_to_brightness(percent: int) -> int:
        """Convert Modbus scale (0-100) to the brightness (0-255)."""
        return round(
            percent
            / (LIGHT_MODBUS_SCALE_MAX - LIGHT_MODBUS_SCALE_MIN)
            * LIGHT_MAX_BRIGHTNESS
        )

    def _convert_modbus_percent_to_temperature(self, percent: int) -> int:
        """Convert Modbus scale (0-100) to the color temperature in Kelvin (2000-7000 К)."""
        assert isinstance(self._attr_min_color_temp_kelvin, int) and isinstance(
            self._attr_max_color_temp_kelvin, int
        )
        return round(
            self._attr_min_color_temp_kelvin
            + (
                percent
                / (LIGHT_MODBUS_SCALE_MAX - LIGHT_MODBUS_SCALE_MIN)
                * (self._attr_max_color_temp_kelvin - self._attr_min_color_temp_kelvin)
            )
        )

    @staticmethod
    def _convert_brightness_to_modbus(brightness: int) -> int:
        """Convert brightness (0-255) to Modbus scale (0-100)."""
        return round(
            brightness
            / LIGHT_MAX_BRIGHTNESS
            * (LIGHT_MODBUS_SCALE_MAX - LIGHT_MODBUS_SCALE_MIN)
        )

    def _convert_color_temp_to_modbus(self, kelvin: int) -> int:
        """Convert color temperature from Kelvin to the Modbus scale (0-100)."""
        assert isinstance(self._attr_min_color_temp_kelvin, int) and isinstance(
            self._attr_max_color_temp_kelvin, int
        )
        return round(
            LIGHT_MODBUS_SCALE_MIN
            + (kelvin - self._attr_min_color_temp_kelvin)
            * (LIGHT_MODBUS_SCALE_MAX - LIGHT_MODBUS_SCALE_MIN)
            / (self._attr_max_color_temp_kelvin - self._attr_min_color_temp_kelvin)
        )
