"""Support for HomematicIP Cloud climate devices."""
from __future__ import annotations

from typing import Any

from homematicip.aio.device import AsyncHeatingThermostat, AsyncHeatingThermostatCompact
from homematicip.aio.group import AsyncHeatingGroup
from homematicip.base.enums import AbsenceType
from homematicip.device import Switch
from homematicip.functionalHomes import IndoorClimateHome

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN as HMIPC_DOMAIN, HomematicipGenericEntity
from .hap import HomematicipHAP

HEATING_PROFILES = {"PROFILE_1": 0, "PROFILE_2": 1, "PROFILE_3": 2}
COOLING_PROFILES = {"PROFILE_4": 3, "PROFILE_5": 4, "PROFILE_6": 5}

ATTR_PRESET_END_TIME = "preset_end_time"
PERMANENT_END_TIME = "permanent"

HMIP_AUTOMATIC_CM = "AUTOMATIC"
HMIP_MANUAL_CM = "MANUAL"
HMIP_ECO_CM = "ECO"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HomematicIP climate from a config entry."""
    hap = hass.data[HMIPC_DOMAIN][config_entry.unique_id]
    entities = []
    for device in hap.home.groups:
        if isinstance(device, AsyncHeatingGroup):
            entities.append(HomematicipHeatingGroup(hap, device))

    if entities:
        async_add_entities(entities)


class HomematicipHeatingGroup(HomematicipGenericEntity, ClimateEntity):
    """Representation of the HomematicIP heating group.

    Heat mode is supported for all heating devices incl. their defined profiles.
    Boost is available for radiator thermostats only.
    Cool mode is only available for floor heating systems, if basically enabled in the hmip app.
    """

    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    )

    def __init__(self, hap: HomematicipHAP, device: AsyncHeatingGroup) -> None:
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
            identifiers={(HMIPC_DOMAIN, self._device.id)},
            manufacturer="eQ-3",
            model=self._device.modelType,
            name=self._device.label,
            via_device=(HMIPC_DOMAIN, self._device.homeId),
        )

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

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
        """
        Return the current hvac_action.

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
            self._device.activeProfile.name
            if self._device.activeProfile.name in self._device_profile_names
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
            presets.append(PRESET_BOOST)

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

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        if self.min_temp <= temperature <= self.max_temp:
            await self._device.set_point_temperature(temperature)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode not in self.hvac_modes:
            return

        if hvac_mode == HVACMode.AUTO:
            await self._device.set_control_mode(HMIP_AUTOMATIC_CM)
        else:
            await self._device.set_control_mode(HMIP_MANUAL_CM)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in self.preset_modes:
            return

        if self._device.boostMode and preset_mode != PRESET_BOOST:
            await self._device.set_boost(False)
        if preset_mode == PRESET_BOOST:
            await self._device.set_boost()
        if preset_mode in self._device_profile_names:
            profile_idx = self._get_profile_idx_by_name(preset_mode)
            if self._device.controlMode != HMIP_AUTOMATIC_CM:
                await self.async_set_hvac_mode(HVACMode.AUTO)
            await self._device.set_active_profile(profile_idx)

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
    def _device_profiles(self) -> list[Any]:
        """Return the relevant profiles."""
        return [
            profile
            for profile in self._device.profiles
            if profile.visible
            and profile.name != ""
            and profile.index in self._relevant_profile_group
        ]

    @property
    def _device_profile_names(self) -> list[str]:
        """Return a collection of profile names."""
        return [profile.name for profile in self._device_profiles]

    def _get_profile_idx_by_name(self, profile_name: str) -> int:
        """Return a profile index by name."""
        relevant_index = self._relevant_profile_group
        index_name = [
            profile.index
            for profile in self._device_profiles
            if profile.name == profile_name
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
        for device in self._device.devices:
            if isinstance(device, Switch):
                return True

        return False

    @property
    def _has_radiator_thermostat(self) -> bool:
        """Return, if a radiator thermostat is in the hmip heating group."""
        return bool(self._first_radiator_thermostat)

    @property
    def _first_radiator_thermostat(
        self,
    ) -> AsyncHeatingThermostat | AsyncHeatingThermostatCompact | None:
        """Return the first radiator thermostat from the hmip heating group."""
        for device in self._device.devices:
            if isinstance(
                device, (AsyncHeatingThermostat, AsyncHeatingThermostatCompact)
            ):
                return device

        return None
