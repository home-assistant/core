"""Ask tankerkoenig.de for petrol price information."""
from datetime import timedelta
import logging
from uuid import UUID

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
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

from .const import CONF_FUEL_TYPES, CONF_STATIONS, DOMAIN, FUEL_TYPES

_LOGGER = logging.getLogger(__name__)

DEFAULT_RADIUS = 2
DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)


def uuid4_string(value):
    """Validate a v4 UUID in string format."""
    try:
        result = UUID(value, version=4)
    except (ValueError, AttributeError, TypeError) as error:
        raise vol.Invalid("Invalid Version4 UUID", error_message=str(error))

    if str(result) != value.lower():
        # UUID() will create a uuid4 if input is invalid
        raise vol.Invalid("Invalid Version4 UUID")

    return str(result)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): uuid4_string,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
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
                    cv.ensure_list, [uuid4_string]
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

    _LOGGER.debug("Setting up integration")

    tankerkoenig = TankerkoenigData(hass, conf)

    latitude = conf.get(CONF_LATITUDE, hass.config.latitude)
    longitude = conf.get(CONF_LONGITUDE, hass.config.longitude)
    radius = conf[CONF_RADIUS]
    additional_stations = conf[CONF_STATIONS]

    setup_ok = await hass.async_add_executor_job(
        tankerkoenig.setup, latitude, longitude, radius, additional_stations
    )
    if not setup_ok:
        _LOGGER.error("Could not setup integration")
        return False

    hass.data[DOMAIN] = tankerkoenig

    hass.async_create_task(
        async_load_platform(
            hass,
            SENSOR_DOMAIN,
            DOMAIN,
            discovered=tankerkoenig.stations,
            hass_config=conf,
        )
    )

    return True


class TankerkoenigData:
    """Get the latest data from the API."""

    def __init__(self, hass, conf):
        """Initialize the data object."""
        self._api_key = conf[CONF_API_KEY]
        self.stations = {}
        self.fuel_types = conf[CONF_FUEL_TYPES]
        self.update_interval = conf[CONF_SCAN_INTERVAL]
        self._hass = hass

    def setup(self, latitude, longitude, radius, additional_stations):
        """Set up the tankerkoenig API.

        Read the initial data from the server, to initialize the list of fuel stations to monitor.
        """
        _LOGGER.debug("Fetching data for (%s, %s) rad: %s", latitude, longitude, radius)
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
            return False

        # Add stations found via location + radius
        nearby_stations = data["stations"]
        if not nearby_stations:
            if not additional_stations:
                _LOGGER.error(
                    "Could not find any station in range."
                    "Try with a bigger radius or manually specify stations in additional_stations"
                )
                return False
            _LOGGER.warning(
                "Could not find any station in range. Will only use manually specified stations"
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
                return False
            self.add_station(additional_station_data["station"])
        return True

    async def fetch_data(self):
        """Get the latest data from tankerkoenig.de."""
        _LOGGER.debug("Fetching new data from tankerkoenig.de")
        station_ids = list(self.stations)
        data = await self._hass.async_add_executor_job(
            pytankerkoenig.getPriceList, self._api_key, station_ids
        )

        if data["ok"]:
            _LOGGER.debug("Received data: %s", data)
            if "prices" not in data:
                _LOGGER.error("Did not receive price information from tankerkoenig.de")
                raise TankerkoenigError("No prices in data")
        else:
            _LOGGER.error(
                "Error fetching data from tankerkoenig.de: %s", data["message"]
            )
            raise TankerkoenigError(data["message"])
        return data["prices"]

    def add_station(self, station: dict):
        """Add fuel station to the entity list."""
        station_id = station["id"]
        if station_id in self.stations:
            _LOGGER.warning(
                "Sensor for station with id %s was already created", station_id
            )
            return

        self.stations[station_id] = station
        _LOGGER.debug("add_station called for station: %s", station)


class TankerkoenigError(HomeAssistantError):
    """An error occurred while contacting tankerkoenig.de."""
