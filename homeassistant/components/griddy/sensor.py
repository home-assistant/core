"""Support for August sensors."""
from homeassistant.const import CURRENCY_CENT, ENERGY_KILO_WATT_HOUR
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_LOADZONE, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the August sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    settlement_point = config_entry.data[CONF_LOADZONE]

    async_add_entities([GriddyPriceSensor(settlement_point, coordinator)], True)


class GriddyPriceSensor(CoordinatorEntity):
    """Representation of an August sensor."""

    def __init__(self, settlement_point, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._settlement_point = settlement_point

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return f"{CURRENCY_CENT}/{ENERGY_KILO_WATT_HOUR}"

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
    def state(self):
        """Get the current price."""
        return round(float(self.coordinator.data.now.price_cents_kwh), 4)
