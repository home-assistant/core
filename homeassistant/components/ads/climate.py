"""Support for ADS climate."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pyads
import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, CONF_NAME, UnitOfTemperature
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .. import ads
from . import AdsEntity

SCAN_INTERVAL = timedelta(seconds=3)
DEFAULT_NAME = "ADS Climate"

CONF_ADS_VAR_ACTUAL_TEMP = "adsvar_actual_temperature"
CONF_ADS_VAR_SET_TEMP = "adsvar_set_temperature"
CONF_ADS_VAR_MODE = "adsvar_mode"
CONF_ADS_VAR_ACTION = "adsvar_action"
CONF_ADS_VAR_PRESET = "adsvar_preset"


PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ADS_VAR_ACTUAL_TEMP): cv.string,
        vol.Optional(CONF_ADS_VAR_SET_TEMP): cv.string,
        vol.Optional(CONF_ADS_VAR_MODE): cv.string,
        vol.Optional(CONF_ADS_VAR_ACTION): cv.string,
        vol.Optional(CONF_ADS_VAR_PRESET): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the climate platform for ADS."""

    ads_hub = hass.data.get(ads.DATA_ADS)
    ads_var_actual_temp = config.get(CONF_ADS_VAR_ACTUAL_TEMP)
    ads_var_set_temp = config.get(CONF_ADS_VAR_SET_TEMP)
    ads_var_mode = config.get(CONF_ADS_VAR_MODE)
    ads_var_action = config.get(CONF_ADS_VAR_ACTION)
    ads_var_preset = config.get(CONF_ADS_VAR_PRESET)
    name = config[CONF_NAME]

    add_entities(
        [
            AdsClimate(
                ads_hub,
                ads_var_actual_temp,
                ads_var_set_temp,
                ads_var_mode,
                ads_var_action,
                ads_var_preset,
                name,
            )
        ]
    )


