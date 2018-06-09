"""
Sensor platform to display the current fuel prices at a NSW fuel station.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.nsw_fuel_station/
"""
import datetime
import logging
from typing import Optional

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['nsw-fuel-api-client==1.0.9']

_LOGGER = logging.getLogger(__name__)

ATTR_STATION_ID = 'station_id'
ATTR_STATION_NAME = 'station_name'

CONF_STATION_ID = 'station_id'
CONF_STATION_NAME = 'station_name'
CONF_FUEL_TYPES = 'fuel_types'
CONF_ALLOWED_FUEL_TYPES = ["E10", "U91", "E85", "P95", "P98", "DL",
                           "PDL", "B20", "LPG", "CNG", "EV"]
CONF_DEFAULT_FUEL_TYPES = ["E10", "U91"]
CONF_ATTRIBUTION = "Data provided by NSW Government FuelCheck"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION_ID): cv.positive_int,
    vol.Required(CONF_STATION_NAME): cv.string,
    vol.Optional(CONF_FUEL_TYPES, default=CONF_DEFAULT_FUEL_TYPES):
        vol.All(cv.ensure_list, [vol.In(CONF_ALLOWED_FUEL_TYPES)]),
})

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(hours=1)

NOTIFICATION_ID = 'nsw_fuel_station_notification'
NOTIFICATION_TITLE = 'NSW Fuel Station Sensor Setup'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the NSW Fuel Station sensor."""
    from nsw_fuel import FuelCheckClient

    station_id = config[CONF_STATION_ID]
    station_name = config[CONF_STATION_NAME]
    fuel_types = config[CONF_FUEL_TYPES]

    client = FuelCheckClient()
    station_data = StationPriceData(client, station_id, station_name)
    station_data.update()

    if station_data.error is not None:
        message = (
            'Error: {}. Check the logs for additional information.'
        ).format(station_data.error)

        hass.components.persistent_notification.create(
            message,
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    available_fuel_types = station_data.get_available_fuel_types()

    add_devices([
        StationPriceSensor(station_data, fuel_type)
        for fuel_type in fuel_types
        if fuel_type in available_fuel_types
    ])


class StationPriceData(object):
    """An object to store and fetch the latest data for a given station."""

    def __init__(self, client, station_id: int, station_name: str) -> None:
        """Initialize the sensor."""
        self.station_id = station_id
        self.station_name = station_name

        self._client = client
        self._data = None
        self.error = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the internal data using the API client."""
        from nsw_fuel import FuelCheckError

        try:
            self._data = self._client.get_fuel_prices_for_station(
                self.station_id)
        except FuelCheckError as exc:
            self.error = str(exc)
            _LOGGER.exception(
                'Failed to fetch NSW Fuel station price data', exc_info=exc)

    def for_fuel_type(self, fuel_type: str):
        """Return the price of the given fuel type."""
        if self._data is None:
            return None
        return next((price for price
                     in self._data if price.fuel_type == fuel_type), None)

    def get_available_fuel_types(self):
        """Return the available fuel types for the station."""
        return [price.fuel_type for price in self._data]


class StationPriceSensor(Entity):
    """Implementation of a sensor that reports the fuel price for a station."""

    def __init__(self, station_data: StationPriceData, fuel_type: str):
        """Initialize the sensor."""
        self._station_data = station_data
        self._fuel_type = fuel_type

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return '{} {}'.format(
            self._station_data.station_name, self._fuel_type)

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor."""
        price_info = self._station_data.for_fuel_type(self._fuel_type)
        if price_info:
            return price_info.price

        return None

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes of the device."""
        return {
            ATTR_STATION_ID: self._station_data.station_id,
            ATTR_STATION_NAME: self._station_data.station_name,
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION
        }

    @property
    def unit_of_measurement(self) -> str:
        """Return the units of measurement."""
        return '¢/L'

    def update(self):
        """Update current conditions."""
        self._station_data.update()
