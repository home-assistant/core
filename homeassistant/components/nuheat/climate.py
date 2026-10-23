"""Climate entities for NuHeat thermostats."""

from asyncio import Lock
from datetime import UTC, datetime
from math import isfinite
from typing import Any, override
from zoneinfo import ZoneInfo

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
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from . import NuHeatConfigEntry
from .behavior import (
    api_mode_for_hvac_mode,
    api_mode_for_preset,
    hvac_mode_for_thermostat,
    preset_for_thermostat,
    setpoint_command_mode,
)
from .const import DOMAIN, PRESET_MODES
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
        self._setpoint_lock = Lock()
        self._attr_unique_id = serial_number
        self._attr_native_temperature_unit = (
            coordinator.hass.config.units.temperature_unit
        )
        self._attr_target_temperature_step = (
            0.5
            if self._attr_native_temperature_unit == UnitOfTemperature.CELSIUS
            else 1.0
        )

    @property
    def thermostat(self) -> Thermostat:
        """Return the latest thermostat state."""
        return self.coordinator.data[self._serial_number]

    def _from_celsius(self, value: float) -> float:
        return TemperatureConverter.convert(
            value, UnitOfTemperature.CELSIUS, self.native_temperature_unit
        )

    def _to_celsius(self, value: float) -> float:
        return TemperatureConverter.convert(
            value, self.native_temperature_unit, UnitOfTemperature.CELSIUS
        )

    @property
    def _optimistic_standby(self) -> bool:
        """Bound Standby display to the coordinator's current intent."""
        return (
            self.coordinator.pending_mode(self._serial_number)
            is ThermostatState.STANDBY
        )

    def _command_temperature(self) -> float | None:
        """Preserve an accepted target while switching mode before readback."""
        if (
            pending := self.coordinator.pending_setpoint(self._serial_number)
        ) is not None:
            return pending
        return self.thermostat.target_temperature

    @property
    @override
    def available(self) -> bool:
        return super().available and self.coordinator.is_thermostat_available(
            self._serial_number
        )

    @property
    @override
    def native_current_temperature(self) -> float | None:
        if (temperature := self.thermostat.current_temperature) is None:
            return None
        return self._from_celsius(temperature)

    @property
    @override
    def native_target_temperature(self) -> float | None:
        if (
            pending := self.coordinator.pending_setpoint(self._serial_number)
        ) is not None:
            return self._from_celsius(pending)
        if self._optimistic_standby or self.thermostat.state is ThermostatState.STANDBY:
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
        if self._optimistic_standby or self.thermostat.state is ThermostatState.STANDBY:
            return HVACAction.OFF
        return HVACAction.HEATING if self.thermostat.heating else HVACAction.IDLE

    @property
    @override
    def assumed_state(self) -> bool:
        """Return whether a successful command is awaiting cloud confirmation."""
        return (
            self.coordinator.pending_mode(self._serial_number) is not None
            or self.coordinator.pending_setpoint(self._serial_number) is not None
        )

    @property
    @override
    def preset_mode(self) -> str | None:
        return preset_for_thermostat(self.thermostat)

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        # Serialize setpoints so a slow earlier command cannot replace a newer
        # request with its completion. Keep vendor mode/hold selection unchanged.
        async with self._setpoint_lock:
            await self._async_set_temperature(**kwargs)

    async def _async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        requested_hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        pending_mode = self.coordinator.pending_mode(self._serial_number)
        if (
            self.hvac_mode is HVACMode.OFF
            and requested_hvac_mode is None
            and pending_mode in (None, ThermostatState.STANDBY)
        ):
            # A setpoint from OFF exits Standby using Manual.
            requested_hvac_mode = HVACMode.HEAT
        try:
            if requested_hvac_mode is None and pending_mode in (
                ThermostatState.SCHEDULED,
                ThermostatState.TIMED_HOLD,
                ThermostatState.PERMANENT_HOLD,
                ThermostatState.MANUAL,
            ):
                mode = {
                    ThermostatState.SCHEDULED: ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE,
                    ThermostatState.TIMED_HOLD: ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE,
                    ThermostatState.PERMANENT_HOLD: ScheduleMode.PERMANENT_HOLD,
                    ThermostatState.MANUAL: ScheduleMode.MANUAL,
                }[pending_mode]
            else:
                mode = setpoint_command_mode(self.thermostat, requested_hvac_mode)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_state",
                translation_placeholders={"state": self.thermostat.state},
            ) from err
        temperature_celsius = self._to_celsius(float(temperature))
        hold_until = None
        if (
            pending_mode is None
            and mode is ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE
            and self.thermostat.state is ThermostatState.TIMED_HOLD
            and self.thermostat.hold_until is not None
        ):
            hold_until = self.thermostat.hold_until
        if (
            requested_hvac_mode is None
            and (
                pending_until := self.coordinator.pending_hold_until(
                    self._serial_number
                )
            )
            is not None
        ):
            mode = ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE
            hold_until = pending_until
        await self._async_write_setpoint(temperature_celsius, mode, hold_until)

    async def async_set_temporary_hold(
        self, temperature: float, hold_until: datetime
    ) -> None:
        """Hold a target until an explicit future time in HA's timezone."""
        async with self._setpoint_lock:
            temperature_celsius = self._to_celsius(temperature)
            if not isfinite(temperature_celsius) or not (
                DEFAULT_MIN_TEMP <= temperature_celsius <= DEFAULT_MAX_TEMP
            ):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_hold_temperature",
                )
            if hold_until.tzinfo is None:
                zone = ZoneInfo(self.hass.config.time_zone)
                candidates = [
                    hold_until.replace(tzinfo=zone, fold=fold) for fold in (0, 1)
                ]
                valid = [
                    item
                    for item in candidates
                    if item.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
                    == hold_until
                ]
                if not valid or len({item.utcoffset() for item in valid}) != 1:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN, translation_key="invalid_hold_time"
                    )
                hold_until = valid[0]
            hold_until = hold_until.astimezone(UTC)
            if hold_until <= dt_util.utcnow():
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="invalid_hold_time"
                )
            await self._async_write_setpoint(
                temperature_celsius, ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE, hold_until
            )

    async def _async_write_setpoint(
        self,
        temperature_celsius: float,
        mode: ScheduleMode,
        hold_until: datetime | None = None,
    ) -> None:
        """Share the existing write, optimism and reconciliation contract."""
        command_kwargs: dict[str, Any] = {"mode": mode}
        if hold_until is not None:
            command_kwargs["hold_until"] = hold_until
        try:
            await self.coordinator.api.set_target_temperature(
                self._serial_number,
                temperature_celsius,
                **command_kwargs,
            )
        except Exception:
            # The library also GETs after PUT: an exception need not mean that
            # the write failed. Read later, without retrying or assuming success.
            self.coordinator.async_schedule_reconciliation()
            raise
        self.coordinator.async_set_pending_mode(self._serial_number, mode)
        self.coordinator.async_set_pending_setpoint(
            self._serial_number, temperature_celsius, hold_until=hold_until
        )
        await self.coordinator.async_request_refresh()

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        async with self._setpoint_lock:
            await self._async_set_hvac_mode(hvac_mode)

    async def _async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode is HVACMode.OFF:
            await self._async_turn_off()
            return
        mode = api_mode_for_hvac_mode(hvac_mode)
        try:
            if mode is ScheduleMode.AUTO:
                await self.coordinator.api.set_schedule_mode(self._serial_number, mode)
            else:
                await self.coordinator.api.set_schedule_mode(
                    self._serial_number,
                    mode,
                    temperature=self._command_temperature(),
                )
        except Exception:
            self.coordinator.async_schedule_reconciliation()
            raise
        self.coordinator.async_clear_pending_setpoint(self._serial_number)
        self.coordinator.async_set_pending_mode(self._serial_number, mode)
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self) -> None:
        """Enter NuHeat's frost-protected Standby state."""
        async with self._setpoint_lock:
            await self._async_turn_off()

    async def _async_turn_off(self) -> None:
        try:
            await self.coordinator.api.set_standby(self._serial_number)
        except Exception:
            self.coordinator.async_schedule_reconciliation()
            raise
        self.coordinator.async_clear_pending_setpoint(self._serial_number)
        self.coordinator.async_set_pending_mode(self._serial_number, None)
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_on(self) -> None:
        """Resume the schedule and exit Standby."""
        await self.async_set_hvac_mode(HVACMode.AUTO)

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        async with self._setpoint_lock:
            await self._async_set_preset_mode(preset_mode)

    async def _async_set_preset_mode(self, preset_mode: str) -> None:
        try:
            mode = api_mode_for_preset(preset_mode)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_preset",
                translation_placeholders={"preset": preset_mode},
            ) from err
        try:
            if mode is ScheduleMode.AUTO:
                await self.coordinator.api.set_schedule_mode(self._serial_number, mode)
            else:
                # Permanent Hold uses the verified v1 schedule-mode-3 request;
                # Temporary Hold without an end lasts until the next schedule event.
                await self.coordinator.api.set_schedule_mode(
                    self._serial_number,
                    mode,
                    temperature=self._command_temperature(),
                )
        except Exception:
            self.coordinator.async_schedule_reconciliation()
            raise
        self.coordinator.async_clear_pending_setpoint(self._serial_number)
        self.coordinator.async_set_pending_mode(self._serial_number, mode)
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
