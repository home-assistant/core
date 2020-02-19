"""Tankerkoenig sensor integration."""

import logging

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_CLOSED,
    STATE_OPEN,
    STATE_UNKNOWN,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, NAME

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


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the tankerkoenig sensors."""

    if not discovery_info:
        return

    tankerkoenig = hass.data[DOMAIN]

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            return await tankerkoenig.fetch_data()
        except LookupError:
            raise UpdateFailed

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=NAME,
        update_method=async_update_data,
        update_interval=tankerkoenig.update_interval,
    )

    station_list = discovery_info.values()
    entity_list = []
    for station in station_list:
        for fuel in tankerkoenig.fuel_types:
            if fuel not in station.keys():
                _LOGGER.warning(
                    "Station %s does not offer %s fuel", station["id"], fuel
                )
                continue
            sensor = FuelPriceSensor(
                fuel, station, coordinator, f"{NAME}_{station['name']}_{fuel}"
            )
            _LOGGER.debug("Added sensor %s", sensor.name)
            entity_list.append(sensor)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()
    async_add_entities(entity_list)


class FuelPriceSensor(Entity):
    """Contains prices for fuel in a given station."""

    def __init__(self, fuel_type, station, coordinator, name=NAME):
        """Initialize the sensor."""
        self._station = station
        self._station_id = station["id"]
        self._fuel_type = fuel_type
        self._coordinator = coordinator
        self._name = name
        self._latitude = station["lat"]
        self._longitude = station["lng"]
        self._is_open = STATE_OPEN if station["isOpen"] else STATE_CLOSED
        self._city = station["place"]
        self._house_number = station["houseNumber"]
        self._postcode = station["postCode"]
        self._street = station["street"]
        self._price = station[fuel_type]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON

    @property
    def unit_of_measurement(self):
        """Return unit of measurement."""
        return "€"

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies of updates."""
        return False

    @property
    def state(self):
        """Return the state of the device."""
        # key Fuel_type is not available when the fuel station is closed, use "get" instead of "[]" to avoid exceptions
        return self._coordinator.data[self._station_id].get(self._fuel_type)

    @property
    def device_state_attributes(self):
        """Return the attributes of the device."""
        data = self._coordinator.data[self._station_id]
        if data is None or "status" not in data.keys():
            self._is_open = STATE_UNKNOWN
        else:
            self._is_open = STATE_OPEN if data["status"] == "open" else STATE_CLOSED

        attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_BRAND: self._station["brand"],
            ATTR_FUEL_TYPE: self._fuel_type,
            ATTR_STATION_NAME: self._station["name"],
            ATTR_STREET: self._street,
            ATTR_HOUSE_NUMBER: self._house_number,
            ATTR_POSTCODE: self._postcode,
            ATTR_CITY: self._city,
            ATTR_LATITUDE: self._latitude,
            ATTR_LONGITUDE: self._longitude,
            ATTR_IS_OPEN: self._is_open,
        }
        return attrs

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self._coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        self._coordinator.async_remove_listener(self.async_write_ha_state)

    async def async_update(self):
        """Update the entity."""
        await self._coordinator.async_request_refresh()
