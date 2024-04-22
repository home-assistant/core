"""Support for the Hive climate devices."""

from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.climate import (
    PRESET_BOOST,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HiveEntity, refresh_system
from .const import (
    ATTR_TIME_PERIOD,
    DOMAIN,
    SERVICE_BOOST_HEATING_OFF,
    SERVICE_BOOST_HEATING_ON,
)

HIVE_TO_HASS_STATE = {
    "SCHEDULE": HVACMode.AUTO,
    "MANUAL": HVACMode.HEAT,
    "OFF": HVACMode.OFF,
}

HASS_TO_HIVE_STATE = {
    HVACMode.AUTO: "SCHEDULE",
    HVACMode.HEAT: "MANUAL",
    HVACMode.OFF: "OFF",
}

HIVE_TO_HASS_HVAC_ACTION = {
    "UNKNOWN": HVACAction.OFF,
    False: HVACAction.IDLE,
    True: HVACAction.HEATING,
}

TEMP_UNIT = {"C": UnitOfTemperature.CELSIUS, "F": UnitOfTemperature.FAHRENHEIT}
PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)
_LOGGER = logging.getLogger()


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hive thermostat based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.session.deviceList.get("climate")
    if devices:
        async_add_entities((HiveClimateEntity(hive, dev) for dev in devices), True)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_BOOST_HEATING_ON,
        {
            vol.Required(ATTR_TIME_PERIOD): vol.All(
                cv.time_period,
                cv.positive_timedelta,
                lambda td: td.total_seconds() // 60,
            ),
            vol.Optional(ATTR_TEMPERATURE, default="25.0"): vol.Coerce(float),
        },
        "async_heating_boost_on",
    )

    platform.async_register_entity_service(
        SERVICE_BOOST_HEATING_OFF,
        {},
        "async_heating_boost_off",
    )


class HiveClimateEntity(HiveEntity, ClimateEntity):
    """Hive Climate Device."""

    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = [PRESET_BOOST, PRESET_NONE]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, hive_session, hive_device):
        """Initialize the Climate device."""
        super().__init__(hive_session, hive_device)
        self.thermostat_node_id = hive_device["device_id"]
        self._attr_temperature_unit = TEMP_UNIT.get(hive_device["temperatureunit"])

    @refresh_system
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        new_mode = HASS_TO_HIVE_STATE[hvac_mode]
        await self.hive.heating.setMode(self.device, new_mode)

    @refresh_system
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        new_temperature = kwargs.get(ATTR_TEMPERATURE)
        if new_temperature is not None:
            await self.hive.heating.setTargetTemperature(self.device, new_temperature)

    @refresh_system
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_NONE and self.preset_mode == PRESET_BOOST:
            await self.hive.heating.setBoostOff(self.device)
        elif preset_mode == PRESET_BOOST:
            curtemp = round((self.current_temperature or 0) * 2) / 2
            temperature = curtemp + 0.5
            await self.hive.heating.setBoostOn(self.device, 30, temperature)

    @refresh_system
    async def async_heating_boost_on(self, time_period, temperature):
        """Handle boost heating service call."""
        await self.hive.heating.setBoostOn(self.device, time_period, temperature)

    @refresh_system
    async def async_heating_boost_off(self):
        """Handle boost heating service call."""
        await self.hive.heating.setBoostOff(self.device)

    async def async_update(self) -> None:
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.heating.getClimate(self.device)
        self._attr_available = self.device["deviceData"].get("online")
        if self._attr_available:
            self._attr_hvac_mode = HIVE_TO_HASS_STATE[self.device["status"]["mode"]]
            self._attr_hvac_action = HIVE_TO_HASS_HVAC_ACTION[
                self.device["status"]["action"]
            ]
            self._attr_current_temperature = self.device["status"][
                "current_temperature"
            ]
            self._attr_target_temperature = self.device["status"]["target_temperature"]
            self._attr_min_temp = self.device["min_temp"]
            self._attr_max_temp = self.device["max_temp"]
            if self.device["status"]["boost"] == "ON":
                self._attr_preset_mode = PRESET_BOOST
            else:
                self._attr_preset_mode = PRESET_NONE
