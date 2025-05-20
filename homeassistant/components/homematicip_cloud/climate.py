"""Support for HomematicIP Cloud climate devices."""

from __future__ import annotations

from typing import Any

from homematicip.base.enums import AbsenceType
from homematicip.device import (
    HeatingThermostat,
    HeatingThermostatCompact,
    HeatingThermostatEvo,
    Switch,
)
from homematicip.functionalHomes import IndoorClimateHome
from homematicip.group import HeatingCoolingProfile, HeatingGroup

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import HomematicipGenericEntity
from .hap import HomematicIPConfigEntry, HomematicipHAP

HEATING_PROFILES = {"PROFILE_1": 0, "PROFILE_2": 1, "PROFILE_3": 2}
COOLING_PROFILES = {"PROFILE_4": 3, "PROFILE_5": 4, "PROFILE_6": 5}
NICE_PROFILE_NAMES = {
    "PROFILE_1": "Default",
    "PROFILE_2": "Alternative 1",
    "PROFILE_3": "Alternative 2",
    "PROFILE_4": "Cooling 1",
    "PROFILE_5": "Cooling 2",
    "PROFILE_6": "Cooling 3",
}

ATTR_PRESET_END_TIME = "preset_end_time"
PERMANENT_END_TIME = "permanent"

HMIP_AUTOMATIC_CM = "AUTOMATIC"
HMIP_MANUAL_CM = "MANUAL"
HMIP_ECO_CM = "ECO"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomematicIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP climate from a config entry."""
    hap = config_entry.runtime_data

    async_add_entities(
        HomematicipHeatingGroup(hap, device)
        for device in hap.home.groups
        if isinstance(device, HeatingGroup)
    )


class HomematicipHeatingGroup(HomematicipGenericEntity, ClimateEntity):
    """Representation of the HomematicIP heating group.

    Heat mode is supported for all heating devices incl. their defined profiles.
    Boost is available for radiator thermostats only.
    Cool mode is only available for floor heating systems, if basically enabled in the hmip app.
    """

    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, hap: HomematicipHAP, device: HeatingGroup) -> None:
        """Initialize heating group."""
        device.modelType = "HmIP-Heating-Group"
        super().__init__(hap, device)
        self._simple_heating = None
        if device.actualTemperature is None:
            self._simple_heating = self._first_radiator_thermostat

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            manufacturer="eQ-3",
            model=self._device.modelType,
            name=self._device.label,
            via_device=(DOMAIN, self._device.homeId),
        )

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self._device.setPointTemperature

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        if self._simple_heating:
            return self._simple_heating.valveActualTemperature
        return self._device.actualTemperature

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return self._device.humidity

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie."""
        if self._disabled_by_cooling_mode and not self._has_switch:
            return HVACMode.OFF
        if self._device.boostMode:
            return HVACMode.HEAT
        if self._device.controlMode == HMIP_MANUAL_CM:
            return HVACMode.HEAT if self._heat_mode_enabled else HVACMode.COOL

        return HVACMode.AUTO

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        if self._disabled_by_cooling_mode and not self._has_switch:
            return [HVACMode.OFF]

        if self._heat_mode_enabled:
            return [HVACMode.AUTO, HVACMode.HEAT]
        return [HVACMode.AUTO, HVACMode.COOL]

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current hvac_action.

        This is only relevant for radiator thermostats.
        """
        if (
            self._device.floorHeatingMode == "RADIATOR"
            and self._has_radiator_thermostat
            and self._heat_mode_enabled
        ):
            return HVACAction.HEATING if self._device.valvePosition else HVACAction.IDLE

        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if self._device.boostMode:
            return PRESET_BOOST
        if self.hvac_mode in (HVACMode.COOL, HVACMode.HEAT, HVACMode.OFF):
            return PRESET_NONE
        if self._device.controlMode == HMIP_ECO_CM:
            if self._indoor_climate.absenceType == AbsenceType.VACATION:
                return PRESET_AWAY
            if self._indoor_climate.absenceType in [
                AbsenceType.PARTY,
                AbsenceType.PERIOD,
                AbsenceType.PERMANENT,
            ]:
                return PRESET_ECO

        return (
            self._get_qualified_profile_name(self._device.activeProfile)
            if self._get_qualified_profile_name(self._device.activeProfile)
            in self._device_profile_names
            else None
        )

    @property
    def preset_modes(self) -> list[str]:
        """Return a list of available preset modes incl. hmip profiles."""
        # Boost is only available if a radiator thermostat is in the room,
        # and heat mode is enabled.
        profile_names = self._device_profile_names

        presets = []
        if (
            self._heat_mode_enabled and self._has_radiator_thermostat
        ) or self._has_switch:
            if not profile_names:
                presets.append(PRESET_NONE)
            presets.extend([PRESET_BOOST, PRESET_ECO])

        presets.extend(profile_names)

        return presets

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._device.minTemperature

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._device.maxTemperature

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        if self.min_temp <= temperature <= self.max_temp:
            await self._device.set_point_temperature_async(temperature)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode not in self.hvac_modes:
            return

        if hvac_mode == HVACMode.AUTO:
            await self._device.set_control_mode_async(HMIP_AUTOMATIC_CM)
        else:
            await self._device.set_control_mode_async(HMIP_MANUAL_CM)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self._device.boostMode and preset_mode != PRESET_BOOST:
            await self._device.set_boost_async(False)
        if preset_mode == PRESET_BOOST:
            await self._device.set_boost_async()
        if preset_mode == PRESET_ECO:
            await self._device.set_control_mode_async(HMIP_ECO_CM)
        if preset_mode in self._device_profile_names:
            profile_idx = self._get_profile_idx_by_name(preset_mode)
            if self._device.controlMode != HMIP_AUTOMATIC_CM:
                await self.async_set_hvac_mode(HVACMode.AUTO)
            await self._device.set_active_profile_async(profile_idx)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the access point."""
        state_attr = super().extra_state_attributes

        if self._device.controlMode == HMIP_ECO_CM:
            if self._indoor_climate.absenceType in [
                AbsenceType.PARTY,
                AbsenceType.PERIOD,
                AbsenceType.VACATION,
            ]:
                state_attr[ATTR_PRESET_END_TIME] = self._indoor_climate.absenceEndTime
            elif self._indoor_climate.absenceType == AbsenceType.PERMANENT:
                state_attr[ATTR_PRESET_END_TIME] = PERMANENT_END_TIME

        return state_attr

    @property
    def _indoor_climate(self) -> IndoorClimateHome:
        """Return the hmip indoor climate functional home of this group."""
        return self._home.get_functionalHome(IndoorClimateHome)

    @property
    def _device_profiles(self) -> list[HeatingCoolingProfile]:
        """Return the relevant profiles."""
        return [
            profile
            for profile in self._device.profiles
            if profile.visible and profile.index in self._relevant_profile_group
        ]

    @property
    def _device_profile_names(self) -> list[str]:
        """Return a collection of profile names."""
        return [
            self._get_qualified_profile_name(profile)
            for profile in self._device_profiles
        ]

    def _get_qualified_profile_name(self, profile: HeatingCoolingProfile) -> str:
        """Get a name for the given profile. If exists, this is the name of the profile."""
        if profile.name != "":
            return profile.name
        if profile.index in NICE_PROFILE_NAMES:
            return NICE_PROFILE_NAMES[profile.index]

        return profile.index

    def _get_profile_idx_by_name(self, profile_name: str) -> int:
        """Return a profile index by name."""
        relevant_index = self._relevant_profile_group
        index_name = [
            profile.index
            for profile in self._device_profiles
            if self._get_qualified_profile_name(profile) == profile_name
        ]

        return relevant_index[index_name[0]]

    @property
    def _heat_mode_enabled(self) -> bool:
        """Return, if heating mode is enabled."""
        return not self._device.cooling

    @property
    def _disabled_by_cooling_mode(self) -> bool:
        """Return, if group is disabled by the cooling mode."""
        return self._device.cooling and (
            self._device.coolingIgnored or not self._device.coolingAllowed
        )

    @property
    def _relevant_profile_group(self) -> dict[str, int]:
        """Return the relevant profile groups."""
        if self._disabled_by_cooling_mode:
            return {}

        return HEATING_PROFILES if self._heat_mode_enabled else COOLING_PROFILES

    @property
    def _has_switch(self) -> bool:
        """Return, if a switch is in the hmip heating group."""
        return any(isinstance(device, Switch) for device in self._device.devices)

    @property
    def _has_radiator_thermostat(self) -> bool:
        """Return, if a radiator thermostat is in the hmip heating group."""
        return bool(self._first_radiator_thermostat)

    @property
    def _first_radiator_thermostat(
        self,
    ) -> HeatingThermostat | HeatingThermostatCompact | HeatingThermostatEvo | None:
        """Return the first radiator thermostat from the hmip heating group."""
        for device in self._device.devices:
            if isinstance(
                device,
                (
                    HeatingThermostat,
                    HeatingThermostatCompact,
                    HeatingThermostatEvo,
                ),
            ):
                return device

        return None
