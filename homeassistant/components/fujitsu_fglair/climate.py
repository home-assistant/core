"""Support for Fujitsu HVAC devices that use the Ayla Iot platform."""

from typing import Any

from ayla_iot_unofficial.fujitsu_hvac import (
    Capability,
    FanSpeed,
    FujitsuHVAC,
    OpMode,
    SwingMode,
)

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from . import FGLairConfigEntry
from .coordinator import FGLairCoordinator
from .entity import FGLairEntity

HA_TO_FUJI_FAN = {
    FAN_LOW: FanSpeed.LOW,
    FAN_MEDIUM: FanSpeed.MEDIUM,
    FAN_HIGH: FanSpeed.HIGH,
    FAN_AUTO: FanSpeed.AUTO,
}
FUJI_TO_HA_FAN = {value: key for key, value in HA_TO_FUJI_FAN.items()}

HA_TO_FUJI_HVAC = {
    HVACMode.OFF: OpMode.OFF,
    HVACMode.HEAT: OpMode.HEAT,
    HVACMode.COOL: OpMode.COOL,
    HVACMode.HEAT_COOL: OpMode.AUTO,
    HVACMode.DRY: OpMode.DRY,
    HVACMode.FAN_ONLY: OpMode.FAN,
}
FUJI_TO_HA_HVAC = {value: key for key, value in HA_TO_FUJI_HVAC.items()}

HA_TO_FUJI_SWING = {
    SWING_OFF: SwingMode.OFF,
    SWING_VERTICAL: SwingMode.SWING_VERTICAL,
    SWING_HORIZONTAL: SwingMode.SWING_HORIZONTAL,
    SWING_BOTH: SwingMode.SWING_BOTH,
}
FUJI_TO_HA_SWING = {value: key for key, value in HA_TO_FUJI_SWING.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FGLairConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one Fujitsu HVAC device."""
    async_add_entities(
        FGLairDevice(entry.runtime_data, device, hass)
        for device in entry.runtime_data.data.values()
    )


class FGLairDevice(FGLairEntity, ClimateEntity):
    """Represent a Fujitsu HVAC device."""

    def __init__(self, coordinator: FGLairCoordinator, device: FujitsuHVAC, hass: HomeAssistant) -> None:
        """Store the representation of the device and set the static attributes."""
        super().__init__(coordinator, device)

        self.hass = hass
        self._attr_unique_id = device.device_serial_number

        if self.hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT:
            self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
            self._attr_target_temperature_step = 1
        else:
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
            self._attr_target_temperature_step = 0.5

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        if device.has_capability(Capability.OP_FAN):
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

        if device.has_capability(Capability.SWING_HORIZONTAL) or device.has_capability(
            Capability.SWING_VERTICAL
        ):
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE

        self._set_attr()

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self.coordinator_context in self.coordinator.data

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set Fan mode."""
        await self.device.async_set_fan_speed(HA_TO_FUJI_FAN[fan_mode])
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        await self.device.async_set_op_mode(HA_TO_FUJI_HVAC[hvac_mode])
        await self.coordinator.async_request_refresh()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode."""
        await self.device.async_set_swing_mode(HA_TO_FUJI_SWING[swing_mode])
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        if self.hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT:
            temperature = round(TemperatureConverter.convert(temperature, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS) * 2) / 2
        await self.device.async_set_set_temp(temperature)
        await self.coordinator.async_request_refresh()

    def _set_attr(self) -> None:
        """Set dynamic attributes based on current configuration."""
        if self.coordinator_context in self.coordinator.data:
            # Convert temperature range dynamically
            if self.hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT:
                self._attr_min_temp = round(TemperatureConverter.convert(self.device.temperature_range[0], UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT))
                self._attr_max_temp = round(TemperatureConverter.convert(self.device.temperature_range[1], UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT))
                self._attr_current_temperature = round(TemperatureConverter.convert(self.device.sensed_temp, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT))
                self._attr_target_temperature = round(TemperatureConverter.convert(self.device.set_temp, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT))
                self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
                self._attr_target_temperature_step = 1
            else:
                self._attr_min_temp = self.device.temperature_range[0]
                self._attr_max_temp = self.device.temperature_range[1]
                self._attr_current_temperature = self.device.sensed_temp
                self._attr_target_temperature = self.device.set_temp
                self._attr_temperature_unit = UnitOfTemperature.CELSIUS
                self._attr_target_temperature_step = 0.5

            # Other attributes
            self._attr_fan_mode = FUJI_TO_HA_FAN.get(self.device.fan_speed)
            self._attr_fan_modes = [
                FUJI_TO_HA_FAN[mode]
                for mode in self.device.supported_fan_speeds
                if mode in FUJI_TO_HA_FAN
            ]
            self._attr_hvac_mode = FUJI_TO_HA_HVAC.get(self.device.op_mode)
            self._attr_hvac_modes = [
                FUJI_TO_HA_HVAC[mode]
                for mode in self.device.supported_op_modes
                if mode in FUJI_TO_HA_HVAC
            ]
            self._attr_swing_mode = FUJI_TO_HA_SWING.get(self.device.swing_mode)
            self._attr_swing_modes = [
                FUJI_TO_HA_SWING[mode]
                for mode in self.device.supported_swing_modes
                if mode in FUJI_TO_HA_SWING
            ]

    def _handle_coordinator_update(self) -> None:
        self._set_attr()
        super()._handle_coordinator_update()
