"""Support for Škoda climate control."""

from typing import Any, override

from skoda_public_api.models.enums import (
    AirConditioningState,
    TemperatureUnit,
    VehicleCapability,
    VehicleOperationName,
)

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from .coordinator import SkodaConfigEntry, SkodaUpdateCoordinator
from .entity import SkodaEntity

PARALLEL_UPDATES = 1

_REQUIRED_OPERATIONS = frozenset(
    {
        VehicleOperationName.START_AIR_CONDITIONING,
        VehicleOperationName.STOP_AIR_CONDITIONING,
    }
)

_HVAC_ACTION_MAP = {
    AirConditioningState.OFF: HVACAction.OFF,
    AirConditioningState.COMPLETED: HVACAction.OFF,
    AirConditioningState.COOLING: HVACAction.COOLING,
    AirConditioningState.HEATING: HVACAction.HEATING,
    AirConditioningState.HEATING_AUXILIARY: HVACAction.HEATING,
    AirConditioningState.VENTILATION: HVACAction.FAN,
}

_HVAC_MODE_MAP = {
    HVACAction.OFF: HVACMode.OFF,
    HVACAction.COOLING: HVACMode.HEAT_COOL,
    HVACAction.HEATING: HVACMode.HEAT_COOL,
    HVACAction.FAN: HVACMode.HEAT_COOL,
}

CLIMATE_DESCRIPTION = ClimateEntityDescription(
    key="air_conditioning",
    translation_key="air_conditioning",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Škoda climate control from ConfigEntry runtime_data."""
    coordinator = entry.runtime_data.coordinator
    vehicle_response = coordinator.data.vehicle_response
    capabilities = vehicle_response.supported_capabilities()
    operations = vehicle_response.supported_operations()

    # The operations list can be temporarily unavailable, in which case only the
    # capability is checked so a transient error does not hide the entity.
    if VehicleCapability.AIR_CONDITIONING in capabilities and (
        operations is None or operations >= _REQUIRED_OPERATIONS
    ):
        async_add_entities([SkodaClimate(coordinator)])


class SkodaClimate(SkodaEntity, ClimateEntity):
    """Air conditioning of a Škoda vehicle."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 16.0
    _attr_max_temp = 30.0
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: SkodaUpdateCoordinator) -> None:
        """Initialize the climate entity."""
        self.entity_description = CLIMATE_DESCRIPTION
        super().__init__(coordinator, coordinator.vin)
        self._reported_target_temperature: float | None = None
        self._update_attrs()

    def _vehicle_target_temperature(self) -> float | None:
        """Return the target temperature reported by the vehicle in Celsius."""
        air_conditioning = self.open_api_air_conditioning
        if air_conditioning is None or air_conditioning.target_temperature is None:
            return None
        target = air_conditioning.target_temperature
        if target.unit == TemperatureUnit.FAHRENHEIT:
            return round(
                TemperatureConverter.convert(
                    target.value,
                    UnitOfTemperature.FAHRENHEIT,
                    UnitOfTemperature.CELSIUS,
                ),
                1,
            )
        return target.value

    def _update_attrs(self) -> None:
        """Update the entity attributes from the latest vehicle data."""
        air_conditioning = self.open_api_air_conditioning
        action = (
            _HVAC_ACTION_MAP.get(air_conditioning.state)
            if air_conditioning is not None
            else None
        )
        self._attr_hvac_action = action
        self._attr_hvac_mode = _HVAC_MODE_MAP.get(action) if action else None

        # Keep a target temperature chosen in Home Assistant until the vehicle
        # reports a different one. A poll without a target does not count.
        reported = self._vehicle_target_temperature()
        if reported is not None and reported != self._reported_target_temperature:
            self._reported_target_temperature = reported
            self._attr_native_target_temperature = reported

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Update the climate state from the latest vehicle data."""
        self._update_attrs()
        super()._handle_coordinator_update()

    async def _async_start(self, temperature: float | None) -> None:
        """Start the air conditioning, using the vehicle's own target if unknown."""
        await self.async_send_command(
            self.coordinator.openapi.start_air_conditioning(self.vin, temperature)
        )
        self._attr_hvac_mode = HVACMode.HEAT_COOL

    async def _async_stop(self) -> None:
        """Stop the air conditioning."""
        await self.async_send_command(
            self.coordinator.openapi.stop_air_conditioning(self.vin)
        )
        self._attr_hvac_mode = HVACMode.OFF

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Start or stop the air conditioning."""
        if hvac_mode == HVACMode.HEAT_COOL:
            await self._async_start(self.native_target_temperature)
        else:
            await self._async_stop()
        self.async_write_ha_state()

    @override
    async def async_turn_on(self) -> None:
        """Start the air conditioning."""
        await self.async_set_hvac_mode(HVACMode.HEAT_COOL)

    @override
    async def async_turn_off(self) -> None:
        """Stop the air conditioning."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature, applying a requested HVAC mode as well."""
        temperature: float = kwargs[ATTR_TEMPERATURE]
        hvac_mode = kwargs.get(ATTR_HVAC_MODE, self.hvac_mode)
        if hvac_mode == HVACMode.HEAT_COOL:
            await self._async_start(temperature)
        elif hvac_mode == HVACMode.OFF and self.hvac_mode != HVACMode.OFF:
            await self._async_stop()
        self._attr_native_target_temperature = temperature
        self.async_write_ha_state()
