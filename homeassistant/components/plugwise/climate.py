"""Plugwise Climate component for Home Assistant."""

import logging

from plugwise.exceptions import PlugwiseException

from homeassistant.components.climate import ClimateEntity, ClimateEntityDescription
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_HOME,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_NAME, ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import callback

from .const import (
    API,
    CLIMATE_DOMAIN,
    COORDINATOR,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN,
    FW,
    MASTER_THERMOSTATS,
    PW_CLASS,
    PW_LOCATION,
    PW_MODEL,
    SCHEDULE_OFF,
    SCHEDULE_ON,
    VENDOR,
)
from .gateway import SmileGateway
from .smile_helpers import GWThermostat

HVAC_MODES_HEAT_ONLY = [HVAC_MODE_HEAT, HVAC_MODE_AUTO, HVAC_MODE_OFF]
HVAC_MODES_HEAT_COOL = [HVAC_MODE_HEAT_COOL, HVAC_MODE_AUTO, HVAC_MODE_OFF]

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smile Thermostats from a config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id][API]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    entities = []
    for dev_id in coordinator.data[1]:
        if coordinator.data[1][dev_id][PW_CLASS] not in MASTER_THERMOSTATS:
            continue

        thermostat = PwThermostat(
            api,
            coordinator,
            ClimateEntityDescription(
                key=f"{dev_id}_thermostat",
                name=coordinator.data[1][dev_id].get(ATTR_NAME),
            ),
            dev_id,
            DEFAULT_MAX_TEMP,
            DEFAULT_MIN_TEMP,
        )
        entities.append(thermostat)

    async_add_entities(entities, True)


class PwThermostat(SmileGateway, ClimateEntity):
    """Representation of a Plugwise (zone) thermostat."""

    def __init__(
        self,
        api,
        coordinator,
        description: ClimateEntityDescription,
        dev_id,
        max_temp,
        min_temp,
    ):
        """Set up the PwThermostat."""
        _cdata = coordinator.data[1][dev_id]
        super().__init__(
            coordinator,
            description,
            dev_id,
            _cdata.get(PW_MODEL),
            description.name,
            _cdata.get(VENDOR),
            _cdata.get(FW),
        )

        self._gw_thermostat = GWThermostat(coordinator.data, dev_id)

        self._api = api
        self._attr_current_temperature = None
        self._attr_device_class = None
        self._attr_hvac_mode = None
        self._attr_max_temp = max_temp
        self._attr_min_temp = min_temp
        self._attr_name = description.name
        self._attr_preset_mode = None
        self._attr_preset_modes = None
        self._attr_supported_features = SUPPORT_FLAGS
        self._attr_target_temperature = None
        self._attr_temperature_unit = TEMP_CELSIUS
        self._attr_unique_id = f"{dev_id}-{CLIMATE_DOMAIN}"
        self._cor_data = coordinator.data
        self._loc_id = _cdata.get(PW_LOCATION)

    @property
    def hvac_action(self):
        """Return the current action."""
        if self._cor_data[0]["single_master_thermostat"]:
            if self._gw_thermostat.heating_state:
                return CURRENT_HVAC_HEAT
            if self._gw_thermostat.cooling_state:
                return CURRENT_HVAC_COOL
            return CURRENT_HVAC_IDLE

        if (
            self._gw_thermostat.target_temperature
            > self._gw_thermostat.current_temperature
        ):
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    @property
    def hvac_modes(self):
        """Return the available hvac modes list."""
        if self._gw_thermostat.compressor_state is not None:
            return HVAC_MODES_HEAT_COOL
        return HVAC_MODES_HEAT_ONLY

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if (temperature is not None) and (
            self._attr_min_temp < temperature < self._attr_max_temp
        ):
            try:
                await self._api.set_temperature(self._loc_id, temperature)
                self._attr_target_temperature = temperature
                self.async_write_ha_state()
                _LOGGER.debug("Set temperature to %s ºC ", temperature)
            except PlugwiseException:
                _LOGGER.error("Error while communicating to device")
        else:
            _LOGGER.error("Invalid temperature requested")

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the hvac mode, options are 'off', 'heat'/'heat_cool' and 'auto'."""
        state = SCHEDULE_OFF
        if hvac_mode == HVAC_MODE_AUTO:
            state = SCHEDULE_ON
            try:
                schedule_temp = self._gw_thermostat.schedule_temperature
                await self._api.set_temperature(self._loc_id, schedule_temp)
                self._attr_target_temperature = schedule_temp
            except PlugwiseException:
                _LOGGER.error("Error while communicating to device")

        try:
            await self._api.set_schedule_state(
                self._loc_id, self._gw_thermostat.last_active_schema, state
            )

            # Feature request - mimic HomeKit behavior
            if hvac_mode == HVAC_MODE_OFF:
                preset_mode = PRESET_AWAY
                await self._api.set_preset(self._loc_id, preset_mode)
                self._attr_preset_mode = preset_mode
                self._attr_target_temperature = self._gw_thermostat.presets.get(
                    preset_mode, PRESET_NONE
                )[0]
            if (
                hvac_mode in [HVAC_MODE_HEAT, HVAC_MODE_HEAT_COOL]
                and self._attr_preset_mode == PRESET_AWAY
            ):
                preset_mode = PRESET_HOME
                await self._api.set_preset(self._loc_id, preset_mode)
                self._attr_preset_mode = preset_mode
                self._attr_target_temperature = self._gw_thermostat.presets.get(
                    preset_mode, PRESET_NONE
                )[0]

            self._attr_hvac_mode = hvac_mode
            self.async_write_ha_state()
            _LOGGER.debug("Set hvac_mode to %s", hvac_mode)
        except PlugwiseException:
            _LOGGER.error("Error while communicating to device")

    async def async_set_preset_mode(self, preset_mode):
        """Set the preset mode."""
        try:
            await self._api.set_preset(self._loc_id, preset_mode)
            self._attr_preset_mode = preset_mode
            self._attr_target_temperature = self._gw_thermostat.presets.get(
                preset_mode, PRESET_NONE
            )[0]
            self.async_write_ha_state()
            _LOGGER.debug("Set preset_mode to %s", preset_mode)
        except PlugwiseException:
            _LOGGER.error("Error while communicating to device")

    @callback
    def _async_process_data(self):
        """Update the data for this climate device."""
        self._gw_thermostat.update_data()

        self._attr_current_temperature = self._gw_thermostat.current_temperature
        self._attr_extra_state_attributes = self._gw_thermostat.extra_state_attributes
        self._attr_hvac_mode = self._gw_thermostat.hvac_mode
        self._attr_preset_mode = self._gw_thermostat.preset_mode
        self._attr_preset_modes = self._gw_thermostat.preset_modes
        self._attr_target_temperature = self._gw_thermostat.target_temperature

        self.async_write_ha_state()
