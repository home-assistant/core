"""The Airly component."""
import asyncio
from datetime import timedelta
import logging

from aiohttp.client_exceptions import ClientConnectorError
from airly import Airly
from airly.exceptions import AirlyError
import async_timeout

from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import Config, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import Throttle

from .const import (
    ATTR_API_ADVICE,
    ATTR_API_CAQI,
    ATTR_API_CAQI_DESCRIPTION,
    ATTR_API_CAQI_LEVEL,
    DATA_CLIENT,
    DOMAIN,
    NO_AIRLY_SENSORS,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured Airly."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}
    return True


async def async_setup_entry(hass, config_entry):
    """Set up Airly as config entry."""
    api_key = config_entry.data[CONF_API_KEY]
    latitude = config_entry.data[CONF_LATITUDE]
    longitude = config_entry.data[CONF_LONGITUDE]

    # For backwards compat, set unique ID
    if config_entry.unique_id is None:
        hass.config_entries.async_update_entry(
            config_entry, unique_id=f"{latitude}-{longitude}"
        )

    websession = async_get_clientsession(hass)

    airly = AirlyData(websession, api_key, latitude, longitude)

    await airly.async_update()

    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = airly

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "air_quality")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    hass.data[DOMAIN][DATA_CLIENT].pop(config_entry.entry_id)
    await hass.config_entries.async_forward_entry_unload(config_entry, "air_quality")
    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    return True


class AirlyData:
    """Define an object to hold Airly data."""

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
            with async_timeout.timeout(20):
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
        except asyncio.TimeoutError:
            _LOGGER.error("Asyncio Timeout Error")
        except (ValueError, AirlyError, ClientConnectorError) as error:
            _LOGGER.error(error)
            self.data = {}
