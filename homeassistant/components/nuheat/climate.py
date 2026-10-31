"""Climate entities for NuHeat thermostats."""

from asyncio import Lock, Task, current_task, gather, timeout
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from math import ceil
from typing import Any, override

from chemelex_nuheat import (
    NuHeatApiError,
    NuHeatPermissionError,
    NuHeatRateLimitError,
    ScheduleMode,
    Thermostat,
    ThermostatState,
)

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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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

CONTROL_OPERATION_TIMEOUT = 30.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NuHeatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the thermostats present during initial setup."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        NuHeatClimateEntity(coordinator, serial) for serial in sorted(coordinator.data)
    )


class NuHeatClimateEntity(CoordinatorEntity[NuHeatCoordinator], ClimateEntity):
    """A NuHeat thermostat using authoritative native Celsius data."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = PRESET_MODES
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    def __init__(self, coordinator: NuHeatCoordinator, serial_number: str) -> None:
        """Initialize one serial-based climate entity."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._setpoint_lock = Lock()
        self._control_tasks: set[Task[Any]] = set()
        self._controls_unloading = False
        self._attr_unique_id = serial_number

    def _check_control_available(self) -> None:
        if self._controls_unloading or self.coordinator.shutdown_requested:
            raise HomeAssistantError("NuHeat is unloading")
        if remaining := self.coordinator.cooldown_remaining:
            raise NuHeatRateLimitError(remaining)

    @asynccontextmanager
    async def _control_operation(self) -> AsyncIterator[None]:
        """Serialize bounded controls without queuing writes through cooldown."""
        task = current_task()
        try:
            self._check_control_available()
            if task is not None:
                self._control_tasks.add(task)
            async with timeout(CONTROL_OPERATION_TIMEOUT):
                async with self._setpoint_lock:
                    self._check_control_available()
                    try:
                        yield
                    finally:
                        if not self._controls_unloading:
                            self.coordinator.async_schedule_reconciliation()
        except NuHeatRateLimitError as err:
            if err.write_applied:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="write_unconfirmed"
                ) from err
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="rate_limited",
                translation_placeholders={"seconds": str(ceil(err.remaining))},
            ) from err
        except NuHeatPermissionError as err:
            if err.write_applied:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="write_unconfirmed"
                ) from err
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="permission_denied"
            ) from err
        except NuHeatApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="request_failed"
            ) from err
        except TimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="request_timeout"
            ) from err
        finally:
            if task is not None:
                self._control_tasks.discard(task)

    @override
    async def async_will_remove_from_hass(self) -> None:
        self._controls_unloading = True
        tasks = self._control_tasks - {current_task()}
        for task in tasks:
            task.cancel()
        if tasks:
            await gather(*tasks, return_exceptions=True)
        await super().async_will_remove_from_hass()

    @property
    def thermostat(self) -> Thermostat:
        """Return the latest authoritative device sample."""
        return self.coordinator.data[self._serial_number]

    @property
    @override
    def available(self) -> bool:
        return super().available and self.coordinator.is_thermostat_available(
            self._serial_number
        )

    @property
    @override
    def native_current_temperature(self) -> float | None:
        return self.thermostat.current_temperature

    @property
    @override
    def native_target_temperature(self) -> float | None:
        if self.thermostat.state is ThermostatState.STANDBY:
            return None
        return self.thermostat.target_temperature

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        return hvac_mode_for_thermostat(self.thermostat)

    @property
    @override
    def preset_mode(self) -> str | None:
        return preset_for_thermostat(self.thermostat)

    @property
    @override
    def hvac_action(self) -> HVACAction:
        if self.thermostat.state is ThermostatState.STANDBY:
            return HVACAction.OFF
        return HVACAction.HEATING if self.thermostat.heating else HVACAction.IDLE

    def _command_temperature(self) -> float:
        temperature = self.thermostat.target_temperature
        if (
            temperature is None
            or not DEFAULT_MIN_TEMP <= temperature <= DEFAULT_MAX_TEMP
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="target_temperature_required"
            )
        return temperature

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        async with self._control_operation():
            requested_mode = kwargs.get(ATTR_HVAC_MODE)
            if requested_mode is HVACMode.OFF:
                await self.coordinator.api.set_standby(self._serial_number)
                return
            if self.hvac_mode is HVACMode.OFF and requested_mode is None:
                requested_mode = HVACMode.HEAT
            try:
                mode = setpoint_command_mode(self.thermostat, requested_mode)
            except ValueError as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unsupported_state",
                    translation_placeholders={"state": self.thermostat.state},
                ) from err
            command: dict[str, Any] = {"mode": mode}
            if (
                requested_mode is None
                and mode is ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE
                and self.thermostat.state is ThermostatState.TIMED_HOLD
                and self.thermostat.hold_until is not None
            ):
                command["hold_until"] = self.thermostat.hold_until
            await self.coordinator.api.set_target_temperature(
                self._serial_number, float(temperature), **command
            )

    async def _async_set_mode(self, mode: ScheduleMode) -> None:
        if mode is ScheduleMode.AUTO:
            await self.coordinator.api.set_schedule_mode(self._serial_number, mode)
        else:
            await self.coordinator.api.set_schedule_mode(
                self._serial_number, mode, temperature=self._command_temperature()
            )

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        async with self._control_operation():
            if hvac_mode is HVACMode.OFF:
                await self.coordinator.api.set_standby(self._serial_number)
            else:
                await self._async_set_mode(api_mode_for_hvac_mode(hvac_mode))

    @override
    async def async_turn_off(self) -> None:
        """Enter frost-protected Standby, not electrical isolation."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    @override
    async def async_turn_on(self) -> None:
        """Exit Standby and resume the schedule."""
        await self.async_set_hvac_mode(HVACMode.AUTO)

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        async with self._control_operation():
            try:
                mode = api_mode_for_preset(preset_mode)
            except ValueError as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unsupported_preset",
                    translation_placeholders={"preset": preset_mode},
                ) from err
            await self._async_set_mode(mode)

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
