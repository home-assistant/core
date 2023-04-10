"""Support for Broadlink climate devices."""
from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .entity import BroadlinkEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Broadlink climate entities."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]

    if device.api.type in {"HYS"}:
        climate_entities = [BroadlinkThermostat(device)]
        async_add_entities(climate_entities)


class BroadlinkThermostat(ClimateEntity, BroadlinkEntity, RestoreEntity):
    """Representation of a Broadlink Hysen climate entity."""

    def __init__(self, device):
        """Initialize the climate entity."""
        super().__init__(device)
        self._device = device
        self._coordinator = device.update_manager.coordinator
        self._attr_hvac_action = None
        self._attr_hvac_mode = None
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_target_temperature_step = 0.5
        self._attr_unique_id = device.unique_id

    @property
    def name(self):
        """Return the name of the thermostat."""
        return f"{self._device.name} Thermostat"

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return ClimateEntityFeature.TARGET_TEMPERATURE

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]
        device = self._device
        self._attr_target_temperature = temperature
        self.async_write_ha_state()
        await device.async_request(device.api.set_temp, temperature)

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._attr_target_temperature_step

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._attr_current_temperature

    @property
    def temperature_unit(self):
        """Return the unit of measurement that is used."""
        return UnitOfTemperature.CELSIUS

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._attr_target_temperature

    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        return self._attr_hvac_mode

    @property
    def hvac_action(self):
        """Return the current HVAC action."""
        return self._attr_hvac_action

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [HVACMode.HEAT, HVACMode.OFF, HVACMode.AUTO]

    @callback
    def update_data(self):
        """Update data."""
        if self._coordinator.last_update_success:
            state = self._coordinator.data
            if state["power"]:
                if state["auto_mode"]:
                    self._attr_hvac_mode = HVACMode.AUTO
                else:
                    self._attr_hvac_mode = HVACMode.HEAT

                if state["active"]:
                    self._attr_hvac_action = HVACAction.HEATING
                else:
                    self._attr_hvac_action = HVACAction.IDLE
            else:
                self._attr_hvac_mode = HVACMode.OFF
                self._attr_hvac_action = HVACAction.OFF

            self._attr_current_temperature = state["room_temp"]
            self._attr_target_temperature = state["thermostat_temp"]

        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Call when the climate device is added to hass."""
        state = await self.async_get_last_state()
        if state is not None:
            self._attr_hvac_mode = state.state
            self._attr_hvac_action = state.attributes[ATTR_HVAC_ACTION]
            self._attr_current_temperature = state.attributes[ATTR_CURRENT_TEMPERATURE]
            self._attr_target_temperature = state.attributes[ATTR_TEMPERATURE]
        self.async_write_ha_state()
        self.async_on_remove(self._coordinator.async_add_listener(self.update_data))

    async def async_update(self):
        """Update the climate entity."""
        await self._coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        device = self._device
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()
        if hvac_mode == HVACMode.OFF:
            await device.async_request(device.api.set_power, 0)

        elif hvac_mode == HVACMode.AUTO:
            await device.async_request(device.api.set_power, 1)
            await device.async_request(device.api.set_mode, 1, 0)

        elif hvac_mode == HVACMode.HEAT:
            await device.async_request(device.api.set_power, 1)
            await device.async_request(device.api.set_mode, 0, 0)
