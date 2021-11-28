"""Support for Generic Micropel Thermostats."""
from __future__ import annotations

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_OFFSET,
    CONF_SCAN_INTERVAL,
    CONF_TEMPERATURE_UNIT,
    CONF_UNIQUE_ID,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMP_KELVIN,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import CLIMATE_SCHEMA
from .const import (
    CONF_CLIMATES,
    CONF_CURRENT_TEMP_ADDRESS,
    CONF_HUB,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_PLC,
    CONF_REGISTER_TYPE,
    CONF_SCALE,
    CONF_STEP,
    CONF_TARGET_TEMP_ADDRESS,
    DOMAIN,
    REGISTER_TYPE_WORD,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CLIMATES): vol.All(cv.ensure_list, [CLIMATE_SCHEMA]),
    }
)


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
):
    """Read configuration and create Micropel climate."""
    climates = []

    for climate in config[CONF_CLIMATES]:
        hub_name = climate[CONF_HUB]
        hub = hass.data[DOMAIN][hub_name]
        climates.append(
            MicropelThermostat(
                hub,
                climate[CONF_SCAN_INTERVAL],
                climate[CONF_UNIQUE_ID],
                climate[CONF_NAME],
                climate.get(CONF_PLC),
                climate[CONF_TARGET_TEMP_ADDRESS],
                climate[CONF_CURRENT_TEMP_ADDRESS],
                climate[CONF_REGISTER_TYPE],
                climate.get(CONF_TEMPERATURE_UNIT),
                climate[CONF_SCALE],
                climate[CONF_OFFSET],
                climate.get(CONF_MAX_TEMP),
                climate.get(CONF_MIN_TEMP),
                climate.get(CONF_STEP),
            )
        )

    if not climates:
        return False
    async_add_entities(climates)


class MicropelThermostat(ClimateEntity):
    """Representation of a Micropel Thermostat."""

    def __init__(
        self,
        hub,
        scan_interval,
        unique_id,
        name,
        plc,
        target_temp_address,
        current_temp_address,
        register_type,
        temperature_unit,
        scale,
        offset,
        max_temp,
        min_temp,
        temp_step,
    ):
        """Initialize the Micropel thermostat."""
        self._hub = hub
        self._unique_id = unique_id
        self._name = name
        self._plc = int(plc)
        self._target_temp_address = int(target_temp_address)
        self._current_temp_address = int(current_temp_address)
        self._register_type = register_type
        self._temperature_unit = temperature_unit
        self._scale = scale
        self._offset = float(offset)
        self._scan_interval = timedelta(seconds=scan_interval)
        self._max_temp = max_temp
        self._min_temp = min_temp
        self._temp_step = temp_step
        self._current_temperature = None
        self._target_temperature = None
        self._available = True

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        async_track_time_interval(
            self.hass, lambda arg: self._update(), self._scan_interval
        )

    @property
    def unique_id(self) -> str:
        """Return the uuid as the unique_id."""
        return self._unique_id

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        # Handle polling directly in this entity
        return False

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self):
        """Return the possible HVAC modes."""
        return [HVAC_MODE_AUTO]

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        # Home Assistant expects this method.
        # We'll keep it here to avoid getting exceptions.

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._target_temperature

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._temperature_unit == "F" or self._temperature_unit == "°F":
            return TEMP_FAHRENHEIT
        if self._temperature_unit == "K" or self._temperature_unit == "°K":
            return TEMP_KELVIN
        return TEMP_CELSIUS

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._max_temp

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._temp_step

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temperature = int(
            (kwargs.get(ATTR_TEMPERATURE) - self._offset) / self._scale
        )
        if target_temperature is None:
            return
        self._write_temp(self._target_temp_address, target_temperature)
        self._update()

    def _update(self):
        """Update Target & Current Temperature."""
        try:
            if self._register_type == REGISTER_TYPE_WORD:
                target_temp = self._hub.read_word(self._plc, self._target_temp_address)
                current_temp = self._hub.read_word(
                    self._plc, self._current_temp_address
                )
        except Exception:
            self._available = False
            return

        self._target_temperature = round(
            (int(target_temp, 0) * self._scale) + self._offset
        )
        self._current_temperature = round(
            (int(current_temp, 0) * self._scale) + self._offset
        )

        self._available = True
        self.schedule_update_ha_state()

    def _write_temp(self, address, value):
        """Write word using the Micropel hub PLC."""
        try:
            self._hub.write_word(self._plc, address, value)
        except Exception:
            self._available = False
            return

        self._available = True
