"""Support for Fujitsu HVAC devices that use the Ayla Iot platform."""

from typing import Any

from ayla_iot_unofficial.fujitsu_hvac import Capability, FujitsuHVAC

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FujitsuHVACConfigEntry
from .const import (
    DOMAIN,
    FUJI_TO_HA_FAN,
    FUJI_TO_HA_HVAC,
    FUJI_TO_HA_SWING,
    HA_TO_FUJI_FAN,
    HA_TO_FUJI_HVAC,
    HA_TO_FUJI_SWING,
)
from .coordinator import FujitsuHVACCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FujitsuHVACConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one Fujitsu HVAC device."""
    async_add_entities(
        FujitsuHVACDevice(entry.runtime_data.coordinator, dev.device_serial_number)
        for dev in entry.runtime_data.coordinator.data.values()
    )


class FujitsuHVACDevice(CoordinatorEntity[FujitsuHVACCoordinator], ClimateEntity):
    """Represent a Fujitsu HVAC device."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_HALVES
    _attr_target_temperature_step = 0.5
    _attr_has_entity_name = True
    _attr_name = None

    _enable_turn_on_off_backwards_compatibility: bool = False

    def __init__(self, coordinator: FujitsuHVACCoordinator, dev_sn: str) -> None:
        """Store the representation of the device and set the static attributes."""
        super().__init__(coordinator, context=dev_sn)

        self._attr_unique_id = self.device.device_serial_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device.device_serial_number)},
            name=self.device.device_name,
            manufacturer="Fujitsu",
            model=self.device.property_values["model_name"],
            serial_number=self.device.device_serial_number,
            sw_version=self.device.property_values["mcu_firmware_version"],
        )

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        if self.device.has_capability(Capability.OP_FAN):
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

        if self.device.has_capability(
            Capability.SWING_HORIZONTAL
        ) or self.device.has_capability(Capability.SWING_VERTICAL):
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE

    @property
    def device(self) -> FujitsuHVAC:
        """Return the device object from the coordinator data."""
        return self.coordinator.data[self.coordinator_context]

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return FUJI_TO_HA_FAN.get(self.device.fan_speed)

    @property
    def fan_modes(self) -> list[str]:
        """Return the list of available fan modes."""
        return [
            FUJI_TO_HA_FAN[mode]
            for mode in self.device.supported_fan_speeds
            if mode in FUJI_TO_HA_FAN
        ]

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set Fan mode."""
        await self.device.async_set_fan_speed(HA_TO_FUJI_FAN[fan_mode])
        await self.coordinator.async_request_refresh()

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        return FUJI_TO_HA_HVAC.get(self.device.op_mode)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        return [
            FUJI_TO_HA_HVAC[mode]
            for mode in self.device.supported_op_modes
            if mode in FUJI_TO_HA_HVAC
        ]

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        await self.device.async_set_op_mode(HA_TO_FUJI_HVAC[hvac_mode])
        await self.coordinator.async_request_refresh()

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting.

        Requires ClimateEntityFeature.SWING_MODE.
        """
        return FUJI_TO_HA_SWING.get(self.device.swing_mode)

    @property
    def swing_modes(self) -> list[str]:
        """Return the list of available swing modes.

        Requires ClimateEntityFeature.SWING_MODE.
        """
        return [
            FUJI_TO_HA_SWING[mode]
            for mode in self.device.supported_swing_modes
            if mode in FUJI_TO_HA_SWING
        ]

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode."""
        await self.device.async_set_swing_mode(HA_TO_FUJI_SWING[swing_mode])
        await self.coordinator.async_request_refresh()

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return float(self.device.temperature_range[0])

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return float(self.device.temperature_range[1])

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return float(self.device.sensed_temp)

    @property
    def target_temperature(self) -> float:
        """Return the target temperature."""
        return float(self.device.set_temp)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self.device.async_set_set_temp(temperature)
        await self.coordinator.async_request_refresh()
