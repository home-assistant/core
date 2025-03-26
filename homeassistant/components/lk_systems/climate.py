"""Support for LK Systems climate entities."""

import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up LK Systems climate entities from a config entry."""
    coordinator = hass.data[DOMAIN]["coordinator"]
    data = coordinator.data
    api = hass.data[DOMAIN]["api"]
    zones = api.get_zone_names(data)
    entities = [
        LKClimateEntity(coordinator, api, zone_id, name)
        for zone_id, name in enumerate(zones)
        if data["active"][zone_id] == "1"
    ]
    async_add_entities(entities)


class LKClimateEntity(CoordinatorEntity, ClimateEntity):
    """Representation of an LK Systems climate entity."""

    def __init__(self, coordinator, api, zone_idx, name):
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._api = api
        self._zone_idx = zone_idx
        self._name = name
        self._attr_hvac_mode = HVACMode.HEAT

    @property
    def name(self):
        """Return the name of the climate entity."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    def hvac_modes(self):
        """Return the list of supported HVAC modes."""
        return [HVACMode.HEAT]

    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        return self._attr_hvac_mode

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return float(self.coordinator.data["set_room_deg"][self._zone_idx]) / 100.0

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return float(self.coordinator.data["get_room_deg"][self._zone_idx]) / 100.0

    async def async_set_temperature(self, **kwargs):
        """Set a new target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        await self._api.set_room_temperature(self._zone_idx, temperature)
        await self.coordinator.async_request_refresh()
