"""Provides climate entities for Home Connect."""

import logging
from typing import Any, cast

from aiohomeconnect.model import EventKey, OptionKey, ProgramKey, SettingKey
from aiohomeconnect.model.error import HomeConnectError
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
from .coordinator import HomeConnectApplianceCoordinator, HomeConnectConfigEntry
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
    appliance_coordinator: HomeConnectApplianceCoordinator,
) -> list[HomeConnectEntity]:
    """Get a list of entities."""
    return (
        [HomeConnectAirConditioningEntity(appliance_coordinator)]
        if (programs := appliance_coordinator.data.programs)
        and any(
            program.key in PROGRAMS_HVAC_MODES_MAP
            and (
                program.constraints is None
                or program.constraints.execution
                in (Execution.SELECT_AND_START, Execution.START_ONLY)
            )
            for program in programs
        )
        else []
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Connect climate entities."""
    setup_home_connect_entry(
        hass,
        entry,
        _get_entities_for_appliance,
        async_add_entities,
    )


class HomeConnectAirConditioningEntity(HomeConnectEntity, ClimateEntity):
    """Representation of a Home Connect climate entity."""

    # Note: The base class requires this to be set even though this
    # class doesn't support any temperature related functionality.
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: HomeConnectApplianceCoordinator,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator,
            AIR_CONDITIONER_ENTITY_DESCRIPTION,
            context_override=EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
        )

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        hvac_modes = [
            hvac_mode
            for program in self.appliance.programs
            if (hvac_mode := PROGRAMS_HVAC_MODES_MAP.get(program.key))
            and (
                program.constraints is None
                or program.constraints.execution
                in (Execution.SELECT_AND_START, Execution.START_ONLY)
            )
        ]
        if SettingKey.BSH_COMMON_POWER_STATE in self.appliance.settings:
            hvac_modes.append(HVACMode.OFF)
        return hvac_modes

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes."""
        return (
            [
                PROGRAMS_PRESET_MODES_MAP[
                    ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_ACTIVE_CLEAN
                ]
            ]
            if any(
                program.key
                is ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_ACTIVE_CLEAN
                for program in self.appliance.programs
            )
            else None
        )

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        features = ClimateEntityFeature(0)
        if SettingKey.BSH_COMMON_POWER_STATE in self.appliance.settings:
            features |= ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        if self.preset_modes:
            features |= ClimateEntityFeature.PRESET_MODE
        if self.appliance.options.get(
            OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE
        ):
            features |= ClimateEntityFeature.FAN_MODE
        return features

    @callback
    def _handle_coordinator_update_fan_mode(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
        _LOGGER.debug(
            "Updated %s (fan mode), new state: %s", self.entity_id, self.fan_mode
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self.async_write_ha_state,
                EventKey.BSH_COMMON_APPLIANCE_CONNECTED,
            )
        )
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self._handle_coordinator_update_fan_mode,
                EventKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
            )
        )
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self._handle_coordinator_update,
                EventKey(SettingKey.BSH_COMMON_POWER_STATE),
            )
        )

    def update_native_value(self) -> None:
        """Set the HVAC Mode and preset mode values."""
        event = self.appliance.events.get(EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM)
        program_key = cast(ProgramKey, event.value) if event else None
        power_state = self.appliance.settings.get(SettingKey.BSH_COMMON_POWER_STATE)
        self._attr_hvac_mode = (
            HVACMode.OFF
            if power_state is not None and power_state.value != BSH_POWER_ON
            else PROGRAMS_HVAC_MODES_MAP.get(program_key)
            if program_key
            and program_key
            != ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_ACTIVE_CLEAN
            else None
        )
        self._attr_preset_mode = (
            PROGRAMS_PRESET_MODES_MAP.get(program_key)
            if program_key
            == ProgramKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_ACTIVE_CLEAN
            else None
        )

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        option_value = None
        if event := self.appliance.events.get(
            EventKey(
                OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE
            )
        ):
            option_value = event.value
        return (
            FAN_MODES_OPTIONS_INVERTED.get(cast(str, option_value))
            if option_value is not None
            else None
        )

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        if (
            (
                option_definition := self.appliance.options.get(
                    OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE
                )
            )
            and (option_constraints := option_definition.constraints)
            and option_constraints.allowed_values
        ):
            return [
                fan_mode
                for fan_mode, api_value in FAN_MODES_OPTIONS.items()
                if api_value in option_constraints.allowed_values
            ]
        if option_definition:
            # Then the constraints or the allowed values are not present
            # So we stick to the default values
            return list(FAN_MODES_OPTIONS.keys())
        return None

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
        """Switch the device off."""
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
        if hvac_mode is HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self._set_program(HVAC_MODES_PROGRAMS_MAP[hvac_mode])

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self._set_program(PRESET_MODES_PROGRAMS_MAP[preset_mode])

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await super().async_set_option_with_key(
            OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
            FAN_MODES_OPTIONS[fan_mode],
        )
        _LOGGER.debug(
            "Updated %s's speed mode option, new state: %s", self.entity_id, self.state
        )
