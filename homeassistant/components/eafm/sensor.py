"""Support for gauges from flood monitoring API."""
import asyncio
from datetime import timedelta
import logging

from aioeafm import get_station

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UNIT_MAPPING = {
    "http://qudt.org/1.1/vocab/unit#Meter": UnitOfLength.METERS,
}


def get_measures(station_data):
    """Force measure key to always be a list."""
    if "measures" not in station_data:
        return []
    if isinstance(station_data["measures"], dict):
        return [station_data["measures"]]
    return station_data["measures"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UK Flood Monitoring Sensors."""
    station_key = config_entry.data["station"]
    session = async_get_clientsession(hass=hass)

    measurements = set()

    async def async_update_data():
        # DataUpdateCoordinator will handle aiohttp ClientErrors and timeouts
        async with asyncio.timeout(30):
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

            entities.append(Measurement(hass.data[DOMAIN][station_key], measure["@id"]))
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


class Measurement(CoordinatorEntity, SensorEntity):
    """A gauge at a flood monitoring station."""

    _attr_attribution = (
        "This uses Environment Agency flood and river level data "
        "from the real-time data API"
    )
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator, key):
        """Initialise the gauge with a data instance and station."""
        super().__init__(coordinator)
        self.key = key
        self._attr_unique_id = key

    @property
    def station_name(self):
        """Return the station name for the measure."""
        return self.coordinator.data["label"]

    @property
    def station_id(self):
        """Return the station id for the measure."""
        return self.coordinator.data["measures"][self.key]["stationReference"]

    @property
    def qualifier(self):
        """Return the qualifier for the station."""
        return self.coordinator.data["measures"][self.key]["qualifier"]

    @property
    def parameter_name(self):
        """Return the parameter name for the station."""
        return self.coordinator.data["measures"][self.key]["parameterName"]

    @property
    def device_info(self):
        """Return the device info."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, "measure-id", self.station_id)},
            manufacturer="https://environment.data.gov.uk/",
            model=self.parameter_name,
            name=f"{self.station_name} {self.parameter_name} {self.qualifier}",
        )

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

    @property
    def native_unit_of_measurement(self):
        """Return units for the sensor."""
        measure = self.coordinator.data["measures"][self.key]
        if "unit" not in measure:
            return None
        return UNIT_MAPPING.get(measure["unit"], measure["unitName"])

    @property
    def native_value(self):
        """Return the current sensor value."""
        return self.coordinator.data["measures"][self.key]["latestReading"]["value"]
