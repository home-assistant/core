"""Support for Broadlink climate devices."""

import voluptuous as vol

from homeassistant.const import ATTR_TEMPERATURE, CONF_HOST, TEMP_CELSIUS
from homeassistant.components.climate import ClimateEntity, PLATFORM_SCHEMA
from homeassistant.helpers import config_validation as cv

from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    CURRENT_HVAC_IDLE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.core import callback

from .const import DOMAIN


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST): cv.string}, extra=vol.ALLOW_EXTRA
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Broadlink climate entities."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]

    if device.api.type in {"Hysen heating controller"}:
        climate_entities = [BroadlinkHysen(device)]
    async_add_entities(climate_entities)


class BroadlinkHysen(ClimateEntity):
    """Representation of a Broadlink Hysen climate entity."""

    def __init__(self, device):
        """Initialize the climate entity."""
        self._device = device
        self._coordinator = device.update_manager.coordinator
        self._supported_features = SUPPORT_TARGET_TEMPERATURE
        self._name = "Broadlink Thermosthat"

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._supported_features

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        self._coordinator.data["thermostat_temp"] = temperature
        if temperature is None:
            return None
        if temperature < self.current_temperature + 0.5:
            self._coordinator.data["active"] = 0
        else:
            self.set_hvac_mode(HVAC_MODE_HEAT)
        self._device.api.set_temp(temperature)

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._coordinator.data["room_temp"]

    @property
    def temperature_unit(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._coordinator.data["thermostat_temp"]

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        if (
            self._coordinator.data["power"]
            and self.current_temperature + 0.5 > self.target_temperature
        ):
            return CURRENT_HVAC_IDLE
        if self._coordinator.data["active"]:
            return HVAC_MODE_HEAT
        if not self._coordinator.data["power"]:
            return HVAC_MODE_OFF
        return CURRENT_HVAC_IDLE

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @callback
    def update_data(self):
        """Update data."""
        self.async_write_ha_state()

    async def async_update(self):
        """Update the climate entity."""
        await self._coordinator.async_request_refresh()

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_HEAT:
            if self.current_temperature + 0.5 < self.target_temperature:
                self._coordinator.data["active"] = 1
            self._coordinator.data["power"] = 1
            self._device.api.set_power()
        elif hvac_mode == HVAC_MODE_OFF:
            self._coordinator.data["active"] = 0
            self._coordinator.data["power"] = 0
            self._device.api.set_power(0)
