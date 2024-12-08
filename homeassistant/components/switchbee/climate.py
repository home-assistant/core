"""Support for SwitchBee climate."""

from __future__ import annotations

from typing import Any

from switchbee.api.central_unit import SwitchBeeDeviceOfflineError, SwitchBeeError
from switchbee.const import (
    ApiAttribute,
    ThermostatFanSpeed,
    ThermostatMode,
    ThermostatTemperatureUnit,
)
from switchbee.device import ApiStateCommand, SwitchBeeThermostat

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SwitchBeeCoordinator
from .entity import SwitchBeeDeviceEntity

FAN_SB_TO_HASS = {
    ThermostatFanSpeed.AUTO: FAN_AUTO,
    ThermostatFanSpeed.LOW: FAN_LOW,
    ThermostatFanSpeed.MEDIUM: FAN_MEDIUM,
    ThermostatFanSpeed.HIGH: FAN_HIGH,
}

FAN_HASS_TO_SB: dict[str | None, str] = {
    FAN_AUTO: ThermostatFanSpeed.AUTO,
    FAN_LOW: ThermostatFanSpeed.LOW,
    FAN_MEDIUM: ThermostatFanSpeed.MEDIUM,
    FAN_HIGH: ThermostatFanSpeed.HIGH,
}

HVAC_MODE_SB_TO_HASS = {
    ThermostatMode.COOL: HVACMode.COOL,
    ThermostatMode.HEAT: HVACMode.HEAT,
    ThermostatMode.FAN: HVACMode.FAN_ONLY,
}

HVAC_MODE_HASS_TO_SB: dict[HVACMode | str | None, str] = {
    HVACMode.COOL: ThermostatMode.COOL,
    HVACMode.HEAT: ThermostatMode.HEAT,
    HVACMode.FAN_ONLY: ThermostatMode.FAN,
}

HVAC_ACTION_SB_TO_HASS = {
    ThermostatMode.COOL: HVACAction.COOLING,
    ThermostatMode.HEAT: HVACAction.HEATING,
    ThermostatMode.FAN: HVACAction.FAN,
}

HVAC_UNIT_SB_TO_HASS = {
    ThermostatTemperatureUnit.CELSIUS: UnitOfTemperature.CELSIUS,
    ThermostatTemperatureUnit.FAHRENHEIT: UnitOfTemperature.FAHRENHEIT,
}

SUPPORTED_FAN_MODES = [FAN_AUTO, FAN_HIGH, FAN_MEDIUM, FAN_LOW]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up SwitchBee climate."""
    coordinator: SwitchBeeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SwitchBeeClimateEntity(switchbee_device, coordinator)
        for switchbee_device in coordinator.data.values()
        if isinstance(switchbee_device, SwitchBeeThermostat)
    )


class SwitchBeeClimateEntity(SwitchBeeDeviceEntity[SwitchBeeThermostat], ClimateEntity):
    """Representation of a SwitchBee climate."""

    _attr_fan_modes = SUPPORTED_FAN_MODES
    _attr_target_temperature_step = 1

    def __init__(
        self,
        device: SwitchBeeThermostat,
        coordinator: SwitchBeeCoordinator,
    ) -> None:
        """Initialize the Switchbee switch."""
        super().__init__(device, coordinator)
        # set HVAC capabilities
        self._attr_max_temp = device.max_temperature
        self._attr_min_temp = device.min_temperature
        self._attr_temperature_unit = HVAC_UNIT_SB_TO_HASS[device.temperature_unit]
        self._attr_hvac_modes = [HVAC_MODE_SB_TO_HASS[mode] for mode in device.modes]
        self._attr_hvac_modes.append(HVACMode.OFF)
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        )
        if len(self.hvac_modes) > 1:
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )
        self._update_attrs_from_coordinator()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs_from_coordinator()
        super()._handle_coordinator_update()

    def _update_attrs_from_coordinator(self) -> None:
        coordinator_device = self._get_coordinator_device()

        self._attr_hvac_mode: HVACMode = (
            HVACMode.OFF
            if coordinator_device.state == ApiStateCommand.OFF
            else HVAC_MODE_SB_TO_HASS[coordinator_device.mode]
        )
        self._attr_fan_mode = FAN_SB_TO_HASS[coordinator_device.fan]
        self._attr_current_temperature = coordinator_device.temperature
        self._attr_target_temperature = coordinator_device.target_temperature

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""

        if hvac_mode == HVACMode.OFF:
            await self._operate(power=ApiStateCommand.OFF)
        else:
            await self._operate(
                power=ApiStateCommand.ON, mode=HVAC_MODE_HASS_TO_SB[hvac_mode]
            )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self._operate(target_temperature=kwargs[ATTR_TEMPERATURE])

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set AC fan mode."""
        await self._operate(fan=FAN_HASS_TO_SB[fan_mode])

    async def _operate(
        self,
        power: str | None = None,
        mode: str | None = None,
        fan: str | None = None,
        target_temperature: int | None = None,
    ) -> None:
        """Send request to central unit."""

        if power is None:
            power = ApiStateCommand.ON
            if self.hvac_mode == HVACMode.OFF:
                power = ApiStateCommand.OFF
        if mode is None:
            mode = HVAC_MODE_HASS_TO_SB[self.hvac_mode]
        if fan is None:
            fan = FAN_HASS_TO_SB[self.fan_mode]
        if target_temperature is None:
            target_temperature = int(self.target_temperature or 0)

        state: dict[str, int | str] = {
            ApiAttribute.POWER: power,
            ApiAttribute.MODE: mode,
            ApiAttribute.FAN: fan,
            ApiAttribute.CONFIGURED_TEMPERATURE: target_temperature,
        }

        try:
            await self.coordinator.api.set_state(self._device.id, state)
        except (SwitchBeeError, SwitchBeeDeviceOfflineError) as exp:
            raise HomeAssistantError(
                f"Failed to set {self.name} state {state}, error: {exp!s}"
            ) from exp

        await self.coordinator.async_refresh()
