"""Climate platform for the Ouman EH-800 integration."""

from dataclasses import dataclass
from typing import Any

from ouman_eh_800_api import (
    EnumControlOumanEndpoint,
    IntControlOumanEndpoint,
    L1BaseEndpoints,
    L1RoomSensor,
    L2BaseEndpoints,
    L2RoomSensor,
    NumberOumanEndpoint,
    OperationMode,
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import OumanDevice
from .coordinator import OumanEh800ConfigEntry, OumanEh800Coordinator
from .entity import OumanEh800Entity, OumanEh800EntityDescription

PARALLEL_UPDATES = 1

# Operation modes that map to HVACMode.HEAT and use the climate's room
# temperature setpoint. The remaining modes (NORMAL_TEMPERATURE,
# MANUAL_VALVE_CONTROL, SHUTDOWN) ignore the setpoint and are reported as
# HVACMode.OFF.
_HEAT_OPERATION_MODES: tuple[OperationMode, ...] = (
    OperationMode.AUTOMATIC,
    OperationMode.TEMPERATURE_DROP,
    OperationMode.BIG_TEMPERATURE_DROP,
)
_PRESET_TO_OPERATION_MODE: dict[str, OperationMode] = {
    mode.name.lower(): mode for mode in _HEAT_OPERATION_MODES
}
# Operation mode written when the user switches to HVACMode.HEAT or
# turns the entity on without picking a specific preset first.
_DEFAULT_HEAT_OPERATION_MODE = OperationMode.AUTOMATIC


@dataclass(frozen=True, kw_only=True)
class OumanEh800ClimateEntityDescription(
    OumanEh800EntityDescription, ClimateEntityDescription
):
    """Climate description identifying the endpoints that back one heating circuit."""

    operation_mode_endpoint: EnumControlOumanEndpoint
    current_temperature_endpoint: NumberOumanEndpoint
    target_temperature_endpoint: IntControlOumanEndpoint
    valve_position_endpoint: NumberOumanEndpoint


CLIMATE_DESCRIPTIONS: tuple[OumanEh800ClimateEntityDescription, ...] = (
    OumanEh800ClimateEntityDescription(
        device=OumanDevice.L1,
        key="climate",
        translation_key="heating_circuit",
        operation_mode_endpoint=L1BaseEndpoints.OPERATION_MODE,
        current_temperature_endpoint=L1RoomSensor.ROOM_TEMPERATURE,
        target_temperature_endpoint=L1RoomSensor.ROOM_TEMPERATURE_SETPOINT_USER,
        valve_position_endpoint=L1BaseEndpoints.VALVE_POSITION,
    ),
    OumanEh800ClimateEntityDescription(
        device=OumanDevice.L2,
        key="climate",
        translation_key="heating_circuit",
        operation_mode_endpoint=L2BaseEndpoints.OPERATION_MODE,
        current_temperature_endpoint=L2RoomSensor.ROOM_TEMPERATURE,
        target_temperature_endpoint=L2RoomSensor.ROOM_TEMPERATURE_SETPOINT_USER,
        valve_position_endpoint=L2BaseEndpoints.VALVE_POSITION,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OumanEh800ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ouman EH-800 climate entities based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        OumanEh800ClimateEntity(coordinator, description)
        for description in CLIMATE_DESCRIPTIONS
        if description.target_temperature_endpoint in coordinator.data
    )


class OumanEh800ClimateEntity(OumanEh800Entity, ClimateEntity):
    """Ouman EH-800 per-circuit room-temperature climate entity."""

    entity_description: OumanEh800ClimateEntityDescription

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = list(_PRESET_TO_OPERATION_MODE)
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        coordinator: OumanEh800Coordinator,
        description: OumanEh800ClimateEntityDescription,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(
            coordinator, description.target_temperature_endpoint, description
        )
        target_endpoint = description.target_temperature_endpoint
        self._attr_min_temp = float(target_endpoint.min_val)
        self._attr_max_temp = float(target_endpoint.max_val)

    @property
    def _operation_mode(self) -> OperationMode:
        value = self.coordinator.data[self.entity_description.operation_mode_endpoint]
        assert isinstance(value, OperationMode)
        return value

    @property
    def hvac_mode(self) -> HVACMode:
        """Return HEAT only when the climate setpoint is controlling the circuit."""
        if self._operation_mode in _HEAT_OPERATION_MODES:
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        """Return HEATING when the mixing valve is open, IDLE when closed, OFF otherwise."""
        if self.hvac_mode is HVACMode.OFF:
            return HVACAction.OFF
        valve_position = self.coordinator.data[
            self.entity_description.valve_position_endpoint
        ]
        assert isinstance(valve_position, float)
        return HVACAction.HEATING if valve_position > 0 else HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        """Return the current heating sub-mode, or None when shut down."""
        mode = self._operation_mode
        return mode.name.lower() if mode in _HEAT_OPERATION_MODES else None

    @property
    def current_temperature(self) -> float:
        """Return the current room temperature."""
        value = self.coordinator.data[
            self.entity_description.current_temperature_endpoint
        ]
        assert isinstance(value, float)
        return value

    @property
    def target_temperature(self) -> float:
        """Return the user-set room temperature setpoint."""
        value = self.coordinator.data[
            self.entity_description.target_temperature_endpoint
        ]
        assert isinstance(value, float)
        return value

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new room temperature setpoint and optionally the HVAC mode."""
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_set_hvac_mode(hvac_mode)
        await self.coordinator.async_set_endpoint_value(
            self.entity_description.target_temperature_endpoint,
            int(kwargs[ATTR_TEMPERATURE]),
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Switch between heating (default sub-mode) and shutdown."""
        new_mode = (
            OperationMode.SHUTDOWN
            if hvac_mode is HVACMode.OFF
            else _DEFAULT_HEAT_OPERATION_MODE
        )
        await self.coordinator.async_set_endpoint_value(
            self.entity_description.operation_mode_endpoint, new_mode
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Switch the heating sub-mode."""
        await self.coordinator.async_set_endpoint_value(
            self.entity_description.operation_mode_endpoint,
            _PRESET_TO_OPERATION_MODE[preset_mode],
        )
