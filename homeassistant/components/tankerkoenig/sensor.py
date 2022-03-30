"""Tankerkoenig sensor integration."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ID,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CURRENCY_EURO,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TankerkoenigDataUpdateCoordinator
from .const import DOMAIN, FUEL_TYPES

_LOGGER = logging.getLogger(__name__)

ATTR_BRAND = "brand"
ATTR_CITY = "city"
ATTR_FUEL_TYPE = "fuel_type"
ATTR_HOUSE_NUMBER = "house_number"
ATTR_IS_OPEN = "is_open"
ATTR_POSTCODE = "postcode"
ATTR_STATION_NAME = "station_name"
ATTR_STREET = "street"
ATTRIBUTION = "Data provided by https://creativecommons.tankerkoenig.de"

ICON = "mdi:gas-station"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the tankerkoenig sensors."""

    coordinator: TankerkoenigDataUpdateCoordinator = hass.data[DOMAIN][entry.unique_id]

    stations = coordinator.stations.values()
    entities = []
    for station in stations:
        for fuel in coordinator.fuel_types:
            if fuel not in station:
                _LOGGER.warning(
                    "Station %s does not offer %s fuel", station["id"], fuel
                )
                continue
            sensor = FuelPriceSensor(
                fuel,
                station,
                coordinator,
                coordinator.show_on_map,
            )
            entities.append(sensor)
    _LOGGER.debug("Added sensors %s", entities)

    async_add_entities(entities)


class FuelPriceSensor(CoordinatorEntity, SensorEntity):
    """Contains prices for fuel in a given station."""

    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, fuel_type, station, coordinator, show_on_map):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._station = station
        self._station_id = station["id"]
        self._fuel_type = fuel_type
        self._latitude = station["lat"]
        self._longitude = station["lng"]
        self._city = station["place"]
        self._house_number = station["houseNumber"]
        self._postcode = station["postCode"]
        self._street = station["street"]
        self._brand = self._station["brand"]
        self._price = station[fuel_type]
        self._show_on_map = show_on_map

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._brand} {self._street} {self._house_number} {FUEL_TYPES[self._fuel_type]}"

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON

    @property
    def native_unit_of_measurement(self):
        """Return unit of measurement."""
        return CURRENCY_EURO

    @property
    def native_value(self):
        """Return the state of the device."""
        # key Fuel_type is not available when the fuel station is closed, use "get" instead of "[]" to avoid exceptions
        return self.coordinator.data[self._station_id].get(self._fuel_type)

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this entity."""
        return f"{self._station_id}_{self._fuel_type}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info."""
        return DeviceInfo(
            identifiers={(ATTR_ID, self._station_id)},
            name=f"{self._brand} {self._street} {self._house_number}",
            model=self._brand,
            configuration_url="https://www.tankerkoenig.de",
        )

    @property
    def extra_state_attributes(self):
        """Return the attributes of the device."""
        data = self.coordinator.data[self._station_id]

        attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_BRAND: self._station["brand"],
            ATTR_FUEL_TYPE: self._fuel_type,
            ATTR_STATION_NAME: self._station["name"],
            ATTR_STREET: self._street,
            ATTR_HOUSE_NUMBER: self._house_number,
            ATTR_POSTCODE: self._postcode,
            ATTR_CITY: self._city,
        }

        if self._show_on_map:
            attrs[ATTR_LATITUDE] = self._latitude
            attrs[ATTR_LONGITUDE] = self._longitude

        if data is not None and "status" in data:
            attrs[ATTR_IS_OPEN] = data["status"] == "open"
        return attrs
