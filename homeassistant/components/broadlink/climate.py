"""Support for Broadlink climate devices."""
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Broadlink climate entities."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]

    if device.api.type in {"Hysen heating controller"}:
        climate_entities = [BroadlinkHysen(device)]
    async_add_entities(climate_entities)


class BroadlinkHysen(ClimateEntity, RestoreEntity):
    """Representation of a Broadlink Hysen climate entity."""

    def __init__(self, device):
        """Initialize the climate entity."""
        self._device = device
        self._coordinator = device.update_manager.coordinator
        self._supported_features = SUPPORT_TARGET_TEMPERATURE
        self._hvac_mode = None

    @property
    def name(self):
        """Return the name of the thermostat."""
        return f"{self._device.name} Thermostat"

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
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
        """Return the current HVAC mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @callback
    def update_data(self):
        """Update data."""
        if self._coordinator.last_update_success:
            if self._coordinator.data["power"]:
                if self._coordinator.data["active"]:
                    self._hvac_mode = HVAC_MODE_HEAT
                    self._hvac_action = CURRENT_HVAC_HEAT
                else:
                    self._hvac_action = CURRENT_HVAC_IDLE
                if self._coordinator.data["auto_mode"]:
                    self._hvac_mode = HVAC_MODE_AUTO
            else:
                self._hvac_action = CURRENT_HVAC_OFF
                self._hvac_mode = HVAC_MODE_OFF
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Call when the climate device is added to hass."""
        self.async_on_remove(self._coordinator.async_add_listener(self.update_data))

    async def async_update(self):
        """Update the climate entity."""
        await self._coordinator.async_request_refresh()

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_HEAT:
            self._device.api.set_power(1)
        elif hvac_mode == HVAC_MODE_OFF:
            self._device.api.set_power(0)
