"""Support for the Foobot indoor air quality monitor."""
import asyncio
from datetime import timedelta
import logging

import aiohttp
from foobot_async import FoobotClient
import voluptuous as vol

from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_TIME,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_TOKEN,
    CONF_USERNAME,
    TEMP_CELSIUS,
    TIME_SECONDS,
    UNIT_PERCENTAGE,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_HUMIDITY = "humidity"
ATTR_PM2_5 = "PM2.5"
ATTR_CARBON_DIOXIDE = "CO2"
ATTR_VOLATILE_ORGANIC_COMPOUNDS = "VOC"
ATTR_FOOBOT_INDEX = "index"

SENSOR_TYPES = {
    "time": [ATTR_TIME, TIME_SECONDS],
    "pm": [ATTR_PM2_5, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, "mdi:cloud"],
    "tmp": [ATTR_TEMPERATURE, TEMP_CELSIUS, "mdi:thermometer"],
    "hum": [ATTR_HUMIDITY, UNIT_PERCENTAGE, "mdi:water-percent"],
    "co2": [ATTR_CARBON_DIOXIDE, CONCENTRATION_PARTS_PER_MILLION, "mdi:molecule-co2"],
    "voc": [
        ATTR_VOLATILE_ORGANIC_COMPOUNDS,
        CONCENTRATION_PARTS_PER_BILLION,
        "mdi:cloud",
    ],
    "allpollu": [ATTR_FOOBOT_INDEX, UNIT_PERCENTAGE, "mdi:percent"],
}

SCAN_INTERVAL = timedelta(minutes=10)
PARALLEL_UPDATES = 1

TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_TOKEN): cv.string, vol.Required(CONF_USERNAME): cv.string}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the devices associated with the account."""
    token = config.get(CONF_TOKEN)
    username = config.get(CONF_USERNAME)

    client = FoobotClient(
        token, username, async_get_clientsession(hass), timeout=TIMEOUT
    )
    dev = []
    try:
        devices = await client.get_devices()
        _LOGGER.debug("The following devices were found: %s", devices)
        for device in devices:
            foobot_data = FoobotData(client, device["uuid"])
            for sensor_type in SENSOR_TYPES:
                if sensor_type == "time":
                    continue
                foobot_sensor = FoobotSensor(foobot_data, device, sensor_type)
                dev.append(foobot_sensor)
    except (
        aiohttp.client_exceptions.ClientConnectorError,
        asyncio.TimeoutError,
        FoobotClient.TooManyRequests,
        FoobotClient.InternalError,
    ) as err:
        _LOGGER.exception("Failed to connect to foobot servers")
        raise PlatformNotReady from err
    except FoobotClient.ClientError:
        _LOGGER.error("Failed to fetch data from foobot servers")
        return
    async_add_entities(dev, True)


class FoobotSensor(Entity):
    """Implementation of a Foobot sensor."""

    def __init__(self, data, device, sensor_type):
        """Initialize the sensor."""
        self._uuid = device["uuid"]
        self.foobot_data = data
        self._name = f"Foobot {device['name']} {SENSOR_TYPES[sensor_type][0]}"
        self.type = sensor_type
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return SENSOR_TYPES[self.type][2]

    @property
    def state(self):
        """Return the state of the device."""
        try:
            data = self.foobot_data.data[self.type]
        except (KeyError, TypeError):
            data = None
        return data

    @property
    def unique_id(self):
        """Return the unique id of this entity."""
        return f"{self._uuid}_{self.type}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    async def async_update(self):
        """Get the latest data."""
        await self.foobot_data.async_update()


class FoobotData(Entity):
    """Get data from Foobot API."""

    def __init__(self, client, uuid):
        """Initialize the data object."""
        self._client = client
        self._uuid = uuid
        self.data = {}

    @Throttle(SCAN_INTERVAL)
    async def async_update(self):
        """Get the data from Foobot API."""
        interval = SCAN_INTERVAL.total_seconds()
        try:
            response = await self._client.get_last_data(
                self._uuid, interval, interval + 1
            )
        except (
            aiohttp.client_exceptions.ClientConnectorError,
            asyncio.TimeoutError,
            self._client.TooManyRequests,
            self._client.InternalError,
        ):
            _LOGGER.debug("Couldn't fetch data")
            return False
        _LOGGER.debug("The data response is: %s", response)
        self.data = {k: round(v, 1) for k, v in response[0].items()}
        return True
