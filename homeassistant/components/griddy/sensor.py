"""Support for August sensors."""
import logging

from homeassistant.const import ENERGY_KILO_WATT_HOUR
from homeassistant.helpers.entity import Entity

from .const import CONF_LOADZONE, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the August sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    settlement_point = config_entry.data[CONF_LOADZONE]

    async_add_entities([GriddyPriceSensor(settlement_point, coordinator)], True)


class GriddyPriceSensor(Entity):
    """Representation of an August sensor."""

    def __init__(self, settlement_point, coordinator):
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._settlement_point = settlement_point

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return f"¢/{ENERGY_KILO_WATT_HOUR}"

    @property
    def name(self):
        """Device Name."""
        return f"{self._settlement_point} Price Now"

    @property
    def icon(self):
        """Device Ice."""
        return "mdi:currency-usd"

    @property
    def unique_id(self):
        """Device Uniqueid."""
        return f"{self._settlement_point}_price_now"

    @property
    def available(self):
        """Return True if entity is available."""
        return self._coordinator.last_update_success

    @property
    def state(self):
        """Get the current price."""
        return round(float(self._coordinator.data.now.price_cents_kwh), 4)

    @property
    def should_poll(self):
        """Return False, updates are controlled via coordinator."""
        return False

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
