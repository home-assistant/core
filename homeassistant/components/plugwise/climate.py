"""Plugwise Climate component for Home Assistant."""

import logging
from typing import Dict

from Plugwise_Smile.Smile import Smile

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import callback

from .const import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP, DOMAIN, THERMOSTAT_ICON

HVAC_MODES_1 = [HVAC_MODE_HEAT, HVAC_MODE_AUTO]
HVAC_MODES_2 = [HVAC_MODE_HEAT_COOL, HVAC_MODE_AUTO]

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smile Thermostats from a config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    updater = hass.data[DOMAIN][config_entry.entry_id]["updater"]

    devices = []
    thermostat_classes = [
        "thermostat",
        "zone_thermostat",
        "thermostatic_radiator_valve",
    ]
    all_devices = api.get_all_devices()

    for dev_id, device in all_devices.items():

        if device["class"] not in thermostat_classes:
            continue

        thermostat = PwThermostat(
            api,
            updater,
            device["name"],
            dev_id,
            device["location"],
            device["class"],
            DEFAULT_MIN_TEMP,
            DEFAULT_MAX_TEMP,
        )

        if not thermostat:
            continue

        devices.append(thermostat)
        _LOGGER.info("Added climate.%s", "{}".format(device["name"]))

    async_add_entities(devices, True)


