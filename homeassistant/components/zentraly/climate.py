"""Climate platform for Zentraly."""

from typing import Any, override

from zentraly import ClimateCapability, ClimateOperationMode

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import ZentralyUpdateCoordinator
from .entity import ZentralyEntity, translate_action_errors
from .models import ZentralyConfigEntry, ZentralyDevice

PARALLEL_UPDATES = 1


def _create_climate_entities(
    device: ZentralyDevice,
    coordinator: ZentralyUpdateCoordinator,
) -> list[ZentralyClimate]:
    """Create climate entities supported by a Zentraly device."""

    climate_api = coordinator.climate_api

    if not any(climate_api.supports(capability) for capability in ClimateCapability):
        return []

    return [
        ZentralyClimate(
            device,
            coordinator,
        )
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZentralyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Zentraly climate entities."""

    parent_entities = _create_climate_entities(
        entry.runtime_data.device,
        entry.runtime_data.coordinator,
    )

    if parent_entities:
        async_add_entities(
            parent_entities,
        )


class ZentralyClimate(ZentralyEntity, ClimateEntity):
    """Representation of a Zentraly thermostat."""

    def __init__(
        self,
        device: ZentralyDevice,
        coordinator: ZentralyUpdateCoordinator,
    ) -> None:
        """Initialize the thermostat."""

        super().__init__(coordinator)
        self._climate_api = coordinator.climate_api
        self._configuration = self._climate_api.configuration

        self._attr_unique_id = device.device_id
        self._attr_name = None

        self._attr_native_temperature_unit = UnitOfTemperature.CELSIUS

        self._attr_min_temp = self._configuration.minimum_temperature
        self._attr_max_temp = self._configuration.maximum_temperature

        self._attr_native_current_temperature = None
        self._attr_current_humidity = None
        self._attr_native_target_temperature = None

        self._attr_hvac_mode = None
        self._attr_hvac_action = None
        self._attr_preset_mode = PRESET_NONE

        self._heat_demand: bool | None = None
        self._configure_features()
        self._apply_state_update(coordinator.data)

    @property
    @override
    def target_temperature_step(self) -> float:
        """Return the display step without changing native Celsius writes."""
        if self.hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return 1.0
        return self._configuration.temperature_step

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Translate the device state into climate attributes."""
        self._apply_state_update(self.coordinator.data)
        super()._handle_coordinator_update()

    def _apply_state_update(
        self,
        updates: dict[object, Any],
    ) -> None:
        """Handle state updates received from Zentraly reports."""

        if ClimateCapability.LOCAL_TEMPERATURE in updates:
            value = updates[ClimateCapability.LOCAL_TEMPERATURE]

            if value is None or isinstance(value, int | float):
                self._attr_native_current_temperature = (
                    None if value is None else float(value)
                )

        if ClimateCapability.TARGET_TEMPERATURE in updates:
            value = updates[ClimateCapability.TARGET_TEMPERATURE]

            if value is None or isinstance(value, int | float):
                self._attr_native_target_temperature = (
                    None if value is None else float(value)
                )

        if ClimateCapability.OPERATION_MODE in updates:
            value = updates[ClimateCapability.OPERATION_MODE]

            if value is None or isinstance(value, ClimateOperationMode):
                self._apply_operation_mode(value)

        if ClimateCapability.HEAT_DEMAND in updates:
            value = updates[ClimateCapability.HEAT_DEMAND]

            if value is None or isinstance(value, bool):
                self._heat_demand = value

        if ClimateCapability.HUMIDITY in updates:
            value = updates[ClimateCapability.HUMIDITY]

            if value is None or isinstance(value, int | float):
                self._attr_current_humidity = None if value is None else float(value)

        self._update_hvac_action()

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
            if ClimateOperationMode.OFF in modes:
                supported_features |= ClimateEntityFeature.TURN_OFF
            if ClimateOperationMode.MANUAL in modes:
                supported_features |= ClimateEntityFeature.TURN_ON
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

        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode is not None and hvac_mode not in self.hvac_modes:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_action"
            )

        step = self._configuration.temperature_step
        temperature = round(float(kwargs[ATTR_TEMPERATURE]) / step) * step

        await self.coordinator.async_wait_for_refresh()
        success = await self._climate_api.async_set_target_temperature(
            float(temperature)
        )

        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="action_failed"
            )

        self._attr_native_target_temperature = float(temperature)

        if (
            self._climate_api.supports(ClimateCapability.OPERATION_MODE)
            and self._configuration.mode_after_setpoint is not None
        ):
            self._apply_operation_mode(self._configuration.mode_after_setpoint)

        self._update_hvac_action()

        updates: dict[object, Any] = {
            ClimateCapability.TARGET_TEMPERATURE: float(temperature)
        }
        if (
            self._climate_api.supports(ClimateCapability.OPERATION_MODE)
            and self._configuration.mode_after_setpoint is not None
        ):
            updates[ClimateCapability.OPERATION_MODE] = (
                self._configuration.mode_after_setpoint
            )
        self.coordinator.async_update_partial(updates)

        if hvac_mode is not None:
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

        await self.coordinator.async_wait_for_refresh()
        success = await self._climate_api.async_set_operation_mode(operation_mode)

        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="action_failed"
            )

        self._apply_operation_mode(operation_mode)
        self._update_hvac_action()

        self.coordinator.async_update_partial(
            {ClimateCapability.OPERATION_MODE: operation_mode}
        )

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

        await self.coordinator.async_wait_for_refresh()
        success = await self._climate_api.async_set_operation_mode(operation_mode)

        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="action_failed"
            )

        self._apply_operation_mode(operation_mode)
        self._update_hvac_action()

        self.coordinator.async_update_partial(
            {ClimateCapability.OPERATION_MODE: operation_mode}
        )
