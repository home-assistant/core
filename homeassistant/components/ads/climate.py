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


PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ADS_VAR_ACTUAL_TEMP): cv.string,
        vol.Optional(CONF_ADS_VAR_SET_TEMP): cv.string,
        vol.Optional(CONF_ADS_VAR_MODE): cv.string,
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
    name = config[CONF_NAME]

    add_entities(
        [
            AdsClimate(
                ads_hub,
                ads_var_actual_temp,
                ads_var_set_temp,
                ads_var_mode,
                name,
            )
        ]
    )


class AdsClimate(AdsEntity, ClimateEntity):
    """Representation of ADS climate entity."""

    def __init__(
        self,
        ads_hub,
        ads_var_actual_temp,
        ads_var_set_temp,
        ads_var_mode,
        name,
    ):
        """Initialize AdsClimate entity."""
        super().__init__(ads_hub, name, ads_var_actual_temp)
        self._ads_var_set_temp = ads_var_set_temp
        self._ads_var_mode = ads_var_mode
        self._ads_var_actual_temp = ads_var_actual_temp
        self._hvac_mode = ads_var_mode
        self._name = name
        self._attr_target_temperature = 30.0
        self._attr_current_temperature = 24.0
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_hvac_action = HVACAction.IDLE
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

    async def async_added_to_hass(self) -> None:
        """Register device notification."""

        if self._ads_var_actual_temp is not None:
            await self.async_initialize_device(
                self._ads_var_actual_temp, pyads.PLCTYPE_LREAL
            )

        if self._ads_var_set_temp is not None:
            await self.async_initialize_device(
                self._ads_var_set_temp, pyads.PLCTYPE_LREAL
            )

        if self._ads_var_mode is not None:
            await self.async_initialize_device(self._ads_var_mode, pyads.PLCTYPE_INT)

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
        return 7.0  # or get from configuration

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 35.0  # or get from configuration

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
        return [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running action of the HVAC unit."""
        return self._attr_hvac_action

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
        return ClimateEntityFeature.TARGET_TEMPERATURE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""

        mode = {
            HVACMode.HEAT: 1,
            HVACMode.COOL: 2,
            HVACMode.OFF: 0,
        }.get(hvac_mode, 0)
        self._ads_hub.write_by_name(self._ads_var_mode, mode, pyads.PLCTYPE_INT)
        self._hvac_mode = hvac_mode
        self.async_schedule_update_ha_state(True)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            new_temp = kwargs[ATTR_TEMPERATURE]
            # Ensure that the temperature is written to the ADS system
            self._attr_target_temperature = new_temp
            self._ads_hub.write_by_name(
                self._ads_var_set_temp,
                new_temp,
                pyads.PLCTYPE_LREAL,
            )
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Retrieve the latest state from the ADS device."""
        # Read the actual temperature value from the ADS device

        self._attr_current_temperature = self._ads_hub.read_by_name(
            self._ads_var_actual_temp, pyads.PLCTYPE_LREAL
        )

        self._attr_target_temperature = self._ads_hub.read_by_name(
            self._ads_var_set_temp, pyads.PLCTYPE_LREAL
        )

        mode = self._ads_hub.read_by_name(self._ads_var_mode, pyads.PLCTYPE_INT)
        self._attr_hvac_mode = {
            0: HVACMode.OFF,
            1: HVACMode.HEAT,
            2: HVACMode.COOL,
        }.get(mode, HVACMode.OFF)

        # Determine the HVAC action based on the mode and temperatures
        if self._attr_hvac_mode == HVACMode.OFF:
            self._attr_hvac_action = HVACAction.OFF
        elif self._attr_hvac_mode == HVACMode.HEAT:
            if (
                self._attr_current_temperature is not None
                and self._attr_target_temperature is not None
                and self._attr_current_temperature < self._attr_target_temperature
            ):
                self._attr_hvac_action = HVACAction.HEATING
            else:
                self._attr_hvac_action = HVACAction.IDLE
        elif self._attr_hvac_mode == HVACMode.COOL:
            if (
                self._attr_current_temperature is not None
                and self._attr_target_temperature is not None
                and self._attr_current_temperature > self._attr_target_temperature
            ):
                self._attr_hvac_action = HVACAction.COOLING
            else:
                self._attr_hvac_action = HVACAction.IDLE

        self.async_write_ha_state()
