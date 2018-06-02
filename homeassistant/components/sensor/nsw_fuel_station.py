"""
Component to display the current fuel prices at a NSW fuel station.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/nsw_fuel_station/
"""
import datetime
from typing import Optional
import voluptuous as vol

from homeassistant.components.light import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['nsw-fuel-api-client==1.0.7']

CONF_STATION_ID = 'station_id'
CONF_STATION_NAME = 'station_name'
CONF_FUEL_TYPES = 'fuel_types'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION_ID): cv.positive_int,
    vol.Required(CONF_STATION_NAME): cv.string,
    vol.Required(CONF_FUEL_TYPES, default=[]): vol.All(
        cv.ensure_list, [cv.string]),
})

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(hours=1)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the NSW Fuel Station component."""
    from nsw_fuel import FuelCheckClient

    station_id = config[CONF_STATION_ID]
    station_name = config[CONF_STATION_NAME]
    fuel_types = config[CONF_FUEL_TYPES]

    client = FuelCheckClient()
    station_data = StationPriceData(client, station_id, station_name)
    station_data.update()

    add_devices([
        StationPriceSensor(station_data, fuel_type)
        for fuel_type in fuel_types
    ])
    return True


class StationPriceData(object):
    """An object to store and fetch the latest data for a given station."""

    def __init__(self, client, station_id: int, station_name: str) -> None:
        """Initialize the sensor."""
        self.station_id = station_id
        self.station_name = station_name

        self._client = client
        self._data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the internal data using the API client."""
        self._data = self._client.get_fuel_prices_for_station(self.station_id)

    def for_fuel_type(self, fuel_type: str):
        """Return the price of the given fuel type."""
        if self._data is None:
            return None
        return next((x for x in self._data if x.fuel_type == fuel_type), None)


class StationPriceSensor(Entity):
    """Implementation of a sensor that reports the fuel price for a station."""

    def __init__(self, station_data: StationPriceData, fuel_type: str):
        """Initialize the sensor."""
        self._station_data = station_data
        self._fuel_type = fuel_type

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return 'NSW Fuel Station {} {}'.format(
            self._station_data.station_name, self._fuel_type)

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor."""
        price_info = self._station_data.for_fuel_type(self._fuel_type)
        if price_info:
            return price_info.price

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes of the device."""
        attr = {}
        attr['Station ID'] = self._station_data.station_id
        attr['Station Name'] = self._station_data.station_name
        return attr

    @property
    def unit_of_measurement(self) -> str:
        """Return the units of measurement."""
        return '¢/L'

    def update(self):
        """Update current conditions."""
        self._station_data.update()
