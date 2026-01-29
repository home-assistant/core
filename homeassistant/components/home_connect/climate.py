"""Provides climate entities for Home Connect."""

import contextlib
import logging
from typing import Any, cast

from aiohomeconnect.model import EventKey, OptionKey, ProgramKey, SettingKey
from aiohomeconnect.model.error import ActiveProgramNotSetError, HomeConnectError
from aiohomeconnect.model.program import Execution

from homeassistant.components.climate import (
    FAN_AUTO,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import setup_home_connect_entry
from .const import BSH_POWER_ON, BSH_POWER_STANDBY, DOMAIN
from .coordinator import (
    HomeConnectApplianceData,
    HomeConnectConfigEntry,
    HomeConnectCoordinator,
)
from .entity import HomeConnectEntity
from .utils import get_dict_from_home_connect_error

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

HVAC_MODES_PROGRAMS_MAP = {
    HVACMode.AUTO: ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_AUTO,
    HVACMode.COOL: ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_COOL,
    HVACMode.DRY: ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_DRY,
    HVACMode.FAN_ONLY: ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN,
    HVACMode.HEAT: ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_HEAT,
}

PROGRAMS_HVAC_MODES_MAP = {v: k for k, v in HVAC_MODES_PROGRAMS_MAP.items()}

PRESET_MODES_PROGRAMS_MAP = {
    "active_clean": ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_ACTIVE_CLEAN,
}
PROGRAMS_PRESET_MODES_MAP = {v: k for k, v in PRESET_MODES_PROGRAMS_MAP.items()}

FAN_MODES_OPTIONS = {
    FAN_AUTO: "HeatingVentilationAirConditioning.AirConditioner.EnumType.FanSpeedMode.Automatic",
    "manual": "HeatingVentilationAirConditioning.AirConditioner.EnumType.FanSpeedMode.Manual",
}

FAN_MODES_OPTIONS_INVERTED = {v: k for k, v in FAN_MODES_OPTIONS.items()}


AIR_CONDITIONER_ENTITY_DESCRIPTION = ClimateEntityDescription(
    key="air_conditioner",
    translation_key="air_conditioner",
    name=None,
)


def _get_entities_for_appliance(
    entry: HomeConnectConfigEntry,
    appliance: HomeConnectApplianceData,
) -> list[HomeConnectEntity]:
    """Get a list of entities."""
    return (
        [HomeConnectAirConditioningEntity(entry.runtime_data, appliance)]
        if appliance.programs
        and any(
            program.key in PROGRAMS_HVAC_MODES_MAP for program in appliance.programs
        )
        else []
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Connect select entities."""
    setup_home_connect_entry(
        entry,
        _get_entities_for_appliance,
        async_add_entities,
    )


class HomeConnectAirConditioningEntity(HomeConnectEntity, ClimateEntity):
    """Representation of a Home Connect climate entity."""

    # Air Conditioner does not report / support temperature yet
    # Whenever it does, this should be updated
    # but by the moment this is required to make it work
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
    ) -> None:
        """Initialize the entity."""
        self._attr_fan_modes = list(FAN_MODES_OPTIONS.keys())
        self._original_option_keys = set(FAN_MODES_OPTIONS_INVERTED)
        super().__init__(
            coordinator,
            appliance,
            AIR_CONDITIONER_ENTITY_DESCRIPTION,
            context_override=(
                appliance.info.ha_id,
                EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
            ),
        )
        self._attr_supported_features |= (
            ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        )
        self.update_fan_mode()
        self.set_hvac_modes_and_preset()

    def set_hvac_modes_and_preset(self) -> None:
        """Set the HVAC modes and preset modes for the entity."""
        self._attr_hvac_modes = [
            hvac_mode
            for program in self.appliance.programs
            if (hvac_mode := PROGRAMS_HVAC_MODES_MAP.get(program.key))
            and (
                program.constraints is None
                or program.constraints.execution
                in (Execution.SELECT_AND_START, Execution.START_ONLY)
            )
        ]

        self._attr_preset_modes = (
            [
                PROGRAMS_PRESET_MODES_MAP[
                    ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_ACTIVE_CLEAN
                ]
            ]
            if any(
                program.key
                == ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_ACTIVE_CLEAN
                for program in self.appliance.programs
            )
            else []
        )
        if self._attr_preset_modes:
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
        else:
            self._attr_supported_features &= ~ClimateEntityFeature.PRESET_MODE

    @callback
    def _handle_coordinator_update_fan_mode(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_fan_mode()
        self.async_write_ha_state()
        _LOGGER.debug(
            "Updated %s (fan mode), new state: %s", self.entity_id, self.fan_mode
        )

    @callback
    def refresh_options(self) -> None:
        """Refresh the options for the entity."""
        self.set_hvac_modes_and_preset()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self.refresh_options,
                (self.appliance.info.ha_id, EventKey.BSH_COMMON_APPLIANCE_CONNECTED),
            )
        )
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self._handle_coordinator_update_fan_mode,
                (
                    self.appliance.info.ha_id,
                    EventKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
                ),
            )
        )

    def update_native_value(self) -> None:
        """Set the  HVAC Mode and preset mode values."""
        event = self.appliance.events.get(EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM)
        program_key = cast(ProgramKey, event.value) if event else None
        self._attr_hvac_mode = (
            PROGRAMS_HVAC_MODES_MAP.get(program_key) if program_key else None
        )
        self._attr_preset_mode = (
            PROGRAMS_PRESET_MODES_MAP.get(program_key)
            if program_key
            == ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_ACTIVE_CLEAN
            else None
        )

    def update_fan_mode(self) -> None:
        """Set the fan mode value."""
        option_value = None
        if event := self.appliance.events.get(
            EventKey(
                OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE
            )
        ):
            option_value = event.value
        self._attr_fan_mode = (
            FAN_MODES_OPTIONS_INVERTED.get(cast(str, option_value), None)
            if option_value is not None
            else None
        )
        if (
            (
                option_definition := self.appliance.options.get(
                    OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE
                )
            )
            and (option_constraints := option_definition.constraints)
            and option_constraints.allowed_values
            and self._original_option_keys != set(option_constraints.allowed_values)
        ):
            self._original_option_keys = {
                value
                for value in option_constraints.allowed_values
                if value is not None
            }
            self._attr_fan_modes = [
                FAN_MODES_OPTIONS_INVERTED[option]
                for option in self._original_option_keys
                if option is not None and option in FAN_MODES_OPTIONS_INVERTED
            ]
        match (
            self._attr_supported_features & ClimateEntityFeature.FAN_MODE,
            option_definition is not None,
        ):
            case (0, True):
                self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
                self.__dict__.pop("supported_features", None)
            case (ClimateEntityFeature.FAN_MODE, False):
                self._attr_supported_features &= ~ClimateEntityFeature.FAN_MODE
                self.__dict__.pop("supported_features", None)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the device on."""
        try:
            await self.coordinator.client.set_setting(
                self.appliance.info.ha_id,
                setting_key=SettingKey.BSH_COMMON_POWER_STATE,
                value=BSH_POWER_ON,
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="power_on",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    "appliance_name": self.appliance.info.name,
                    "value": BSH_POWER_ON,
                },
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the device off.

        We don't set `hvac_mode` to `HVACMode.OFF` because the device can still change
        the hvac_mode although the appliance is in standby mode.
        """
        try:
            await self.coordinator.client.set_setting(
                self.appliance.info.ha_id,
                setting_key=SettingKey.BSH_COMMON_POWER_STATE,
                value=BSH_POWER_STANDBY,
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="power_off",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    "appliance_name": self.appliance.info.name,
                    "value": BSH_POWER_STANDBY,
                },
            ) from err

    async def _set_program(self, program_key: ProgramKey) -> None:
        try:
            await self.coordinator.client.start_program(
                self.appliance.info.ha_id, program_key=program_key
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="start_program",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    "program": program_key.value,
                },
            ) from err
        _LOGGER.debug("Updated %s, new state: %s", self.entity_id, self.state)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self._set_program(HVAC_MODES_PROGRAMS_MAP[hvac_mode])

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self._set_program(PRESET_MODES_PROGRAMS_MAP[preset_mode])

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        value = FAN_MODES_OPTIONS[fan_mode]
        try:
            # We try to set the active program option first,
            # if it fails we try to set the selected program option
            with contextlib.suppress(ActiveProgramNotSetError):
                await self.coordinator.client.set_active_program_option(
                    self.appliance.info.ha_id,
                    option_key=OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
                    value=value,
                )
                _LOGGER.debug(
                    "Updated %s for the active program, new state: %s",
                    self.entity_id,
                    self.state,
                )
                return

            await self.coordinator.client.set_selected_program_option(
                self.appliance.info.ha_id,
                option_key=OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
                value=value,
            )
            _LOGGER.debug(
                "Updated %s for the selected program, new state: %s",
                self.entity_id,
                self.state,
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_option",
                translation_placeholders=get_dict_from_home_connect_error(err),
            ) from err
