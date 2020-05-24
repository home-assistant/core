"""Support for guages from flood monitoring API."""
import logging

from homeassistant.const import ATTR_ATTRIBUTION, LENGTH_METERS
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "This uses Environment Agency flood and river level data from the real-time data API"

UNIT_MAPPING = {
    "http://qudt.org/1.1/vocab/unit#Meter": LENGTH_METERS,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up UK Flood Monitoring Sensors."""
    station_key = config_entry.data["station"]

    @callback
    def async_add_entity(station, measurement):
        measurement = Measurement(station, measurement)
        async_add_entities([measurement])
        return measurement

    hass.data[DOMAIN][station_key].async_platform_loaded("sensor", async_add_entity)


class Measurement(Entity):
    """A gauge at a flood monitoring station."""

    def __init__(self, station, measure):
        """Initialise the gauge with a data instance and station."""
        self._station = station
        self._measure = measure
        self._available = True

    @callback
    def async_process_update(self, measure):
        """Process a new reading for this gauge."""
        self._measure = measure
        self._available = "latestReading" in measure
        self.async_write_ha_state()

    @callback
    def async_set_unavailable(self):
        """Mark on entity that sensor failed to update."""
        self._available = False
        self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        """Stations are polled as a group - the entity shouldn't poll by itself."""
        return False

    @property
    def unique_id(self):
        """Return the unique id of the gauge."""
        return self._measure["@id"]

    @property
    def name(self):
        """Return the name of the gauge."""
        station_name = self._station["label"]
        measure_qualifier = self._measure["qualifier"]
        parameter = self._measure["parameterName"]
        return f"{station_name} {parameter} ({measure_qualifier})"

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, "measure-id", self.unique_id)},
            "name": self.name,
            "manufacturer": "https://environment.data.gov.uk/",
            "model": self._measure["parameterName"],
            "via_device": (DOMAIN, "station-id", self._measure["stationReference"]),
            "entry_type": "service",
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def unit_of_measurement(self):
        """Return units for the sensor."""
        unit = self._measure["unit"]
        unit_name = self._measure["unitName"]
        return UNIT_MAPPING.get(unit, unit_name)

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def device_state_attributes(self):
        """Return the sensor specific state attributes."""
        return {ATTR_ATTRIBUTION: self.attribution}

    @property
    def state(self):
        """Return the current sensor value."""
        return self._measure["latestReading"]["value"]
