"""Support for HomematicIP Cloud climate devices."""
import logging
from typing import Any, Dict, List, Optional, Union

from homematicip.aio.device import AsyncHeatingThermostat, AsyncHeatingThermostatCompact
from homematicip.aio.group import AsyncHeatingGroup
from homematicip.base.enums import AbsenceType
from homematicip.device import Switch
from homematicip.functionalHomes import IndoorClimateHome

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.helpers.typing import HomeAssistantType

from . import DOMAIN as HMIPC_DOMAIN, HomematicipGenericDevice
from .hap import HomematicipHAP

HEATING_PROFILES = {"PROFILE_1": 0, "PROFILE_2": 1, "PROFILE_3": 2}
COOLING_PROFILES = {"PROFILE_4": 3, "PROFILE_5": 4, "PROFILE_6": 5}

_LOGGER = logging.getLogger(__name__)

ATTR_PRESET_END_TIME = "preset_end_time"
PERMANENT_END_TIME = "permanent"

HMIP_AUTOMATIC_CM = "AUTOMATIC"
HMIP_MANUAL_CM = "MANUAL"
HMIP_ECO_CM = "ECO"


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the HomematicIP climate from a config entry."""
    hap = hass.data[HMIPC_DOMAIN][config_entry.unique_id]
    entities = []
    for device in hap.home.groups:
        if isinstance(device, AsyncHeatingGroup):
            entities.append(HomematicipHeatingGroup(hap, device))

    if entities:
        async_add_entities(entities)


class HomematicipHeatingGroup(HomematicipGenericDevice, ClimateDevice):
    """Representation of a HomematicIP heating group.

    Heat mode is supported for all heating devices incl. their defined profiles.
    Boost is available for radiator thermostats only.
    Cool mode is only available for floor heating systems, if basically enabled in the hmip app.
    """

    def __init__(self, hap: HomematicipHAP, device: AsyncHeatingGroup) -> None:
        """Initialize heating group."""
        device.modelType = "HmIP-Heating-Group"
        super().__init__(hap, device)
        self._simple_heating = None
        if device.actualTemperature is None:
            self._simple_heating = self._first_radiator_thermostat

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device specific attributes."""
        return {
            "identifiers": {(HMIPC_DOMAIN, self._device.id)},
            "name": self._device.label,
            "manufacturer": "eQ-3",
            "model": self._device.modelType,
            "via_device": (HMIPC_DOMAIN, self._device.homeId),
        }

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_PRESET_MODE | SUPPORT_TARGET_TEMPERATURE

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
    def hvac_mode(self) -> str:
        """Return hvac operation ie."""
        if self._disabled_by_cooling_mode and not self._has_switch:
            return HVAC_MODE_OFF
        if self._device.boostMode:
            return HVAC_MODE_HEAT
        if self._device.controlMode == HMIP_MANUAL_CM:
            return HVAC_MODE_HEAT if self._heat_mode_enabled else HVAC_MODE_COOL

        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        if self._disabled_by_cooling_mode and not self._has_switch:
            return [HVAC_MODE_OFF]

        return (
            [HVAC_MODE_AUTO, HVAC_MODE_HEAT]
            if self._heat_mode_enabled
            else [HVAC_MODE_AUTO, HVAC_MODE_COOL]
        )

    @property
    def hvac_action(self) -> Optional[str]:
        """
        Return the current hvac_action.

        This is only relevant for radiator thermostats.
        """
        if (
            self._device.floorHeatingMode == "RADIATOR"
            and self._has_radiator_thermostat
            and self._heat_mode_enabled
        ):
            return (
                CURRENT_HVAC_HEAT if self._device.valvePosition else CURRENT_HVAC_IDLE
            )

        return None

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode."""
        if self._device.boostMode:
            return PRESET_BOOST
        if self.hvac_mode in (HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_OFF):
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
    def preset_modes(self) -> List[str]:
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
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        if self.min_temp <= temperature <= self.max_temp:
            await self._device.set_point_temperature(temperature)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode not in self.hvac_modes:
            return

        if hvac_mode == HVAC_MODE_AUTO:
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
                await self.async_set_hvac_mode(HVAC_MODE_AUTO)
            await self._device.set_active_profile(profile_idx)

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes of the access point."""
        state_attr = super().device_state_attributes

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
    def _device_profiles(self) -> List[str]:
        """Return the relevant profiles."""
        return [
            profile
            for profile in self._device.profiles
            if profile.visible
            and profile.name != ""
            and profile.index in self._relevant_profile_group
        ]

    @property
    def _device_profile_names(self) -> List[str]:
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
    def _relevant_profile_group(self) -> List[str]:
        """Return the relevant profile groups."""
        if self._disabled_by_cooling_mode:
            return []

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
    ) -> Optional[Union[AsyncHeatingThermostat, AsyncHeatingThermostatCompact]]:
        """Return the first radiator thermostat from the hmip heating group."""
        for device in self._device.devices:
            if isinstance(
                device, (AsyncHeatingThermostat, AsyncHeatingThermostatCompact)
            ):
                return device

        return None
