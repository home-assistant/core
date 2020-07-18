"""Support for Smart Meter Texas sensors."""
import logging

from homeassistant.const import ENERGY_KILO_WATT_HOUR
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, LAST_UPDATED

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smart Meter Texas sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    meter_number = config_entry.data["meter"]
    esiid = config_entry.data["esiid"]

    async_add_entities([SmartMeterTexasSensor(coordinator, meter_number, esiid)], True)


class SmartMeterTexasSensor(Entity):
    """Representation of an Smart Meter Texas sensor."""

    def __init__(self, coordinator, meter_number, esiid):
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._meter_number = meter_number
        self._esiid = esiid
        self._last_updated = coordinator.data.reading_datetime

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_KILO_WATT_HOUR

    @property
    def name(self):
        """Device Name."""
        return "Electric meter"

    @property
    def icon(self):
        """Device Ice."""
        return "mdi:counter"

    @property
    def unique_id(self):
        """Device Uniqueid."""
        return f"electric_meter_{self._meter_number}"

    @property
    def available(self):
        """Return True if entity is available."""
        return self._coordinator.last_update_success

    @property
    def state(self):
        """Get the current price."""
        return self._coordinator.data.reading

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        attributes = {}

        if self._last_updated is not None:
            attributes[LAST_UPDATED] = self._last_updated

        attributes["meter"] = self._meter_number
        attributes["esiid"] = self._esiid

        return attributes

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
