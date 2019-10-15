"""The Airly component."""
import asyncio
import logging
from datetime import timedelta

import async_timeout
from aiohttp.client_exceptions import ClientConnectorError
from airly import Airly
from airly.exceptions import AirlyError

from homeassistant.core import Config, HomeAssistant

# from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import Throttle

from .const import (
    ATTR_API_ADVICE,
    ATTR_API_CAQI,
    ATTR_API_CAQI_DESCRIPTION,
    ATTR_API_CAQI_LEVEL,
    # ATTR_API_PM10,
    # ATTR_API_PM10_LIMIT,
    # ATTR_API_PM10_PERCENT,
    # ATTR_API_PM25,
    # ATTR_API_PM25_LIMIT,
    # ATTR_API_PM25_PERCENT,
    NO_AIRLY_SENSORS,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)


# def setup(hass, config_entry):
#     """Set up the Airly component."""
#     api_key = config_entry.data[CONF_API_KEY]
#     name = config_entry.data[CONF_NAME]
#     latitude = config_entry.data[CONF_LATITUDE]
#     longitude = config_entry.data[CONF_LONGITUDE]

#     websession = async_get_clientsession(hass)

#     data = AirlyData(websession, api_key, latitude, longitude)


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured Airly."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up Airly as config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "air_quality")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(config_entry, "air_quality")
    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    return True


class AirlyData:
    """Define an object to hold sensor data."""

    def __init__(self, session, api_key, latitude, longitude):
        """Initialize."""
        self.latitude = latitude
        self.longitude = longitude
        self.airly = Airly(api_key, session)
        self.data = {}

    @Throttle(DEFAULT_SCAN_INTERVAL)
    async def async_update(self):
        """Update Airly data."""

        try:
            with async_timeout.timeout(10):
                measurements = self.airly.create_measurements_session_point(
                    self.latitude, self.longitude
                )
                await measurements.update()

            values = measurements.current["values"]
            index = measurements.current["indexes"][0]
            standards = measurements.current["standards"]

            if index["description"] == NO_AIRLY_SENSORS:
                _LOGGER.error("Can't retrieve data: no Airly sensors in this area")
                return
            for value in values:
                self.data[value["name"]] = value["value"]
            for standard in standards:
                self.data[f"{standard['pollutant']}_LIMIT"] = standard["limit"]
                self.data[f"{standard['pollutant']}_PERCENT"] = standard["percent"]
            self.data[ATTR_API_CAQI] = index["value"]
            self.data[ATTR_API_CAQI_LEVEL] = index["level"].lower().replace("_", " ")
            self.data[ATTR_API_CAQI_DESCRIPTION] = index["description"]
            self.data[ATTR_API_ADVICE] = index["advice"]
            _LOGGER.debug("Data retrieved from Airly")
        except (
            ValueError,
            AirlyError,
            asyncio.TimeoutError,
            ClientConnectorError,
        ) as error:
            _LOGGER.error(error)
            self.data = {}