class PwThermostat(ClimateEntity):
    """Representation of an Plugwise thermostat."""

    def __init__(self, api, updater, name, dev_id, loc_id, model, min_temp, max_temp):
        """Set up the Plugwise API."""
        self._api = api
        self._updater = updater
        self._name = name
        self._dev_id = dev_id
        self._loc_id = loc_id
        self._model = model
        self._min_temp = min_temp
        self._max_temp = max_temp

        self._selected_schema = None
        self._last_active_schema = None
        self._preset_mode = None
        self._presets = None
        self._presets_list = None
        self._boiler_state = None
        self._heating_state = None
        self._cooling_state = None
        self._dhw_state = None
        self._hvac_mode = None
        self._schema_names = None
        self._schema_status = None
        self._temperature = None
        self._setpoint = None
        self._water_pressure = None
        self._schedule_temp = None
        self._hvac_mode = None
        self._single_thermostat = self._api.single_master_thermostat()
        self._unique_id = f"cl-{dev_id}-{self._name}"

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._updater.async_add_listener(self._update_callback)

    async def async_will_remove_from_hass(self):
        """Disconnect callbacks."""
        self._updater.async_remove_listener(self._update_callback)

    @callback
    def _update_callback(self):
        """Call update method."""
        self.update()
        self.async_write_ha_state()

    @property
    def hvac_action(self):
        """Return the current action."""
        if self._single_thermostat:
            if self._heating_state or self._boiler_state:
                return CURRENT_HVAC_HEAT
            if self._cooling_state:
                return CURRENT_HVAC_COOL
            return CURRENT_HVAC_IDLE
        if self._heating_state is not None or self._boiler_state is not None:
            if self._setpoint > self._temperature:
                return CURRENT_HVAC_HEAT
            if self._cooling_state:
                return CURRENT_HVAC_COOL
            return CURRENT_HVAC_IDLE
        if self._heating_state is not None or self._boiler_state is not None:
            if self._setpoint > self._temperature:
                return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""

        via_device = self._api.gateway_id
        if self._dev_id is via_device:
            via_device = None

        return {
            "identifiers": {(DOMAIN, self._dev_id)},
            "name": self._name,
            "manufacturer": "Plugwise",
            "model": self._model.replace("_", " ").title(),
            "via_device": via_device,
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return THERMOSTAT_ICON

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        attributes = {}
        if self._schema_names:
            attributes["available_schemas"] = self._schema_names
        if self._selected_schema:
            attributes["selected_schema"] = self._selected_schema
        return attributes

    @property
    def preset_modes(self):
        """Return the available preset modes list."""
        return self._presets_list

    @property
    def hvac_modes(self):
        """Return the available hvac modes list."""
        if self._heating_state is not None or self._boiler_state is not None:
            if self._cooling_state is not None:
                return HVAC_MODES_2
            return HVAC_MODES_1

    @property
    def hvac_mode(self):
        """Return current active hvac state."""
        return self._hvac_mode

    @property
    def target_temperature(self):
        """Return the target_temperature."""
        return self._setpoint

    @property
    def preset_mode(self):
        """Return the active preset."""
        if self._presets:
            return self._preset_mode
        return None

    @property
    def current_temperature(self):
        """Return the current room temperature."""
        return self._temperature

    @property
    def min_temp(self):
        """Return the minimal temperature possible to set."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature possible to set."""
        return self._max_temp

    @property
    def temperature_unit(self):
        """Return the unit of measured temperature."""
        return TEMP_CELSIUS

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if (temperature is not None) and (
            self._min_temp < temperature < self._max_temp
        ):
            try:
                await self._api.set_temperature(self._loc_id, temperature)
                self._setpoint = temperature
                self.async_write_ha_state()
            except Smile.PlugwiseError:
                _LOGGER.error("Error while communicating to device")
        else:
            _LOGGER.error("Invalid temperature requested")

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the hvac mode."""
        state = "false"
        if hvac_mode == HVAC_MODE_AUTO:
            state = "true"
            try:
                await self._api.set_temperature(self._loc_id, self._schedule_temp)
                self._setpoint = self._schedule_temp
            except Smile.PlugwiseError:
                _LOGGER.error("Error while communicating to device")
        try:
            await self._api.set_schedule_state(
                self._loc_id, self._last_active_schema, state
            )
            self._hvac_mode = hvac_mode
            self.async_write_ha_state()
        except Smile.PlugwiseError:
            _LOGGER.error("Error while communicating to device")

    async def async_set_preset_mode(self, preset_mode):
        """Set the preset mode."""
        try:
            await self._api.set_preset(self._loc_id, preset_mode)
            self._preset_mode = preset_mode
            self._setpoint = self._presets.get(self._preset_mode, "none")[0]
            self.async_write_ha_state()
        except Smile.PlugwiseError:
            _LOGGER.error("Error while communicating to device")

    def update(self):
        """Update the data for this climate device."""
        _LOGGER.info("Updating climate...")
        climate_data = self._api.get_device_data(self._dev_id)
        heater_central_data = self._api.get_device_data(self._api.heater_id)

        if not climate_data:
            _LOGGER.error("Received no climate_data for device %s.", self._name)
        else:
            if "setpoint" in climate_data:
                self._setpoint = climate_data["setpoint"]
            if "temperature" in climate_data:
                self._temperature = climate_data["temperature"]
            if "schedule_temperature" in climate_data:
                self._schedule_temp = climate_data["schedule_temperature"]
            if "available_schedules" in climate_data:
                self._schema_names = climate_data["available_schedules"]
            if "selected_schedule" in climate_data:
                self._selected_schema = climate_data["selected_schedule"]
                if self._selected_schema is not None:
                    self._schema_status = True
                else:
                    self._schema_status = False
            if "last_used" in climate_data:
                self._last_active_schema = climate_data["last_used"]
            if "presets" in climate_data:
                self._presets = climate_data["presets"]
                if self._presets:
                    self._presets_list = list(self._presets)
            if "active_preset" in climate_data:
                self._preset_mode = climate_data["active_preset"]

        if not heater_central_data:
            _LOGGER.error("Received no heater_central_data for device %s.", self._name)
        else:
            if "boiler_state" in heater_central_data:
                if heater_central_data["boiler_state"] is not None:
                    self._boiler_state = heater_central_data["boiler_state"]
            if "heating_state" in heater_central_data:
                if heater_central_data["heating_state"] is not None:
                    self._heating_state = heater_central_data["heating_state"]
            if "cooling_state" in heater_central_data:
                if heater_central_data["cooling_state"] is not None:
                    self._cooling_state = heater_central_data["cooling_state"]

        if self._schema_status:
            self._hvac_mode = HVAC_MODE_AUTO
        elif self._heating_state is not None or self._boiler_state is not None:
            if self._cooling_state is not None:
                self._hvac_mode = HVAC_MODE_HEAT_COOL
            self._hvac_mode = HVAC_MODE_HEAT
        elif self._cooling_state is not None:
            if self._heating_state is not None or self._boiler_state is not None:
                self._hvac_mode = HVAC_MODE_HEAT_COOL
