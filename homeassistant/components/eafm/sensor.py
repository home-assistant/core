"""Support for guages from flood monitoring API."""
from datetime import timedelta
import logging

from aioeafm import get_station
import async_timeout

from homeassistant.const import ATTR_ATTRIBUTION, LENGTH_METERS
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "This uses Environment Agency flood and river level data from the real-time data API"

UNIT_MAPPING = {
    "http://qudt.org/1.1/vocab/unit#Meter": LENGTH_METERS,
}


def get_measures(station_data):
    """Force measure key to always be a list."""
    if "measures" not in station_data:
        return []
    if isinstance(station_data["measures"], dict):
        return [station_data["measures"]]
    return station_data["measures"]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up UK Flood Monitoring Sensors."""
    station_key = config_entry.data["station"]
    session = async_get_clientsession(hass=hass)

    measurements = set()

    async def async_update_data():
        # DataUpdateCoordinator will handle aiohttp ClientErrors and timouts
        async with async_timeout.timeout(30):
            data = await get_station(session, station_key)

        measures = get_measures(data)
        entities = []

        # Look to see if payload contains new measures
        for measure in measures:
            if measure["@id"] in measurements:
                continue

            if "latestReading" not in measure:
                # Don't create a sensor entity for a gauge that isn't available
                continue

            if measure["@id"] not in measurements:
                entities.append(
                    Measurement(hass.data[DOMAIN][station_key], measure["@id"])
                )
                measurements.add(measure["@id"])

        async_add_entities(entities)

        # Turn data.measures into a dict rather than a list so easier for entities to
        # find themselves.
        data["measures"] = {measure["@id"]: measure for measure in measures}

        return data

    hass.data[DOMAIN][station_key] = coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=timedelta(seconds=15 * 60),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()


class Measurement(Entity):
    """A gauge at a flood monitoring station."""

    def __init__(self, coordinator, key):
        """Initialise the gauge with a data instance and station."""
        self.coordinator = coordinator
        self.key = key

    @property
    def station_name(self):
        """Return the station name for the measure."""
        return self.coordinator.data["label"]

    @property
    def station_id(self):
        """Return the station id for the measure."""
        return self.coordinator.data["stationReference"]

    @property
    def qualifier(self):
        """Return the qualifier for the station."""
        return self.coordinator.data["measures"][self.key]["qualifier"]

    @property
    def parameter_name(self):
        """Return the parameter name for the station."""
        return self.coordinator.data["measures"][self.key]["parameterName"]

    @property
    def name(self):
        """Return the name of the gauge."""
        return f"{self.station_name} {self.parameter_name} {self.qualifier}"

    @property
    def should_poll(self) -> bool:
        """Stations are polled as a group - the entity shouldn't poll by itself."""
        return False

    @property
    def unique_id(self):
        """Return the unique id of the gauge."""
        return self.key

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, "measure-id", self.unique_id)},
            "name": self.name,
            "manufacturer": "https://environment.data.gov.uk/",
            "model": self.parameter_name,
            "entry_type": "service",
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        # If sensor goes offline it will no longer contain a reading
        if "latestReading" not in self.coordinator.data["measures"][self.key]:
            return False

        # Sometimes lastestReading key is present but actually a URL rather than a piece of data
        # This is usually because the sensor has been archived
        if not isinstance(
            self.coordinator.data["measures"][self.key]["latestReading"], dict
        ):
            return False

        return True

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def unit_of_measurement(self):
        """Return units for the sensor."""
        measure = self.coordinator.data["measures"][self.key]
        if "unit" not in measure:
            return None
        return UNIT_MAPPING.get(measure["unit"], measure["unitName"])

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
        return self.coordinator.data["measures"][self.key]["latestReading"]["value"]

    async def async_update(self):
        """
        Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()
