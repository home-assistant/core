"""Climate platform for Zentraly."""

import asyncio
from datetime import datetime
from typing import Any, override

from zentraly import ClimateCapability, ClimateOperationMode, ZentralyClimateApi

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    PRESET_AWAY,
    PRESET_NONE,
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
from homeassistant.helpers.event import async_track_time_interval

from .actions import translate_action_errors
from .const import DOMAIN, SCAN_INTERVAL
from .models import ZentralyConfigEntry, ZentralyDevice

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZentralyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Zentraly climate entities."""

    parent_entities = _create_climate_entities(
        entry.runtime_data.device,
    )

    if parent_entities:
        async_add_entities(
            parent_entities,
        )


class ZentralyClimate(ClimateEntity):
    """Representation of a Zentraly thermostat."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        device: ZentralyDevice,
        *,
        climate_api: ZentralyClimateApi | None = None,
    ) -> None:
        """Initialize the thermostat."""

        self._device = device
        self._climate_api = climate_api or ZentralyClimateApi(device)
        self._configuration = self._climate_api.configuration

        self._attr_unique_id = device.device_id
        self._attr_name = None

        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        self._attr_target_temperature_step = self._configuration.temperature_step
        self._attr_min_temp = self._configuration.minimum_temperature
        self._attr_max_temp = self._configuration.maximum_temperature

        self._attr_current_temperature = None
        self._attr_current_humidity = None
        self._attr_target_temperature = None

        self._attr_hvac_mode = None
        self._attr_hvac_action = None
        self._attr_preset_mode = PRESET_NONE

        self._heat_demand: bool | None = None

        self._configure_features()

    @override
    async def async_added_to_hass(self) -> None:
        """Register Zentraly listeners and periodic state refresh."""

        await super().async_added_to_hass()

        self.async_on_remove(self._device.add_state_listener(self.async_write_ha_state))

        self.async_on_remove(
            self._device.add_connection_state_listener(self._handle_connection_state)
        )

        self.async_on_remove(
            self._climate_api.add_state_listener(self._handle_state_update)
        )

        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._async_periodic_refresh,
                SCAN_INTERVAL,
            )
        )

        self.async_schedule_update_ha_state(force_refresh=True)

    async def _async_periodic_refresh(
        self,
        now: datetime,
    ) -> None:
        """Refresh device state periodically as a synchronization fallback."""

        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    @override
    def available(self) -> bool:
        """Return availability independently of a missing attribute value."""
        return self._device.available and self._device.connected

    def _handle_connection_state(
        self,
        connected: bool,
    ) -> None:
        """Handle Zentraly connection-state changes."""

        if not connected:
            self.async_write_ha_state()
            return

        self.async_schedule_update_ha_state(force_refresh=True)

    def _handle_state_update(
        self,
        updates: dict[ClimateCapability, Any],
    ) -> None:
        """Handle state updates received from Zentraly reports."""

        if ClimateCapability.LOCAL_TEMPERATURE in updates:
            value = updates[ClimateCapability.LOCAL_TEMPERATURE]

            if isinstance(value, int | float):
                self._attr_current_temperature = float(value)

        if ClimateCapability.TARGET_TEMPERATURE in updates:
            value = updates[ClimateCapability.TARGET_TEMPERATURE]

            if isinstance(value, int | float):
                self._attr_target_temperature = float(value)

        if ClimateCapability.OPERATION_MODE in updates:
            value = updates[ClimateCapability.OPERATION_MODE]

            if isinstance(value, ClimateOperationMode):
                self._apply_operation_mode(value)

        if ClimateCapability.HEAT_DEMAND in updates:
            value = updates[ClimateCapability.HEAT_DEMAND]

            if isinstance(value, bool):
                self._heat_demand = value

        if ClimateCapability.HUMIDITY in updates:
            value = updates[ClimateCapability.HUMIDITY]

            if isinstance(value, int | float):
                self._attr_current_humidity = float(value)

        self._update_hvac_action()

        self.async_write_ha_state()

    def _configure_features(self) -> None:
        """Configure Home Assistant features from device capabilities."""

        supported_features = ClimateEntityFeature(0)

        if self._climate_api.supports(ClimateCapability.TARGET_TEMPERATURE):
            supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

        if self._climate_api.supports(ClimateCapability.OPERATION_MODE):
            modes = self._configuration.operation_modes
            self._attr_hvac_modes = [
                hvac_mode
                for operation_mode, hvac_mode in (
                    (ClimateOperationMode.OFF, HVACMode.OFF),
                    (ClimateOperationMode.MANUAL, HVACMode.HEAT),
                    (ClimateOperationMode.AUTO, HVACMode.AUTO),
                )
                if operation_mode in modes
            ]
            if (
                ClimateOperationMode.AWAY in modes
                and ClimateOperationMode.MANUAL in modes
            ):
                supported_features |= ClimateEntityFeature.PRESET_MODE
                self._attr_preset_modes = [PRESET_NONE, PRESET_AWAY]
            else:
                self._attr_preset_modes = None

        else:
            self._attr_hvac_modes = [
                HVACMode.HEAT,
            ]

            self._attr_preset_modes = None
            self._attr_hvac_mode = HVACMode.HEAT

        self._attr_supported_features = supported_features

    async def async_update(self) -> None:
        """Update climate state from the Zentraly device."""

        if not self._device.connected:
            return

        current_temperature_task = (
            asyncio.create_task(self._climate_api.async_get_current_temperature())
            if self._climate_api.supports(ClimateCapability.LOCAL_TEMPERATURE)
            else None
        )

        target_temperature_task = (
            asyncio.create_task(self._climate_api.async_get_target_temperature())
            if self._climate_api.supports(ClimateCapability.TARGET_TEMPERATURE)
            else None
        )

        operation_mode_task = (
            asyncio.create_task(self._climate_api.async_get_operation_mode())
            if self._climate_api.supports(ClimateCapability.OPERATION_MODE)
            else None
        )

        heat_demand_task = (
            asyncio.create_task(self._climate_api.async_get_heat_demand())
            if self._climate_api.supports(ClimateCapability.HEAT_DEMAND)
            else None
        )

        humidity_task = (
            asyncio.create_task(self._climate_api.async_get_humidity())
            if self._climate_api.supports(ClimateCapability.HUMIDITY)
            else None
        )

        tasks = [
            task
            for task in (
                current_temperature_task,
                target_temperature_task,
                operation_mode_task,
                heat_demand_task,
                humidity_task,
            )
            if task is not None
        ]

        if tasks:
            try:
                await asyncio.gather(*tasks)
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

        if current_temperature_task is not None:
            current_temperature = current_temperature_task.result()

            self._attr_current_temperature = current_temperature

        if target_temperature_task is not None:
            target_temperature = target_temperature_task.result()

            self._attr_target_temperature = target_temperature

        if operation_mode_task is not None:
            operation_mode = operation_mode_task.result()

            self._apply_operation_mode(operation_mode)

        if heat_demand_task is not None:
            heat_demand = heat_demand_task.result()

            self._heat_demand = heat_demand

        if humidity_task is not None:
            humidity = humidity_task.result()

            self._attr_current_humidity = humidity

        self._update_hvac_action()

    def _apply_operation_mode(
        self,
        mode: ClimateOperationMode | None,
    ) -> None:
        """Map a Zentraly operation mode to Home Assistant state."""

        if mode is None:
            self._attr_hvac_mode = None
            self._attr_preset_mode = PRESET_NONE
            return

        if mode is ClimateOperationMode.OFF:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_preset_mode = PRESET_NONE
            return

        if mode is ClimateOperationMode.MANUAL:
            self._attr_hvac_mode = HVACMode.HEAT
            self._attr_preset_mode = PRESET_NONE
            return

        if mode is ClimateOperationMode.AUTO:
            self._attr_hvac_mode = HVACMode.AUTO
            self._attr_preset_mode = PRESET_NONE
            return

        if mode is ClimateOperationMode.AWAY:
            self._attr_hvac_mode = HVACMode.HEAT
            self._attr_preset_mode = PRESET_AWAY

    def _update_hvac_action(self) -> None:
        """Update HVAC action from mode and heat demand."""

        if self._attr_hvac_mode is HVACMode.OFF:
            self._attr_hvac_action = HVACAction.OFF
            return

        if self._heat_demand is None:
            self._attr_hvac_action = None
            return

        if self._heat_demand:
            self._attr_hvac_action = HVACAction.HEATING
            return

        self._attr_hvac_action = HVACAction.IDLE

    @override
    @translate_action_errors
    async def async_set_temperature(
        self,
        **kwargs: Any,
    ) -> None:
        """Set new target temperature."""

        temperature = kwargs[ATTR_TEMPERATURE]

        success = await self._climate_api.async_set_target_temperature(
            float(temperature)
        )

        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="action_failed"
            )

        self._attr_target_temperature = float(temperature)

        if (
            self._climate_api.supports(ClimateCapability.OPERATION_MODE)
            and self._configuration.mode_after_setpoint is not None
        ):
            self._apply_operation_mode(self._configuration.mode_after_setpoint)

        self._update_hvac_action()

        self.async_write_ha_state()

        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            # Writing a setpoint selects manual mode on the thermostat.
            await self.async_set_hvac_mode(hvac_mode)

    @override
    @translate_action_errors
    async def async_set_hvac_mode(
        self,
        hvac_mode: HVACMode,
    ) -> None:
        """Set new HVAC mode."""

        if hvac_mode is HVACMode.OFF:
            operation_mode = ClimateOperationMode.OFF

        elif hvac_mode is HVACMode.HEAT:
            operation_mode = ClimateOperationMode.MANUAL

        elif hvac_mode is HVACMode.AUTO:
            operation_mode = ClimateOperationMode.AUTO

        else:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_action"
            )

        success = await self._climate_api.async_set_operation_mode(operation_mode)

        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="action_failed"
            )

        self._apply_operation_mode(operation_mode)
        self._update_hvac_action()

        self.async_write_ha_state()

    @override
    @translate_action_errors
    async def async_set_preset_mode(
        self,
        preset_mode: str,
    ) -> None:
        """Set new preset mode."""

        if preset_mode == PRESET_AWAY:
            operation_mode = ClimateOperationMode.AWAY

        elif preset_mode == PRESET_NONE:
            operation_mode = ClimateOperationMode.MANUAL

        else:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_action"
            )

        success = await self._climate_api.async_set_operation_mode(operation_mode)

        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="action_failed"
            )

        self._apply_operation_mode(operation_mode)
        self._update_hvac_action()

        self.async_write_ha_state()

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device information."""

        return self._device.device_info


def _create_climate_entities(
    device: ZentralyDevice,
) -> list[ZentralyClimate]:
    """Create climate entities supported by a Zentraly device."""

    climate_api = ZentralyClimateApi(device)

    if not any(climate_api.supports(capability) for capability in ClimateCapability):
        return []

    return [
        ZentralyClimate(
            device,
            climate_api=climate_api,
        )
    ]
