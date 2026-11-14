"""Support for VeSync thermostats."""

from typing import Any, override

from pyvesync.base_devices.thermostat_base import VeSyncThermostat
from pyvesync.const import (
    ThermostatFanModes,
    ThermostatWorkModes,
    ThermostatWorkStatusCodes,
)

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import is_thermostat
from .const import VS_DEVICES, VS_DISCOVERY
from .coordinator import VesyncConfigEntry, VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

PARALLEL_UPDATES = 1

FAN_CIRCULATE = "circulate"

# Emergency heat is reported as heat and cannot be selected from Home Assistant.
VS_TO_HA_HVAC_MODE = {
    ThermostatWorkModes.OFF: HVACMode.OFF,
    ThermostatWorkModes.HEAT: HVACMode.HEAT,
    ThermostatWorkModes.COOL: HVACMode.COOL,
    ThermostatWorkModes.AUTO: HVACMode.HEAT_COOL,
    ThermostatWorkModes.SMART_AUTO: HVACMode.AUTO,
    ThermostatWorkModes.EM_HEAT: HVACMode.HEAT,
}
HA_TO_VS_HVAC_MODE = {
    HVACMode.OFF: ThermostatWorkModes.OFF,
    HVACMode.HEAT: ThermostatWorkModes.HEAT,
    HVACMode.COOL: ThermostatWorkModes.COOL,
    HVACMode.HEAT_COOL: ThermostatWorkModes.AUTO,
    HVACMode.AUTO: ThermostatWorkModes.SMART_AUTO,
}

VS_TO_HA_FAN_MODE = {
    ThermostatFanModes.AUTO: FAN_AUTO,
    ThermostatFanModes.ON: FAN_ON,
    ThermostatFanModes.CIRCULATE: FAN_CIRCULATE,
}
HA_TO_VS_FAN_MODE = {v: k for k, v in VS_TO_HA_FAN_MODE.items()}

VS_TO_HA_HVAC_ACTION = {
    ThermostatWorkStatusCodes.HEATING: HVACAction.HEATING,
    ThermostatWorkStatusCodes.EM_HEATING: HVACAction.HEATING,
    ThermostatWorkStatusCodes.COOLING: HVACAction.COOLING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VesyncConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the VeSync climate platform."""

    coordinator = config_entry.runtime_data

    @callback
    def discover(devices: list[VeSyncThermostat]) -> None:
        """Add new devices to platform."""
        _setup_entities(
            [dev for dev in devices if is_thermostat(dev)],
            async_add_entities,
            coordinator,
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(
        config_entry.runtime_data.manager.devices.thermostats,
        async_add_entities,
        coordinator,
    )


@callback
def _setup_entities(
    devices: list[VeSyncThermostat],
    async_add_entities: AddConfigEntryEntitiesCallback,
    coordinator: VeSyncDataCoordinator,
) -> None:
    """Add climate entities."""
    async_add_entities(VeSyncThermostatHA(dev, coordinator) for dev in devices)


class VeSyncThermostatHA(VeSyncBaseEntity[VeSyncThermostat], ClimateEntity):
    """Representation of a VeSync thermostat."""

    _attr_name = None
    _attr_translation_key = "vesync"
    _attr_precision = PRECISION_TENTHS
    _attr_target_temperature_step = 1
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        device: VeSyncThermostat,
        coordinator: VeSyncDataCoordinator,
    ) -> None:
        """Initialize the VeSync thermostat."""
        super().__init__(device, coordinator)
        self._attr_hvac_modes = [
            mode
            for mode, vs_mode in HA_TO_VS_HVAC_MODE.items()
            if vs_mode in device.supported_work_modes
        ]
        self._attr_fan_modes = [
            VS_TO_HA_FAN_MODE[ThermostatFanModes(mode)]
            for mode in device.fan_modes
            if mode in VS_TO_HA_FAN_MODE
        ]

    @property
    @override
    def native_temperature_unit(self) -> str:
        """Return the unit of measurement used by the device."""
        if (self.device.state.temperature_unit or "").lower() in ("c", "celsius"):
            return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT

    @property
    @override
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.device.state.temperature

    @property
    @override
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self.device.state.humidity

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        if self.device.state.work_mode is None:
            return None
        return VS_TO_HA_HVAC_MODE.get(self.device.state.work_mode)

    @property
    @override
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        state = self.device.state
        if state.work_status is None:
            return None
        if (action := VS_TO_HA_HVAC_ACTION.get(state.work_status)) is not None:
            return action
        if state.is_fan_on:
            return HVACAction.FAN
        if state.work_mode == ThermostatWorkModes.OFF:
            return HVACAction.OFF
        return HVACAction.IDLE

    @property
    @override
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        if self.device.state.fan_mode is None:
            return None
        return VS_TO_HA_FAN_MODE.get(self.device.state.fan_mode)

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return the target temperature in single setpoint modes."""
        if self.hvac_mode == HVACMode.HEAT:
            return self.device.state.heat_to_temp
        if self.hvac_mode == HVACMode.COOL:
            return self.device.state.cool_to_temp
        return None

    @property
    @override
    def native_target_temperature_low(self) -> float | None:
        """Return the lower bound target temperature in range modes."""
        if self.hvac_mode in (HVACMode.HEAT_COOL, HVACMode.AUTO):
            return self.device.state.heat_to_temp
        return None

    @property
    @override
    def native_target_temperature_high(self) -> float | None:
        """Return the upper bound target temperature in range modes."""
        if self.hvac_mode in (HVACMode.HEAT_COOL, HVACMode.AUTO):
            return self.device.state.cool_to_temp
        return None

    def _raise_for_failure(self, action: str) -> None:
        if self.device.last_response:
            raise HomeAssistantError(self.device.last_response.message)
        raise HomeAssistantError(f"Failed to {action}.")

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        if not await self.device.set_mode(HA_TO_VS_HVAC_MODE[hvac_mode]):
            self._raise_for_failure("set HVAC mode")
        await self.coordinator.async_request_refresh()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        if not await self.device.set_fan_mode(HA_TO_VS_FAN_MODE[fan_mode]):
            self._raise_for_failure("set fan mode")
        await self.coordinator.async_request_refresh()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        if (low := kwargs.get(ATTR_TARGET_TEMP_LOW)) is not None:
            if not await self.device.set_heat_to_temp(low):
                self._raise_for_failure("set heat to temperature")
        if (high := kwargs.get(ATTR_TARGET_TEMP_HIGH)) is not None:
            if not await self.device.set_cool_to_temp(high):
                self._raise_for_failure("set cool to temperature")
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            if self.hvac_mode == HVACMode.COOL:
                success = await self.device.set_cool_to_temp(temperature)
            else:
                success = await self.device.set_heat_to_temp(temperature)
            if not success:
                self._raise_for_failure("set temperature")
        await self.coordinator.async_request_refresh()
