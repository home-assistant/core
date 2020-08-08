"""Support for Smart Meter Texas sensors."""
import logging

from smart_meter_texas import Meter

from homeassistant.const import CONF_ADDRESS, ENERGY_KILO_WATT_HOUR
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, ELECTRIC_METER, ESIID, METER_NUMBER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smart Meter Texas sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    meters = coordinator.data.meters

    async_add_entities(
        [SmartMeterTexasSensor(meter, coordinator) for meter in meters], True
    )


class SmartMeterTexasSensor(Entity):
    """Representation of an Smart Meter Texas sensor."""

    def __init__(self, meter: Meter, coordinator: DataUpdateCoordinator):
        """Initialize the sensor."""
        self.meter = meter
        self.coordinator = coordinator

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_KILO_WATT_HOUR

    @property
    def name(self):
        """Device Name."""
        return f"{ELECTRIC_METER} {self.meter.meter}"

    @property
    def unique_id(self):
        """Device Uniqueid."""
        return f"{METER_NUMBER}_{self.meter.meter}"

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def state(self):
        """Get the latest reading."""
        return self.meter.reading

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        attributes = {
            METER_NUMBER: self.meter.meter,
            ESIID: self.meter.esiid,
            CONF_ADDRESS: self.meter.address,
        }
        return attributes

    @property
    def should_poll(self):
        """Return False, updates are controlled via coordinator."""
        return False

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
