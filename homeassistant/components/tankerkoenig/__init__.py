"""Ask tankerkoenig.de for petrol price information."""
from datetime import timedelta
from functools import partial
import logging

import pytankerkoenig
import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_FUEL_TYPES, CONF_STATIONS, DOMAIN, FUEL_TYPES, NAME
from .sensor import FuelPriceSensor

_LOGGER = logging.getLogger(__name__)

DEFAULT_RADIUS = 2
SCAN_INTERVAL = timedelta(minutes=30)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
                vol.Optional(CONF_FUEL_TYPES, default=FUEL_TYPES): vol.All(
                    cv.ensure_list, [vol.In(FUEL_TYPES)]
                ),
                vol.Inclusive(
                    CONF_LATITUDE,
                    "coordinates",
                    "Latitude and longitude must exist together",
                ): cv.latitude,
                vol.Inclusive(
                    CONF_LONGITUDE,
                    "coordinates",
                    "Latitude and longitude must exist together",
                ): cv.longitude,
                vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): vol.All(
                    cv.positive_int, vol.Range(min=1)
                ),
                vol.Optional(CONF_STATIONS, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set the tankerkoenig component up."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    _LOGGER.debug("Setting up platform")

    tankerkoenig = await hass.async_add_executor_job(
        partial(TankerkoenigData, hass, conf)
    )

    if not tankerkoenig.entity_list:
        _LOGGER.error("Could not find any fuel station to track")
        return False

    hass.data[DOMAIN] = tankerkoenig
    async_track_time_interval(hass, tankerkoenig.update, conf[CONF_SCAN_INTERVAL])

    hass.async_create_task(
        async_load_platform(
            hass, SENSOR_DOMAIN, DOMAIN, discovered=None, hass_config=conf
        )
    )

    return True


class TankerkoenigData:
    """Get the latest data from the API."""

    def __init__(self, hass, conf):
        """Initialize the data object."""
        self._api_key = conf[CONF_API_KEY]
        self._entities = {}
        self._fuel_types = conf[CONF_FUEL_TYPES]

        latitude = conf.get(CONF_LATITUDE, hass.config.latitude)
        longitude = conf.get(CONF_LONGITUDE, hass.config.longitude)
        radius = conf[CONF_RADIUS]

        additional_stations = conf[CONF_STATIONS]

        _LOGGER.debug("Fetching data for (%s,%s) rad: %s", latitude, longitude, radius)

        try:
            data = pytankerkoenig.getNearbyStations(
                self._api_key, latitude, longitude, radius, "all", "dist"
            )
        except pytankerkoenig.customException as err:
            data = {"ok": False, "message": err, "exception": True}
        _LOGGER.debug("Received data: %s", data)
        if not data["ok"]:
            _LOGGER.error(
                "Setup for sensors was unsuccessful. Error occurred while fetching data from tankerkoenig.de: %s",
                data["message"],
            )
            return

        # Add stations found via location + radius
        nearby_stations = data["stations"]
        if not nearby_stations:
            _LOGGER.warning(
                "Could not find any station in range. Try with a bigger radius"
            )
        else:
            for station in data["stations"]:
                self.add_station(station)

        # Add manually specified additional stations
        for station_id in additional_stations:
            try:
                additional_station_data = pytankerkoenig.getStationData(
                    self._api_key, station_id
                )
            except pytankerkoenig.customException as err:
                additional_station_data = {
                    "ok": False,
                    "message": err,
                    "exception": True,
                }

            if not additional_station_data["ok"]:
                _LOGGER.error(
                    "Error when adding station %s:\n %s",
                    station_id,
                    additional_station_data["message"],
                )
                # Clear entity dictionary, so that the platform setup fails / no sensors get loaded in hass
                self._entities = {}
            else:
                self.add_station(additional_station_data["station"])

    @property
    def entity_list(self):
        """Get the list of all entities the platform is monitoring."""

        # Get flat list from the dictionary of lists
        return [
            sensor_entity
            for sublist in self._entities.values()
            for sensor_entity in sublist
        ]

    def update(self, now=None):
        """Get the latest data from tankerkoenig.de."""
        _LOGGER.debug("Fetching new data from tankerkoenig.de")
        entity_list = list(self._entities.keys())
        data = pytankerkoenig.getPriceList(self._api_key, entity_list)

        if data["ok"]:
            _LOGGER.debug("Received data: %s", data)
            for station_id, station_list in self._entities.items():
                for station in station_list:
                    station.new_data(data["prices"].get(station_id))
        else:
            _LOGGER.error(
                "Error fetching data from tankerkoenig.de: %s", data["message"]
            )

    def add_station(self, station: dict):
        """Add fuel station to the entity list."""
        station_id = station["id"]
        if station_id in self._entities.keys():
            _LOGGER.warning(
                "Sensor for station with id %s was already created", station_id
            )
            return

        self._entities[station_id] = []
        _LOGGER.debug(
            "add_station called for station: %s and fuel types: %s",
            station,
            self._fuel_types,
        )
        for fuel in self._fuel_types:
            if fuel in station.keys():
                station_sensor = FuelPriceSensor(
                    fuel, station, f"{NAME}_{station['name']}_{fuel}"
                )
                self._entities[station_id].append(station_sensor)
            else:
                _LOGGER.warning("Station %s does not offer %s fuel", station_id, fuel)
