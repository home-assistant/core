"""Plugwise Climate component for Home Assistant."""
from typing import Any

from plugwise.exceptions import PlugwiseException
from plugwise.smile import Smile

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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    COORDINATOR,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN,
    LOGGER,
    SCHEDULE_OFF,
    SCHEDULE_ON,
)
from .entity import PlugwiseEntity

HVAC_MODES_HEAT_ONLY = [HVAC_MODE_HEAT, HVAC_MODE_AUTO]
HVAC_MODES_HEAT_COOL = [HVAC_MODE_HEAT_COOL, HVAC_MODE_AUTO]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile Thermostats from a config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    entities = []
    thermostat_classes = [
        "thermostat",
        "zone_thermostat",
        "thermostatic_radiator_valve",
    ]
    all_devices = api.get_all_devices()

    for dev_id, device_properties in all_devices.items():

        if device_properties["class"] not in thermostat_classes:
            continue

        thermostat = PwThermostat(
            api,
            coordinator,
            device_properties["name"],
            dev_id,
            device_properties["location"],
            device_properties["class"],
        )

        entities.append(thermostat)

    async_add_entities(entities, True)


class PwThermostat(PlugwiseEntity, ClimateEntity):
    """Representation of an Plugwise thermostat."""

    _attr_hvac_mode = HVAC_MODE_HEAT
    _attr_max_temp = DEFAULT_MAX_TEMP
    _attr_min_temp = DEFAULT_MIN_TEMP
    _attr_preset_mode = None
    _attr_preset_modes = None
    _attr_supported_features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_hvac_modes = HVAC_MODES_HEAT_ONLY
    _attr_hvac_mode = HVAC_MODE_HEAT

    def __init__(
        self,
        api: Smile,
        coordinator: DataUpdateCoordinator,
        name: str,
        dev_id: str,
        loc_id: str,
        model: str,
    ) -> None:
        """Set up the Plugwise API."""
        super().__init__(api, coordinator, name, dev_id)
        self._attr_extra_state_attributes = {}
        self._attr_unique_id = f"{dev_id}-climate"

        self._api = api
        self._loc_id = loc_id
        self._model = model

        self._presets = None
        self._single_thermostat = self._api.single_master_thermostat()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if (temperature is not None) and (
            self._attr_min_temp < temperature < self._attr_max_temp
        ):
            try:
                await self._api.set_temperature(self._loc_id, temperature)
                self._attr_target_temperature = temperature
                self.async_write_ha_state()
            except PlugwiseException:
                LOGGER.error("Error while communicating to device")
        else:
            LOGGER.error("Invalid temperature requested")

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set the hvac mode."""
        state = SCHEDULE_OFF
        climate_data = self._api.get_device_data(self._dev_id)

        if hvac_mode == HVAC_MODE_AUTO:
            state = SCHEDULE_ON
            try:
                await self._api.set_temperature(
                    self._loc_id, climate_data.get("schedule_temperature")
                )
                self._attr_target_temperature = climate_data.get("schedule_temperature")
            except PlugwiseException:
                LOGGER.error("Error while communicating to device")

        try:
            await self._api.set_schedule_state(
                self._loc_id, climate_data.get("last_used"), state
            )
            self._attr_hvac_mode = hvac_mode
            self.async_write_ha_state()
        except PlugwiseException:
            LOGGER.error("Error while communicating to device")

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        if self._presets is None:
            raise ValueError("No presets available")

        try:
            await self._api.set_preset(self._loc_id, preset_mode)
            self._attr_preset_mode = preset_mode
            self._attr_target_temperature = self._presets.get(preset_mode, "none")[0]
            self.async_write_ha_state()
        except PlugwiseException:
            LOGGER.error("Error while communicating to device")

    @callback
    def _async_process_data(self) -> None:
        """Update the data for this climate device."""
        climate_data = self._api.get_device_data(self._dev_id)
        heater_central_data = self._api.get_device_data(self._api.heater_id)

        # Current & set temperatures
        if setpoint := climate_data.get("setpoint"):
            self._attr_target_temperature = setpoint
        if temperature := climate_data.get("temperature"):
            self._attr_current_temperature = temperature

        # Presets handling
        self._attr_preset_mode = climate_data.get("active_preset")
        if presets := climate_data.get("presets"):
            self._presets = presets
            self._attr_preset_modes = list(presets)
        else:
            self._presets = None
            self._attr_preset_mode = None

        # Determine current hvac action
        self._attr_hvac_action = CURRENT_HVAC_IDLE
        if self._single_thermostat:
            if heater_central_data.get("heating_state"):
                self._attr_hvac_action = CURRENT_HVAC_HEAT
            elif heater_central_data.get("cooling_state"):
                self._attr_hvac_action = CURRENT_HVAC_COOL
        elif (
            self.target_temperature is not None
            and self.current_temperature is not None
            and self.target_temperature > self.current_temperature
        ):
            self._attr_hvac_action = CURRENT_HVAC_HEAT

        # Determine hvac modes and current hvac mode
        self._attr_hvac_mode = HVAC_MODE_HEAT
        self._attr_hvac_modes = HVAC_MODES_HEAT_ONLY
        if heater_central_data.get("compressor_state") is not None:
            self._attr_hvac_mode = HVAC_MODE_HEAT_COOL
            self._attr_hvac_modes = HVAC_MODES_HEAT_COOL
        if climate_data.get("selected_schedule") is not None:
            self._attr_hvac_mode = HVAC_MODE_AUTO

        # Extra attributes
        self._attr_extra_state_attributes = {
            "available_schemas": climate_data.get("available_schedules"),
            "selected_schema": climate_data.get("selected_schedule"),
        }

        self.async_write_ha_state()
