"""Support for the Airly service."""
import asyncio
import logging
from datetime import timedelta

import async_timeout
from airly import Airly
from airly.exceptions import AirlyError

from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
)
from homeassistant.components.air_quality import (
    AirQualityEntity,
    ATTR_PM_10,
    ATTR_PM_2_5,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import Throttle

from .const import CONF_LANGUAGE, NO_AIRLY_SENSORS

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by Airly"

ATTR_CAQI = "CAQI"
ATTR_CAQI_ADVICE = "advice"
ATTR_CAQI_DESCRIPTION = "DESCRIPTION"
ATTR_CAQI_LEVEL = "air quality index level"
ATTR_PM_10_LIMIT = "PM10_LIMIT"
ATTR_PM_10_PERCENT = "PM10_PERCENT"
ATTR_PM_2_5_LIMIT = "PM25_LIMIT"
ATTR_PM_2_5_PERCENT = "PM25_PERCENT"
LABEL_PM_2_5_LIMIT = f"{ATTR_PM_2_5} limit"
LABEL_PM_2_5_PERCENT = f"{ATTR_PM_2_5} percent of limit"
LABEL_PM_10_LIMIT = f"{ATTR_PM_10} limit"
LABEL_PM_10_PERCENT = f"{ATTR_PM_10} percent of limit"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a Airly entities from a config_entry."""
    api_key = config_entry.data[CONF_API_KEY]
    name = config_entry.data[CONF_NAME]
    latitude = config_entry.data[CONF_LATITUDE]
    longitude = config_entry.data[CONF_LONGITUDE]
    language = config_entry.data[CONF_LANGUAGE]
    scan_interval = DEFAULT_SCAN_INTERVAL

    websession = async_get_clientsession(hass)

    data = AirlyData(
        websession, api_key, latitude, longitude, language, scan_interval=scan_interval
    )

    await data.async_update()

    async_add_entities([AirlyAirQuality(data, name)], True)


def round_state(func):
    """Round state."""

    def _decorator(self):
        res = func(self)
        if isinstance(res, float):
            return round(res)
        return res

    return _decorator


class AirlyAirQuality(AirQualityEntity):
    """Define an Airly air_quality."""

    def __init__(self, airly, name):
        """Initialize."""
        self.airly = airly
        self.data = airly.data
        self._name = name
        self._pm_2_5 = None
        self._pm_10 = None
        self._caqi = None
        self._icon = "mdi:blur"
        self._attrs = {}

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    @round_state
    def air_quality_index(self):
        """Return the air quality index."""
        return self._caqi

    @property
    @round_state
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self._pm_2_5

    @property
    @round_state
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self._pm_10

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def state(self):
        """Return the CAQI description."""
        return self.data[ATTR_CAQI_DESCRIPTION]

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self.airly.latitude}-{self.airly.longitude}"

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self.airly.data)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        self._attrs[ATTR_CAQI_ADVICE] = self.data[ATTR_CAQI_ADVICE]
        self._attrs[ATTR_CAQI_LEVEL] = self.data[ATTR_CAQI_LEVEL]
        self._attrs[LABEL_PM_2_5_LIMIT] = self.data[ATTR_PM_2_5_LIMIT]
        self._attrs[LABEL_PM_2_5_PERCENT] = round(self.data[ATTR_PM_2_5_PERCENT])
        self._attrs[LABEL_PM_10_LIMIT] = self.data[ATTR_PM_10_LIMIT]
        self._attrs[LABEL_PM_10_PERCENT] = round(self.data[ATTR_PM_10_PERCENT])
        return self._attrs

    async def async_update(self):
        """Get the data from Airly."""
        await self.airly.async_update()

        self._pm_10 = self.data["PM10"]
        self._pm_2_5 = self.data["PM25"]
        self._caqi = self.data[ATTR_CAQI]


class AirlyData:
    """Define an object to hold sensor data."""

    def __init__(self, session, api_key, latitude, longitude, language, **kwargs):
        """Initialize."""
        self.session = session
        self.latitude = latitude
        self.longitude = longitude
        self.language = language
        self.api_key = api_key
        self.airly = Airly(self.api_key, self.session, language=self.language)
        self.data = {}

        self.async_update = Throttle(kwargs[CONF_SCAN_INTERVAL])(self._async_update)

    async def _async_update(self):
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

            if index["description"] != NO_AIRLY_SENSORS:
                for value in values:
                    self.data[value["name"]] = value["value"]
                for standard in standards:
                    self.data[f"{standard['pollutant']}_LIMIT"] = standard["limit"]
                    self.data[f"{standard['pollutant']}_PERCENT"] = standard["percent"]
                self.data[ATTR_CAQI] = index["value"]
                self.data[ATTR_CAQI_LEVEL] = index["level"].lower().replace("_", " ")
                self.data[ATTR_CAQI_DESCRIPTION] = index["description"]
                self.data[ATTR_CAQI_ADVICE] = index["advice"]
                _LOGGER.debug("Data retrieved from Airly")
            else:
                _LOGGER.error("Can't retrieve data: no Airly sensors in this area")
        except (ValueError, AirlyError, asyncio.TimeoutError) as error:
            _LOGGER.error(error)
            self.data = {}
