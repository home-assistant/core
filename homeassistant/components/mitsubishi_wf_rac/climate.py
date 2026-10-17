"""Climate platform for the Mitsubishi WF-RAC integration."""

import logging
from typing import Any, override

from pywfrac import Aircon, AirconCommands, OperationMode

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    FAN_AUTO,
    PRESET_AWAY,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    FAN_MODE_BY_AIRFLOW,
    FAN_MODE_TRANSLATION,
    HOME_LEAVE_TEMP_COOL,
    HOME_LEAVE_TEMP_HEAT,
    HVAC_MODE_BY_OPERATION,
    HVAC_TRANSLATION,
    NORMAL_TEMP,
    SUPPORT_FLAGS,
    SUPPORT_SWING_HORIZONTAL_MODES,
    SUPPORT_SWING_MODES,
    SUPPORTED_FAN_MODES,
    SUPPORTED_HVAC_MODES,
    SWING_3D_AUTO,
    SWING_HORIZONTAL_AUTO,
    SWING_HORIZONTAL_MODE_BY_DIRECTION,
    SWING_HORIZONTAL_MODE_TRANSLATION,
    SWING_MODE_BY_DIRECTION,
    SWING_MODE_TRANSLATION,
    SWING_VERTICAL_AUTO,
)
from .coordinator import MitsubishiWfRacConfigEntry, WfRacCoordinator
from .entity import WfRacEntity

_LOGGER = logging.getLogger(__name__)
# The coordinator serializes and spaces requests itself.
PARALLEL_UPDATES = 0

