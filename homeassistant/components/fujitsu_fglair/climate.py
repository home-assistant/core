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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FGLairConfigEntry
from .const import DOMAIN
from .coordinator import FGLairCoordinator

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
        FGLairDevice(entry.runtime_data, device)
        for device in entry.runtime_data.data.values()
    )


class FGLairDevice(CoordinatorEntity[FGLairCoordinator], ClimateEntity):
    """Represent a Fujitsu HVAC device."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_HALVES
    _attr_target_temperature_step = 0.5
    _attr_has_entity_name = True
    _attr_name = None

    _enable_turn_on_off_backwards_compatibility: bool = False

    def __init__(self, coordinator: FGLairCoordinator, device: FujitsuHVAC) -> None:
        """Store the representation of the device and set the static attributes."""
        super().__init__(coordinator, context=device.device_serial_number)

        self._attr_unique_id = device.device_serial_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_serial_number)},
            name=device.device_name,
            manufacturer="Fujitsu",
            model=device.property_values["model_name"],
            serial_number=device.device_serial_number,
            sw_version=device.property_values["mcu_firmware_version"],
        )

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
    def device(self) -> FujitsuHVAC:
        """Return the device object from the coordinator data."""
        return self.coordinator.data[self.coordinator_context]

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
        await self.device.async_set_set_temp(temperature)
        await self.coordinator.async_request_refresh()

    def _set_attr(self) -> None:
        if self.coordinator_context in self.coordinator.data:
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
            self._attr_min_temp = self.device.temperature_range[0]
            self._attr_max_temp = self.device.temperature_range[1]
            self._attr_current_temperature = self.device.sensed_temp
            self._attr_target_temperature = self.device.set_temp

    def _handle_coordinator_update(self) -> None:
        self._set_attr()
        super()._handle_coordinator_update()
