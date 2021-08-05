"""Support for the Hive climate devices."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_BOOST,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.helpers import config_validation as cv, entity_platform

from . import HiveEntity, refresh_system
from .const import (
    ATTR_TIME_PERIOD,
    DOMAIN,
    SERVICE_BOOST_HEATING_OFF,
    SERVICE_BOOST_HEATING_ON,
)

HIVE_TO_HASS_STATE = {
    "SCHEDULE": HVAC_MODE_AUTO,
    "MANUAL": HVAC_MODE_HEAT,
    "OFF": HVAC_MODE_OFF,
}

HASS_TO_HIVE_STATE = {
    HVAC_MODE_AUTO: "SCHEDULE",
    HVAC_MODE_HEAT: "MANUAL",
    HVAC_MODE_OFF: "OFF",
}

HIVE_TO_HASS_HVAC_ACTION = {
    "UNKNOWN": CURRENT_HVAC_OFF,
    False: CURRENT_HVAC_IDLE,
    True: CURRENT_HVAC_HEAT,
}

TEMP_UNIT = {"C": TEMP_CELSIUS, "F": TEMP_FAHRENHEIT}

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
SUPPORT_HVAC = [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF]
SUPPORT_PRESET = [PRESET_NONE, PRESET_BOOST]
PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)
_LOGGER = logging.getLogger()


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hive thermostat based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.session.deviceList.get("climate")
    entities = []
    if devices:
        for dev in devices:
            entities.append(HiveClimateEntity(hive, dev))
    async_add_entities(entities, True)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "boost_heating",
        {
            vol.Required(ATTR_TIME_PERIOD): vol.All(
                cv.time_period,
                cv.positive_timedelta,
                lambda td: td.total_seconds() // 60,
            ),
            vol.Optional(ATTR_TEMPERATURE, default="25.0"): vol.Coerce(float),
        },
        "async_heating_boost",
    )

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

    def __init__(self, hive_session, hive_device):
        """Initialize the Climate device."""
        super().__init__(hive_session, hive_device)
        self.thermostat_node_id = hive_device["device_id"]
        self.temperature_type = TEMP_UNIT.get(hive_device["temperatureunit"])

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.device["device_id"])},
            "name": self.device["device_name"],
            "model": self.device["deviceData"]["model"],
            "manufacturer": self.device["deviceData"]["manufacturer"],
            "sw_version": self.device["deviceData"]["version"],
            "via_device": (DOMAIN, self.device["parentDevice"]),
        }

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the name of the Climate device."""
        return self.device["haName"]

    @property
    def available(self):
        """Return if the device is available."""
        return self.device["deviceData"]["online"]

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return SUPPORT_HVAC

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        return HIVE_TO_HASS_STATE[self.device["status"]["mode"]]

    @property
    def hvac_action(self):
        """Return current HVAC action."""
        return HIVE_TO_HASS_HVAC_ACTION[self.device["status"]["action"]]

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self.temperature_type

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.device["status"]["current_temperature"]

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self.device["status"]["target_temperature"]

    @property
    def min_temp(self):
        """Return minimum temperature."""
        return self.device["min_temp"]

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self.device["max_temp"]

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        if self.device["status"]["boost"] == "ON":
            return PRESET_BOOST
        return None

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return SUPPORT_PRESET

    @refresh_system
    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        new_mode = HASS_TO_HIVE_STATE[hvac_mode]
        await self.hive.heating.setMode(self.device, new_mode)

    @refresh_system
    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        new_temperature = kwargs.get(ATTR_TEMPERATURE)
        if new_temperature is not None:
            await self.hive.heating.setTargetTemperature(self.device, new_temperature)

    @refresh_system
    async def async_set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        if preset_mode == PRESET_NONE and self.preset_mode == PRESET_BOOST:
            await self.hive.heating.setBoostOff(self.device)
        elif preset_mode == PRESET_BOOST:
            curtemp = round(self.current_temperature * 2) / 2
            temperature = curtemp + 0.5
            await self.hive.heating.setBoostOn(self.device, 30, temperature)

    async def async_heating_boost(self, time_period, temperature):
        """Handle boost heating service call."""
        _LOGGER.warning(
            "Hive Service heating_boost will be removed in 2021.7.0, please update to heating_boost_on"
        )
        await self.async_heating_boost_on(time_period, temperature)

    @refresh_system
    async def async_heating_boost_on(self, time_period, temperature):
        """Handle boost heating service call."""
        await self.hive.heating.setBoostOn(self.device, time_period, temperature)

    @refresh_system
    async def async_heating_boost_off(self):
        """Handle boost heating service call."""
        await self.hive.heating.setBoostOff(self.device)

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.heating.getClimate(self.device)
