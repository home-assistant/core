"""Support for the Airly service."""

import asyncio
from datetime import timedelta
import logging

from airly import Airly
from airly.exceptions import AirlyError
import async_timeout

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import CONF_LANGUAGE, NO_AIRLY_SENSORS

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by Airly"

ATTR_CAQI = "CAQI"
ATTR_CAQI_ADVICE = "advice"
ATTR_CAQI_DESCRIPTION = "DESCRIPTION"
ATTR_CAQI_LEVEL = "level"
ATTR_ICON = "icon"
ATTR_LABEL = "label"
ATTR_LIMIT = "limit"
ATTR_PERCENT = "percent"
ATTR_PM1 = "PM1"
ATTR_PM10 = "PM10"
ATTR_PM10_LIMIT = "PM10_LIMIT"
ATTR_PM10_PERCENT = "PM10_PERCENT"
ATTR_PM25 = "PM25"
ATTR_PM25_LIMIT = "PM25_LIMIT"
ATTR_PM25_PERCENT = "PM25_PERCENT"
ATTR_HUMIDITY = "HUMIDITY"
ATTR_PRESSURE = "PRESSURE"
ATTR_TEMPERATURE = "TEMPERATURE"
ATTR_UNIT = "unit"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)

HUMI_PERCENT = "%"
VOLUME_MICROGRAMS_PER_CUBIC_METER = "µg/m³"

AVAILABLE_CONDITIONS = [
    ATTR_CAQI,
    ATTR_CAQI_DESCRIPTION,
    ATTR_PM1,
    ATTR_PM10,
    ATTR_PM25,
    ATTR_HUMIDITY,
    ATTR_PRESSURE,
    ATTR_TEMPERATURE,
]