class AdsClimate(AdsEntity, ClimateEntity):
    """Representation of ADS climate entity."""

    PRESET_NONE = "None"
    PRESET_ECO = "Eco"
    PRESET_AWAY = "Away"
    PRESET_BOOST = "Boost"
    PRESET_COMFORT = "Comfort"
    PRESET_HOME = "Home"
    PRESET_SLEEP = "Sleep"
    PRESET_ACTIVITY = "Activity"

    PRESETS = {
        PRESET_NONE: 0,
        PRESET_ECO: 1,
        PRESET_AWAY: 2,
        PRESET_BOOST: 3,
        PRESET_COMFORT: 4,
        PRESET_HOME: 5,
        PRESET_SLEEP: 6,
        PRESET_ACTIVITY: 7,
    }

    def __init__(
        self,
        ads_hub,
        ads_var_actual_temp,
        ads_var_set_temp,
        ads_var_mode,
        ads_var_action,
        ads_var_preset,
        name,
    ):
        """Initialize AdsClimate entity."""
        super().__init__(ads_hub, name, ads_var_actual_temp)
        self._ads_var_set_temp = ads_var_set_temp
        self._ads_var_mode = ads_var_mode
        self._ads_var_action = ads_var_action
        self._ads_var_preset = ads_var_preset
        self._ads_var_actual_temp = ads_var_actual_temp
        self._hvac_mode = ads_var_mode
        self._name = name
        self._attr_target_temperature = 24.0
        self._attr_current_temperature = 24.0
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_hvac_mode = HVACMode.AUTO
        self._attr_hvac_action = HVACAction.IDLE
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        )
        self._attr_preset_mode = self.PRESET_NONE

    async def async_added_to_hass(self) -> None:
        """Register device notification."""

        if self._ads_var_actual_temp is not None:
            await self.async_initialize_device(
                self._ads_var_actual_temp, pyads.PLCTYPE_REAL
            )

        if self._ads_var_set_temp is not None:
            await self.async_initialize_device(
                self._ads_var_set_temp, pyads.PLCTYPE_REAL
            )

        if self._ads_var_mode is not None:
            await self.async_initialize_device(self._ads_var_mode, pyads.PLCTYPE_INT)

        if self._ads_var_action is not None:
            await self.async_initialize_device(self._ads_var_action, pyads.PLCTYPE_INT)

        if self._ads_var_preset:
            await self.async_initialize_device(self._ads_var_preset, pyads.PLCTYPE_INT)

        self._attr_max_temp = 35.0
        self._attr_min_temp = 7.0
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self.async_schedule_update_ha_state(True)

    @property
    def should_poll(self) -> bool:
        """Return True if the entity should be polled."""
        return True

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 7.0

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 35.0

    @property
    def name(self) -> str:
        """Return the name of the climate device."""
        return self._name

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        return self._attr_hvac_mode

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC modes."""
        return [
            HVACMode.OFF,
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.AUTO,
        ]

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running action of the HVAC unit."""
        return self._attr_hvac_action

    @property
    def hvac_actions(self) -> list[HVACAction]:
        """Return the list of available HVAC actions."""
        return [
            HVACAction.OFF,
            HVACAction.PREHEATING,
            HVACAction.HEATING,
            HVACAction.COOLING,
            HVACAction.DRYING,
            HVACAction.FAN,
            HVACAction.IDLE,
            HVACAction.DEFROSTING,
        ]

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._attr_current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature currently set to be achieved."""
        return self._attr_target_temperature

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        )

    @property
    def preset_modes(self) -> list[str]:
        """Return the list of available preset modes."""
        return list(self.PRESETS.keys())

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self._attr_preset_mode

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        preset_value = self.PRESETS.get(preset_mode, self.PRESETS[self.PRESET_NONE])
        self._ads_hub.write_by_name(
            self._ads_var_preset, preset_value, pyads.PLCTYPE_INT
        )
        self._attr_preset_mode = preset_mode
        self.async_schedule_update_ha_state(True)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""

        mode = {
            HVACMode.OFF: 0,
            HVACMode.HEAT: 1,
            HVACMode.COOL: 2,
            HVACMode.AUTO: 4,
        }.get(hvac_mode, 0)
        self._ads_hub.write_by_name(self._ads_var_mode, mode, pyads.PLCTYPE_INT)
        self._hvac_mode = hvac_mode
        self.async_schedule_update_ha_state(True)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            new_temp = kwargs[ATTR_TEMPERATURE]
            self._attr_target_temperature = new_temp
            self._ads_hub.write_by_name(
                self._ads_var_set_temp, new_temp, pyads.PLCTYPE_REAL
            )
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Retrieve the latest state from the ADS device."""
        self._attr_current_temperature = self._ads_hub.read_by_name(
            self._ads_var_actual_temp, pyads.PLCTYPE_REAL
        )

        self._attr_target_temperature = self._ads_hub.read_by_name(
            self._ads_var_set_temp, pyads.PLCTYPE_REAL
        )

        mode = self._ads_hub.read_by_name(self._ads_var_mode, pyads.PLCTYPE_INT)
        self._attr_hvac_mode = {
            0: HVACMode.OFF,
            1: HVACMode.HEAT,
            2: HVACMode.COOL,
            4: HVACMode.AUTO,
        }.get(mode, HVACMode.OFF)

        action = self._ads_hub.read_by_name(self._ads_var_action, pyads.PLCTYPE_INT)
        self._attr_hvac_action = {
            0: HVACAction.OFF,
            1: HVACAction.PREHEATING,
            2: HVACAction.HEATING,
            3: HVACAction.COOLING,
            4: HVACAction.DRYING,
            5: HVACAction.FAN,
            6: HVACAction.IDLE,
            7: HVACAction.DEFROSTING,
        }.get(action, HVACAction.OFF)

        preset_value = self._ads_hub.read_by_name(
            self._ads_var_preset, pyads.PLCTYPE_INT
        )
        self._attr_preset_mode = {
            0: self.PRESET_NONE,
            1: self.PRESET_ECO,
            2: self.PRESET_AWAY,
            3: self.PRESET_BOOST,
            4: self.PRESET_COMFORT,
            5: self.PRESET_HOME,
            6: self.PRESET_SLEEP,
            7: self.PRESET_ACTIVITY,
        }.get(preset_value, self.PRESET_NONE)

        self.async_write_ha_state()
