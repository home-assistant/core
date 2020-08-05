"""Support for Smart Meter Texas sensors."""
from datetime import timedelta
import logging

from smart_meter_texas import Client, Meter

from homeassistant.const import CONF_ADDRESS, ENERGY_KILO_WATT_HOUR
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=1)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smart Meter Texas sensors."""
    smartmetertexas = hass.data[DOMAIN][config_entry.entry_id]
    for meter in smartmetertexas.meters:
        async_add_entities([SmartMeterTexasSensor(meter, smartmetertexas.client)], True)


class SmartMeterTexasSensor(Entity):
    """Representation of an Smart Meter Texas sensor."""

    def __init__(self, meter: Meter, client: Client):
        """Initialize the sensor."""
        self.meter = meter
        self.client = client

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_KILO_WATT_HOUR

    @property
    def name(self):
        """Device Name."""
        return f"Electric meter {self.meter.meter}"

    @property
    def icon(self):
        """Device Ice."""
        return "mdi:counter"

    @property
    def unique_id(self):
        """Device Uniqueid."""
        return f"electric_meter_{self.meter.meter}"

    @property
    def available(self):
        """Return True if entity is available."""
        return True  # self._coordinator.last_update_success

    @property
    def state(self):
        """Get the latest reading."""
        return self.meter.reading

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        attributes = {
            "meter_number": self.meter.meter,
            "electric_service_identifier": self.meter.esiid,
            CONF_ADDRESS: self.meter.address,
            "last_updated": self.meter.reading_datetime,
        }
        return attributes

    @property
    def should_poll(self):
        """Return False, updates are controlled via coordinator."""
        return True

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        _LOGGER.debug("Reading meter %s", self.meter.meter)
        await self.meter.read_meter(self.client)
