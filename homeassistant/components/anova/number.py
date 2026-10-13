"""Support for Anova Numbers."""

from typing import override

from anova_wifi import Capability, CommandFailure, NoActiveCookError, WebsocketFailure

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import STATE_UNKNOWN, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import AnovaConfigEntry, AnovaCoordinator
from .entity import AnovaEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnovaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Anova number entities."""
    anova_data = entry.runtime_data

    # anova-wifi 2.0.0 reports a3 temperatures in the device's display unit
    # and never publishes a cook time; gate the numbers until the fix ships.
    async_add_entities(
        entity
        for coordinator in anova_data.coordinators
        if coordinator.anova_device.type != "a3"
        and Capability.UPDATE_RUNNING_COOK
        in coordinator.anova_device.supported_capabilities
        for entity in (
            AnovaTargetTemperatureNumber(coordinator),
            AnovaTimerNumber(coordinator),
        )
    )


class AnovaTargetTemperatureNumber(AnovaEntity, RestoreNumber):
    """The target temperature for the current, or next, cook.

    While idle, this is held locally (mirroring the official app) and used
    when the cook switch is turned on. While a cook is running, it reflects
    and updates the live job via update_running_cook.
    """

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: AnovaCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = NumberEntityDescription(
            key="target_temperature", translation_key="target_temperature"
        )
        self._attr_unique_id = f"{coordinator.device_unique_id}_target_temperature"

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last locally-set value, if any, overriding the coordinator's seed."""
        if (
            (last_state := await self.async_get_last_state())
            and (last_number_data := await self.async_get_last_number_data())
            and last_state.state != STATE_UNKNOWN
            and last_number_data.native_value is not None
        ):
            self.coordinator.pending_target_temperature = last_number_data.native_value
        if (
            self.coordinator.anova_device.is_cooking
            and self.coordinator.data is not None
        ):
            self._attr_native_value = self.coordinator.data.sensor.target_temperature
        else:
            self._attr_native_value = self.coordinator.pending_target_temperature
        await super().async_added_to_hass()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Reflect the live job's target temperature while cooking, else the pending value."""
        if (
            self.coordinator.anova_device.is_cooking
            and self.coordinator.data is not None
        ):
            self._attr_native_value = self.coordinator.data.sensor.target_temperature
        else:
            self._attr_native_value = self.coordinator.pending_target_temperature
        super()._handle_coordinator_update()

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the target temperature."""
        if not self.coordinator.anova_device.is_cooking:
            self.coordinator.pending_target_temperature = value
            self._attr_native_value = value
            self.async_write_ha_state()
            return
        try:
            await self.coordinator.anova_device.update_running_cook(
                target_temperature=value, temperature_unit="C"
            )
        except (CommandFailure, WebsocketFailure, NoActiveCookError) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_target_temperature_failed",
                translation_placeholders={"value": str(value)},
            ) from ex
        self.coordinator.pending_target_temperature = value


class AnovaTimerNumber(AnovaEntity, RestoreNumber):
    """The cook timer for the current, or next, cook.

    Anova's protocol works in seconds (coordinator.pending_cook_time_seconds,
    APCUpdateSensor.cook_time, update_running_cook's cook_time_seconds), but
    minutes are a far more usable unit for a person setting a cook timer, so
    this entity converts at its own boundary rather than exposing raw seconds.

    While idle, this is held locally (mirroring the official app) and used
    when the cook switch is turned on. While a cook is running, it reflects
    and updates the live job via update_running_cook.
    """

    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = 0
    _attr_native_max_value = 60 * 72
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: AnovaCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = NumberEntityDescription(
            key="timer", translation_key="timer"
        )
        self._attr_unique_id = f"{coordinator.device_unique_id}_timer"

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last locally-set value, if any, overriding the coordinator's seed."""
        if (
            (last_state := await self.async_get_last_state())
            and (last_number_data := await self.async_get_last_number_data())
            and last_state.state != STATE_UNKNOWN
            and last_number_data.native_value is not None
        ):
            self.coordinator.pending_cook_time_seconds = round(
                last_number_data.native_value * 60
            )
        if (
            self.coordinator.anova_device.is_cooking
            and self.coordinator.data is not None
        ):
            self._attr_native_value = self._minutes(
                self.coordinator.data.sensor.cook_time
            )
        else:
            self._attr_native_value = self._minutes(
                self.coordinator.pending_cook_time_seconds
            )
        await super().async_added_to_hass()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Reflect the live job's configured timer while cooking, else the pending value."""
        if (
            self.coordinator.anova_device.is_cooking
            and self.coordinator.data is not None
        ):
            self._attr_native_value = self._minutes(
                self.coordinator.data.sensor.cook_time
            )
        else:
            self._attr_native_value = self._minutes(
                self.coordinator.pending_cook_time_seconds
            )
        super()._handle_coordinator_update()

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the cook timer, given in minutes."""
        cook_time_seconds = round(value * 60)
        if not self.coordinator.anova_device.is_cooking:
            self.coordinator.pending_cook_time_seconds = cook_time_seconds
            self._attr_native_value = value
            self.async_write_ha_state()
            return
        try:
            await self.coordinator.anova_device.update_running_cook(
                cook_time_seconds=cook_time_seconds
            )
        except (CommandFailure, WebsocketFailure, NoActiveCookError) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_timer_failed",
                translation_placeholders={"value": str(value)},
            ) from ex
        self.coordinator.pending_cook_time_seconds = cook_time_seconds

    @staticmethod
    def _minutes(cook_time_seconds: int | None) -> float | None:
        """Convert a raw seconds value from the device/coordinator to minutes."""
        if cook_time_seconds is None:
            return None
        return cook_time_seconds / 60
