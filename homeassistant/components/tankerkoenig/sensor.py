"""Tankerkoenig sensor integration."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TankerkoenigCoordinatorEntity, TankerkoenigDataUpdateCoordinator
from .const import (
    ATTR_BRAND,
    ATTR_CITY,
    ATTR_FUEL_TYPE,
    ATTR_HOUSE_NUMBER,
    ATTR_POSTCODE,
    ATTR_STATION_NAME,
    ATTR_STREET,
    ATTRIBUTION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the tankerkoenig sensors."""

    coordinator: TankerkoenigDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

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


class FuelPriceSensor(TankerkoenigCoordinatorEntity, SensorEntity):
    """Contains prices for fuel in a given station."""

    _attr_attribution = ATTRIBUTION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_icon = "mdi:gas-station"

    def __init__(self, fuel_type, station, coordinator, show_on_map):
        """Initialize the sensor."""
        super().__init__(coordinator, station)
        self._station_id = station["id"]
        self._fuel_type = fuel_type
        self._attr_translation_key = fuel_type
        self._attr_unique_id = f"{station['id']}_{fuel_type}"
        attrs = {
            ATTR_BRAND: station["brand"],
            ATTR_FUEL_TYPE: fuel_type,
            ATTR_STATION_NAME: station["name"],
            ATTR_STREET: station["street"],
            ATTR_HOUSE_NUMBER: station["houseNumber"],
            ATTR_POSTCODE: station["postCode"],
            ATTR_CITY: station["place"],
        }

        if show_on_map:
            attrs[ATTR_LATITUDE] = station["lat"]
            attrs[ATTR_LONGITUDE] = station["lng"]
        self._attr_extra_state_attributes = attrs

    @property
    def native_value(self):
        """Return the state of the device."""
        # key Fuel_type is not available when the fuel station is closed,
        # use "get" instead of "[]" to avoid exceptions
        return self.coordinator.data[self._station_id].get(self._fuel_type)