SENSOR_TYPES = {
    ATTR_CAQI: {ATTR_ICON: None, ATTR_LABEL: ATTR_CAQI, ATTR_UNIT: None},
    ATTR_CAQI_DESCRIPTION: {
        ATTR_ICON: "mdi:card-text-outline",
        ATTR_LABEL: ATTR_CAQI_DESCRIPTION.capitalize(),
        ATTR_UNIT: None,
    },
    ATTR_PM1: {
        ATTR_ICON: "mdi:blur",
        ATTR_LABEL: ATTR_PM1,
        ATTR_UNIT: VOLUME_MICROGRAMS_PER_CUBIC_METER,
    },
    ATTR_PM10: {
        ATTR_ICON: "mdi:blur",
        ATTR_LABEL: ATTR_PM10,
        ATTR_UNIT: VOLUME_MICROGRAMS_PER_CUBIC_METER,
    },
    ATTR_PM25: {
        ATTR_ICON: "mdi:blur",
        ATTR_LABEL: "PM2.5",
        ATTR_UNIT: VOLUME_MICROGRAMS_PER_CUBIC_METER,
    },
    ATTR_HUMIDITY: {
        ATTR_ICON: "mdi:water-percent",
        ATTR_LABEL: ATTR_HUMIDITY.capitalize(),
        ATTR_UNIT: HUMI_PERCENT,
    },
    ATTR_PRESSURE: {
        ATTR_ICON: "mdi:gauge",
        ATTR_LABEL: ATTR_PRESSURE.capitalize(),
        ATTR_UNIT: PRESSURE_HPA,
    },
    ATTR_TEMPERATURE: {
        ATTR_ICON: "mdi:thermometer",
        ATTR_LABEL: ATTR_TEMPERATURE.capitalize(),
        ATTR_UNIT: TEMP_CELSIUS,
    },
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a Airly entities from a config_entry."""
    api_key = config_entry.data[CONF_API_KEY]
    name = config_entry.data[CONF_NAME]
    latitude = config_entry.data[CONF_LATITUDE]
    longitude = config_entry.data[CONF_LONGITUDE]
    language = config_entry.data[CONF_LANGUAGE]
    scan_interval = DEFAULT_SCAN_INTERVAL
    _LOGGER.debug("Using latitude and longitude: %s, %s", latitude, longitude)

    websession = async_get_clientsession(hass)

    data = AirlyData(
        websession, api_key, latitude, longitude, language, scan_interval=scan_interval
    )

    await data.async_update()

    sensors = []
    for condition in AVAILABLE_CONDITIONS:
        sensors.append(AirlySensor(data, name, condition))
    async_add_entities(sensors, True)


class AirlySensor(Entity):
    """Define an Airly sensor."""

    def __init__(self, airly, name, kind):
        """Initialize."""
        self.airly = airly
        self.data = airly.data
        self._name = name
        self.kind = kind
        self._state = None
        self._device_class = None
        self._icon = None
        self._unit_of_measurement = None
        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def name(self):
        """Return the name."""
        return f"{self._name} {SENSOR_TYPES[self.kind][ATTR_LABEL]}"

    @property
    def state(self):
        """Return the state."""
        self._state = self.data[self.kind]
        if self.kind in [ATTR_PM1, ATTR_PM25, ATTR_PM10, ATTR_PRESSURE, ATTR_CAQI]:
            self._state = round(self._state)
        if self.kind in [ATTR_TEMPERATURE, ATTR_HUMIDITY]:
            self._state = round(self._state, 1)
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self.kind == ATTR_CAQI_DESCRIPTION:
            self._attrs.update({ATTR_CAQI_ADVICE: self.data[ATTR_CAQI_ADVICE]})
        if self.kind == ATTR_CAQI:
            self._attrs.update({ATTR_CAQI_LEVEL: self.data[ATTR_CAQI_LEVEL]})
        if self.kind == ATTR_PM25:
            self._attrs.update({ATTR_LIMIT: self.data[ATTR_PM25_LIMIT]})
            self._attrs.update({ATTR_PERCENT: round(self.data[ATTR_PM25_PERCENT])})
        if self.kind == ATTR_PM10:
            self._attrs.update({ATTR_LIMIT: self.data[ATTR_PM10_LIMIT]})
            self._attrs.update({ATTR_PERCENT: round(self.data[ATTR_PM10_PERCENT])})
        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        if self.kind == ATTR_CAQI:
            if self._state <= 25:
                self._icon = "mdi:emoticon-excited"
            elif self._state <= 50:
                self._icon = "mdi:emoticon-happy"
            elif self._state <= 75:
                self._icon = "mdi:emoticon-neutral"
            elif self._state <= 100:
                self._icon = "mdi:emoticon-sad"
            elif self._state > 100:
                self._icon = "mdi:emoticon-dead"
        else:
            self._icon = SENSOR_TYPES[self.kind][ATTR_ICON]
        return self._icon

    @property
    def device_class(self):
        """Return the device_class."""
        if self.kind == ATTR_TEMPERATURE:
            self._device_class = DEVICE_CLASS_TEMPERATURE
        elif self.kind == ATTR_HUMIDITY:
            self._device_class = DEVICE_CLASS_HUMIDITY
        elif self.kind == ATTR_PRESSURE:
            self._device_class = DEVICE_CLASS_PRESSURE
        return self._device_class

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self.airly.latitude}-{self.airly.longitude}-{self.kind.lower()}"

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SENSOR_TYPES[self.kind][ATTR_UNIT]

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self.airly.data)

    async def async_update(self):
        """Get the data from Airly."""
        await self.airly.async_update()

        if not self.airly.data:
            return


class AirlyData:
    """Define an object to hold sensor data."""

    def __init__(self, client, api_key, latitude, longitude, language, **kwargs):
        """Initialize."""
        self.client = client
        self.latitude = latitude
        self.longitude = longitude
        self.language = language
        self.api_key = api_key
        self.data = {}

        self.async_update = Throttle(kwargs[CONF_SCAN_INTERVAL])(self._async_update)

    async def _async_update(self):
        """Update Airly data."""

        try:
            with async_timeout.timeout(10):
                airly = Airly(self.api_key, self.client, language=self.language)
                measurements = airly.create_measurements_session_point(
                    self.latitude, self.longitude
                )

                await measurements.update()
            values = measurements.current["values"]
            standards = measurements.current["standards"]
            index = measurements.current["indexes"][0]

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
