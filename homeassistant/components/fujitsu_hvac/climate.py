"""Support for Fujitsu HVAC devices that use the Ayla Iot platform."""
from typing import Any

from ayla_iot_unofficial.fujitsu_hvac import Capability, FujitsuHVAC

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one Fujitsu HVAC device."""
    api = hass.data[DOMAIN][entry.entry_id]
    coordinator = FujitsuHVACCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        [FujitsuHVACDevice(coordinator, dev) for dev in coordinator.data.values()]
    )


class FujitsuHVACDevice(CoordinatorEntity, ClimateEntity):
    """Represent a Fujitsu HVAC device."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_HALVES
    _attr_target_temperature_step = 0.5
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: FujitsuHVACCoordinator, dev: FujitsuHVAC) -> None:
        """Set up static attributes."""
        super().__init__(coordinator, context=dev.device_serial_number)
        self._dev = dev

        self._attr_unique_id = dev.device_serial_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, dev.device_serial_number)},
            name=dev.device_name,
            manufacturer="Fujitsu",
            model=dev.property_values["model_name"],
            serial_number=dev.device_serial_number,
            sw_version=self._dev.property_values["mcu_firmware_version"],
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self._dev = self.coordinator.data[self._dev.device_serial_number]
        self.async_write_ha_state()

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting.

        Requires ClimateEntityFeature.FAN_MODE.
        """
        return FUJI_TO_HA_FAN.get(self._dev.fan_speed)

    @property
    def fan_modes(self) -> list[str]:
        """Return the list of available fan modes.

        Requires ClimateEntityFeature.FAN_MODE.
        """
        return [
            FUJI_TO_HA_FAN[mode]
            for mode in self._dev.supported_fan_speeds
            if mode in FUJI_TO_HA_FAN
        ]

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set Fan mode."""
        await self._dev.async_set_fan_speed(HA_TO_FUJI_FAN[fan_mode])
        await self.coordinator.async_request_refresh()

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        return FUJI_TO_HA_HVAC.get(self._dev.op_mode)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        return [
            FUJI_TO_HA_HVAC[mode]
            for mode in self._dev.supported_op_modes
            if mode in FUJI_TO_HA_HVAC
        ]

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        await self._dev.async_set_op_mode(HA_TO_FUJI_HVAC[hvac_mode])
        await self.coordinator.async_request_refresh()

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting.

        Requires ClimateEntityFeature.SWING_MODE.
        """
        return FUJI_TO_HA_SWING.get(self._dev.swing_mode)

    @property
    def swing_modes(self) -> list[str]:
        """Return the list of available swing modes.

        Requires ClimateEntityFeature.SWING_MODE.
        """
        return [
            FUJI_TO_HA_SWING[mode]
            for mode in self._dev.supported_swing_modes
            if mode in FUJI_TO_HA_SWING
        ]

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode."""
        await self._dev.async_set_swing_mode(HA_TO_FUJI_SWING[swing_mode])
        await self.coordinator.async_request_refresh()

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return float(self._dev.temperature_range[0])

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return float(self._dev.temperature_range[1])

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return float(self._dev.sensed_temp)

    @property
    def target_temperature(self) -> float:
        """Return the target temperature."""
        return float(self._dev.set_temp)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self._dev.async_set_set_temp(temperature)
        await self.coordinator.async_request_refresh()

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        ret = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        if self._dev.has_capability(Capability.OP_FAN):
            ret |= ClimateEntityFeature.FAN_MODE

        if self._dev.has_capability(
            Capability.SWING_HORIZONTAL
        ) or self._dev.has_capability(Capability.SWING_VERTICAL):
            ret |= ClimateEntityFeature.SWING_MODE

        return ret