# Modes with a setpoint of their own; off and fan-only have none.
REGULATING_HVAC_MODES = (HVACMode.AUTO, HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MitsubishiWfRacConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the climate entity."""
    async_add_entities([AircoClimate(entry.runtime_data.coordinator)])


class AircoClimate(WfRacEntity, ClimateEntity):
    """Representation of a climate entity."""

    _attr_supported_features: ClimateEntityFeature = SUPPORT_FLAGS
    _attr_native_temperature_unit: str = UnitOfTemperature.CELSIUS
    _attr_hvac_modes: list[HVACMode] = SUPPORTED_HVAC_MODES
    _attr_fan_modes: list[str] = SUPPORTED_FAN_MODES
    _attr_hvac_action: HVACAction | None = None
    _attr_fan_mode: str | None = FAN_AUTO
    _attr_swing_mode: str | None = SWING_VERTICAL_AUTO
    _attr_swing_modes: list[str] | None = SUPPORT_SWING_MODES
    _attr_swing_horizontal_mode: str | None = SWING_HORIZONTAL_AUTO
    _attr_swing_horizontal_modes: list[str] | None = SUPPORT_SWING_HORIZONTAL_MODES
    # The frame truncates to half degrees; async_set_temperature rounds first.
    _attr_target_temperature_step: float = 0.5
    # Set only for units that report VacantProperty.
    _attr_preset_modes: list[str] | None = None
    _attr_preset_mode: str | None = None
    _attr_translation_key = "mitsubishi_wf_rac"
    # This entity is the device, so it carries the device name alone.
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: WfRacCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.airco_id.lower()
        capabilities = coordinator.data.Capabilities
        features = SUPPORT_FLAGS
        # Away maps to the unit's Home Leave mode.
        if capabilities.vacant_property:
            features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes = [PRESET_NONE, PRESET_AWAY]
        # Ceiling cassettes have neither a horizontal vane nor 3D auto.
        if capabilities.wind_direction_lr:
            features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE
        else:
            self._attr_swing_horizontal_mode = None
            self._attr_swing_horizontal_modes = None
        if not capabilities.entrust:
            self._attr_swing_modes = [
                mode for mode in SUPPORT_SWING_MODES if mode != SWING_3D_AUTO
            ]
        self._attr_supported_features = features
        self._update_state()

    def _union_setpoint_range(self) -> tuple[float, float]:
        """The widest range any regulating mode of this unit allows."""
        capabilities = self.coordinator.data.Capabilities
        ranges = [
            capabilities.setpoint_range(HVAC_TRANSLATION[mode])
            for mode in REGULATING_HVAC_MODES
        ]
        return (min(low for low, _ in ranges), max(high for _, high in ranges))

    def _setpoint_range_for_mode(self, hvac_mode: HVACMode) -> tuple[float, float]:
        """Return the range a setpoint is held to before it is sent.

        Off and fan-only get the union, as the value applies to the next mode.
        """
        if hvac_mode in REGULATING_HVAC_MODES:
            return self.coordinator.data.Capabilities.setpoint_range(
                HVAC_TRANSLATION[hvac_mode]
            )
        return self._union_setpoint_range()

    def _advertised_range(self) -> tuple[float, float]:
        """Return the range HA validates against.

        Widened where the away preset exists: Home Leave reports 31 or 10 °C
        as the target temperature.
        """
        min_temp, max_temp = self._union_setpoint_range()
        if self.preset_modes:
            return (
                min(min_temp, HOME_LEAVE_TEMP_HEAT),
                max(max_temp, HOME_LEAVE_TEMP_COOL),
            )
        return (min_temp, max_temp)

    @override
    @property
    def min_temp(self) -> float:
        """Return the lowest setpoint any of this unit's modes allows."""
        return self._advertised_range()[0]

    @override
    @property
    def max_temp(self) -> float:
        """Return the highest setpoint any of this unit's modes allows."""
        return self._advertised_range()[1]

    @staticmethod
    def _hvac_mode_params(hvac_mode: HVACMode) -> dict[AirconCommands, Any]:
        """Return the command params for a target hvac mode.

        Off sends no mode: the library re-encodes from fresh state after a lock
        refusal, and a stale mode would overwrite a foreign client's.
        """
        if hvac_mode == HVACMode.OFF:
            return {AirconCommands.Operation: False}
        return {
            AirconCommands.OperationMode: HVAC_TRANSLATION[hvac_mode],
            AirconCommands.Operation: True,
        }

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        set_temp = kwargs[ATTR_TEMPERATURE]

        # The service schema does not check hvac_mode against the offered modes.
        requested_hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)
        if requested_hvac_mode is not None:
            self._valid_mode_or_raise("hvac", requested_hvac_mode, self.hvac_modes)

        # Validate against the requested mode, not the one still reported.
        target_hvac_mode = (
            requested_hvac_mode if requested_hvac_mode is not None else self.hvac_mode
        )
        target_hvac_mode = (
            HVACMode.OFF if target_hvac_mode is None else target_hvac_mode
        )
        min_temp, max_temp = self._setpoint_range_for_mode(target_hvac_mode)

        if set_temp < min_temp:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="temperature_below_minimum",
                translation_placeholders={
                    "temperature": str(set_temp),
                    "min_temp": str(min_temp),
                    "hvac_mode": str(target_hvac_mode),
                },
            )

        if set_temp > max_temp:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="temperature_above_maximum",
                translation_placeholders={
                    "temperature": str(set_temp),
                    "max_temp": str(max_temp),
                    "hvac_mode": str(target_hvac_mode),
                },
            )

        # The step is not validated and the frame truncates; round to halves.
        opts: dict[AirconCommands, Any] = {
            AirconCommands.PresetTemp: round(set_temp * 2) / 2
        }

        if requested_hvac_mode is not None:
            opts.update(self._hvac_mode_params(target_hvac_mode))

        await self.coordinator.async_queue_command(opts)

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self.coordinator.async_queue_command(
            {AirconCommands.AirFlow: FAN_MODE_TRANSLATION[fan_mode]}
        )

    @override
    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.coordinator.async_queue_command({AirconCommands.Operation: True})

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self.coordinator.async_queue_command(self._hvac_mode_params(hvac_mode))

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        _swing_auto = swing_mode == SWING_3D_AUTO
        if _swing_auto:
            await self.coordinator.async_queue_command(
                {
                    AirconCommands.Entrust: _swing_auto,
                }
            )
        else:
            await self.coordinator.async_queue_command(
                {
                    AirconCommands.WindDirectionUD: SWING_MODE_TRANSLATION[swing_mode],
                    AirconCommands.Entrust: False,
                }
            )

    @override
    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set new target horizontal swing operation."""
        await self.coordinator.async_queue_command(
            {
                AirconCommands.WindDirectionLR: SWING_HORIZONTAL_MODE_TRANSLATION[
                    swing_horizontal_mode
                ],
                AirconCommands.Entrust: False,
            }
        )

    @override
    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.coordinator.async_queue_command({AirconCommands.Operation: False})

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Enter or leave the unit's Home Leave mode.

        Home Leave is entered by writing the away target of the running
        direction, so only cool and heat have one.
        """
        if preset_mode == PRESET_NONE:
            # A scene restores preset none after its own setpoint.
            if self.preset_mode != PRESET_AWAY:
                return
            await self.coordinator.async_queue_command(
                {AirconCommands.PresetTemp: NORMAL_TEMP}
            )
            return

        if self.hvac_mode == HVACMode.COOL:
            away_temp = HOME_LEAVE_TEMP_COOL
        elif self.hvac_mode == HVACMode.HEAT:
            away_temp = HOME_LEAVE_TEMP_HEAT
        else:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="preset_away_needs_cool_or_heat",
                translation_placeholders={"hvac_mode": str(self.hvac_mode)},
            )

        await self.coordinator.async_queue_command(
            {
                AirconCommands.Operation: True,
                AirconCommands.OperationMode: HVAC_TRANSLATION[self.hvac_mode],
                AirconCommands.PresetTemp: away_temp,
            }
        )

    @override
    def _update_state(self) -> None:
        """Read the coordinator data into the entity attributes.

        A raw value the library cannot name leaves its attribute unknown.
        """
        airco = self.coordinator.data

        self._attr_native_target_temperature = airco.PresetTemp
        self._attr_native_current_temperature = airco.IndoorTemp
        fan = airco.air_flow
        self._attr_fan_mode = None if fan is None else FAN_MODE_BY_AIRFLOW[fan]
        # Units without 3D auto can still set the bit; report only offered modes.
        entrusted = airco.Entrust and SWING_3D_AUTO in (self.swing_modes or ())
        vertical = airco.wind_direction_ud
        if entrusted:
            self._attr_swing_mode = SWING_3D_AUTO
        else:
            self._attr_swing_mode = (
                None if vertical is None else SWING_MODE_BY_DIRECTION[vertical]
            )
        # The horizontal vane keeps its own position while 3D auto drives both.
        if self.supported_features & ClimateEntityFeature.SWING_HORIZONTAL_MODE:
            horizontal = airco.wind_direction_lr
            self._attr_swing_horizontal_mode = (
                None
                if horizontal is None
                else SWING_HORIZONTAL_MODE_BY_DIRECTION[horizontal]
            )

        # OperationMode keeps reporting cool/heat while the unit is off.
        operation_mode = airco.operation_mode
        if airco.Operation is False:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF
        elif operation_mode is None:
            self._attr_hvac_mode = None
            self._attr_hvac_action = None
        else:
            self._attr_hvac_mode = HVAC_MODE_BY_OPERATION[operation_mode]
            self._attr_hvac_action = self._determine_hvac_action(airco, operation_mode)

        # Vacant also follows a Home Leave entered from the app or the remote.
        if self.supported_features & ClimateEntityFeature.PRESET_MODE:
            self._attr_preset_mode = PRESET_AWAY if airco.Vacant else PRESET_NONE

    @staticmethod
    def _determine_hvac_action(airco: Aircon, mode: OperationMode) -> HVACAction:
        """Determine the current HVAC action.

        CompressorRunning separates "on" from "running", so a satisfied
        setpoint reports IDLE.
        """
        if mode == OperationMode.FAN:
            return HVACAction.FAN

        if mode == OperationMode.DRY:
            return HVACAction.DRYING

        if not airco.CompressorRunning:
            return HVACAction.IDLE

        # AUTO leaves the direction to the unit.
        if mode == OperationMode.AUTO:
            return HVACAction.HEATING if airco.CoolHotJudge else HVACAction.COOLING

        if mode == OperationMode.COOL:
            return HVACAction.COOLING

        return HVACAction.HEATING
