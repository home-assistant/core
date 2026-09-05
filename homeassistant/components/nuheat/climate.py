"""Climate entities for NuHeat thermostats."""

from typing import Any, override

from chemelex_nuheat import ScheduleMode, Thermostat, ThermostatState

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.unit_conversion import TemperatureConverter

from . import NuHeatConfigEntry
from .behavior import (
    api_mode_for_hvac_mode,
    api_mode_for_preset,
    hvac_mode_for_thermostat,
    preset_for_thermostat,
    setpoint_command_mode,
)
from .const import DOMAIN, PRESET_MODES, PRESET_PERMANENT_HOLD
from .coordinator import NuHeatCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NuHeatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create entities initially and when later polls discover thermostats."""
    coordinator = entry.runtime_data.coordinator
    known_serials: set[str] = set()

    def async_add_new_entities() -> None:
        new_serials = set(coordinator.data or {}) - known_serials
        if not new_serials:
            return
        known_serials.update(new_serials)
        async_add_entities(
            NuHeatClimateEntity(coordinator, serial_number)
            for serial_number in sorted(new_serials)
        )

    async_add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(async_add_new_entities))


class NuHeatClimateEntity(CoordinatorEntity[NuHeatCoordinator], ClimateEntity):
    """A NuHeat radiant-floor thermostat."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "thermostat"
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = PRESET_MODES
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    def __init__(self, coordinator: NuHeatCoordinator, serial_number: str) -> None:
        """Initialize a NuHeat thermostat entity."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        # Standby is verified as Manual at 5°C, but documented GET fields cannot
        # distinguish it. This memory is authoritative only for commands sent by
        # this running entity; external changes may remain invisible until HA
        # sends another command or restarts.
        self._optimistic_standby = False
        self._attr_unique_id = serial_number
        self._attr_temperature_unit = coordinator.hass.config.units.temperature_unit
        self._attr_target_temperature_step = (
            0.5 if self._attr_temperature_unit == UnitOfTemperature.CELSIUS else 1.0
        )

    @property
    def thermostat(self) -> Thermostat:
        """Return the latest thermostat state."""
        return self.coordinator.data[self._serial_number]

    def _from_celsius(self, value: float) -> float:
        return TemperatureConverter.convert(
            value, UnitOfTemperature.CELSIUS, self.temperature_unit
        )

    def _to_celsius(self, value: float) -> float:
        return TemperatureConverter.convert(
            value, self.temperature_unit, UnitOfTemperature.CELSIUS
        )

    @property
    @override
    def available(self) -> bool:
        return super().available and self.coordinator.is_thermostat_available(
            self._serial_number
        )

    @property
    @override
    def current_temperature(self) -> float | None:
        if (temperature := self.thermostat.current_temperature) is None:
            return None
        return self._from_celsius(temperature)

    @property
    @override
    def target_temperature(self) -> float | None:
        if self._optimistic_standby:
            return None
        if (temperature := self.thermostat.target_temperature) is None:
            return None
        return self._from_celsius(temperature)

    @property
    @override
    def min_temp(self) -> float:
        # OpenAPI v2 does not expose the thermostat's native minimum.
        return self._from_celsius(DEFAULT_MIN_TEMP)

    @property
    @override
    def max_temp(self) -> float:
        # OpenAPI v2 does not expose the thermostat's native maximum.
        return self._from_celsius(DEFAULT_MAX_TEMP)

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        if self._optimistic_standby:
            return HVACMode.OFF
        return hvac_mode_for_thermostat(self.thermostat)

    @property
    @override
    def hvac_action(self) -> HVACAction:
        if self._optimistic_standby:
            return HVACAction.OFF
        return HVACAction.HEATING if self.thermostat.heating else HVACAction.IDLE

    @property
    @override
    def assumed_state(self) -> bool:
        """Return whether OFF is remembered from an unobservable command."""
        return self._optimistic_standby

    @property
    @override
    def preset_mode(self) -> str | None:
        return preset_for_thermostat(self.thermostat)

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        requested_hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if self._optimistic_standby and requested_hvac_mode is None:
            # A setpoint from optimistic OFF exits Standby using Manual.
            requested_hvac_mode = HVACMode.HEAT
        try:
            mode = setpoint_command_mode(self.thermostat, requested_hvac_mode)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_state",
                translation_placeholders={"state": self.thermostat.state},
            ) from err
        temperature_celsius = self._to_celsius(float(temperature))
        if (
            mode is ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE
            and self.thermostat.state is ThermostatState.TIMED_HOLD
            and self.thermostat.hold_until is not None
        ):
            await self.coordinator.api.set_target_temperature(
                self._serial_number,
                temperature_celsius,
                mode=mode,
                hold_until=self.thermostat.hold_until,
            )
        else:
            await self.coordinator.api.set_target_temperature(
                self._serial_number,
                temperature_celsius,
                mode=mode,
            )
        self._optimistic_standby = False
        await self.coordinator.async_request_refresh()

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode is HVACMode.OFF:
            await self.async_turn_off()
            return
        mode = api_mode_for_hvac_mode(hvac_mode)
        if mode is ScheduleMode.AUTO:
            await self.coordinator.api.set_schedule_mode(self._serial_number, mode)
        else:
            await self.coordinator.api.set_schedule_mode(
                self._serial_number,
                mode,
                temperature=self.thermostat.target_temperature,
            )
        self._optimistic_standby = False
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self) -> None:
        """Enter NuHeat's frost-protected Standby state."""
        await self.coordinator.api.set_standby(self._serial_number)
        self._optimistic_standby = True
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_on(self) -> None:
        """Resume the schedule and exit Standby."""
        await self.async_set_hvac_mode(HVACMode.AUTO)

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == PRESET_PERMANENT_HOLD:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="indefinite_hold_unsupported",
            )
        try:
            mode = api_mode_for_preset(preset_mode)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_preset",
                translation_placeholders={"preset": preset_mode},
            ) from err
        if mode is ScheduleMode.AUTO:
            await self.coordinator.api.set_schedule_mode(self._serial_number, mode)
        else:
            # A Hold command without an end is verified to last until the next
            # scheduled event; it does not create an indefinite hold.
            await self.coordinator.api.set_schedule_mode(
                self._serial_number,
                mode,
                temperature=self.thermostat.target_temperature,
            )
        self._optimistic_standby = False
        await self.coordinator.async_request_refresh()

    @property
    @override
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_number)},
            serial_number=self._serial_number,
            name=self.thermostat.name or self._serial_number,
            manufacturer="Chemelex / NuHeat",
            suggested_area=self.thermostat.name,
        )
