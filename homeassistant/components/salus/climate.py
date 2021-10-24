"""Climate entity for the Salus integration."""

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Set up the it500 Salus thermostat."""
    coordinator, device = hass.data[DOMAIN][config_entry.entry_id]

    temperature_unit = hass.config.units.temperature_unit
    entity = IT500Salus(coordinator, temperature_unit, device)

    async_add_entities([entity], True)


class IT500Salus(CoordinatorEntity, ClimateEntity):
    """Representation of a Salus IT500 Thermostat."""

    def __init__(self, coordinator, temperature_unit, device):
        """Initialize the thermostat."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._temperature_unit = temperature_unit
        self._device = device

    @property
    def name(self):
        """Return default name for entity."""
        return f"{self._device.name} Temperature"

    @property
    def temperature_unit(self):
        """Return temperature unit user."""
        return self._temperature_unit

    @property
    def current_temperature(self):
        """Return current room temperature."""
        return self._coordinator.data.current_temperature

    @property
    def target_temperature(self):
        """Return currently set target temperature."""
        return self._coordinator.data.current_target_temperature

    @property
    def hvac_mode(self):
        """Return current HVAC mode. IT500 Salus only supports heat/off modes."""
        if self.hvac_action == CURRENT_HVAC_IDLE:
            return HVAC_MODE_OFF
        return HVAC_MODE_HEAT

    @property
    def hvac_action(self):
        """Return current HVAC action."""
        if self._coordinator.data.heat_on:
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    @property
    def hvac_modes(self):
        """Return manageable HVAC modes. IT500 Salus only supports heat/off modes."""
        return [HVAC_MODE_HEAT]

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._device.device_id

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._device.name)},
            "name": self._device.name,
            "model": "IT500 Salus",
            "manufacturer": MANUFACTURER,
        }

    def set_hvac_mode(self, mode: str):
        """We do nothing here as we only support heating."""

    async def async_set_temperature(self, **kwargs):
        """Set a new target temperature."""
        await self._coordinator.set_manual_temperature_override(
            kwargs.get(ATTR_TEMPERATURE)
        )
        self.schedule_update_ha_state(False)
