"""Support for Broadlink climate devices."""
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
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

    if device.api.type in {"HYS"}:
        climate_entities = [BroadlinkThermostat(device)]
        async_add_entities(climate_entities)


class BroadlinkThermostat(ClimateEntity, RestoreEntity):
    """Representation of a Broadlink Hysen climate entity."""

    def __init__(self, device):
        """Initialize the climate entity."""
        self._device = device
        self._coordinator = device.update_manager.coordinator
        self._hvac_mode = None
        self._hvac_action = None
        self._current_temperature = None
        self._target_temperature = None

    @property
    def name(self):
        """Return the name of the thermostat."""
        return f"{self._device.name} Thermostat"

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]
        device = self._device
        await device.async_request(device.api.set_temp, temperature)

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def temperature_unit(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        return self._hvac_mode

    @property
    def hvac_action(self):
        """Return the current HVAC action."""
        return self._hvac_action

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF, HVAC_MODE_AUTO]

    @callback
    def update_data(self):
        """Update data."""
        if self._coordinator.last_update_success:
            state = self._coordinator.data
            if state["power"]:
                if state["auto_mode"]:
                    self._hvac_mode = HVAC_MODE_AUTO
                else:
                    self._hvac_mode = HVAC_MODE_HEAT

                if state["active"]:
                    self._hvac_action = CURRENT_HVAC_HEAT
                else:
                    self._hvac_action = CURRENT_HVAC_IDLE
            else:
                self._hvac_mode = HVAC_MODE_OFF
                self._hvac_action = CURRENT_HVAC_OFF

            self._current_temperature = state["room_temp"]
            self._target_temperature = state["thermostat_temp"]

        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Call when the climate device is added to hass."""
        state = await self.async_get_last_state()
        if state is not None:
            self._hvac_mode = state.state
            self._hvac_action = state.attributes[ATTR_HVAC_ACTION]
            self._current_temperature = state.attributes[ATTR_CURRENT_TEMPERATURE]
            self._target_temperature = state.attributes[ATTR_TEMPERATURE]

        self.async_on_remove(self._coordinator.async_add_listener(self.update_data))

    async def async_update(self):
        """Update the climate entity."""
        await self._coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        device = self._device

        if hvac_mode == HVAC_MODE_OFF:
            await device.async_request(device.api.set_power, 0)

        elif hvac_mode == HVAC_MODE_AUTO:
            await device.async_request(device.api.set_power, 1)
            await device.async_request(device.api.set_mode, 1, 0)

        elif hvac_mode == HVAC_MODE_HEAT:
            await device.async_request(device.api.set_power, 1)
            await device.async_request(device.api.set_mode, 0, 0)
