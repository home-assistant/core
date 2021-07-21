"""
Support for EBox.

Get data from 'My Usage Page' page: https://client.ebox.ca/myusage
"""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import NamedTuple

from pyebox import EboxClient
from pyebox.client import PyEboxError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    DATA_GIGABITS,
    PERCENTAGE,
    TIME_DAYS,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

PRICE = "CAD"

DEFAULT_NAME = "EBox"

REQUESTS_TIMEOUT = 15
SCAN_INTERVAL = timedelta(minutes=15)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)


class EboxSensorMetadata(NamedTuple):
    """Metadata for an individual ebox sensor."""

    name: str
    unit_of_measurement: str
    icon: str


SENSOR_TYPES = {
    "usage": EboxSensorMetadata(
        "Usage",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
    ),
    "balance": EboxSensorMetadata(
        "Balance",
        unit_of_measurement=PRICE,
        icon="mdi:cash-usd",
    ),
    "limit": EboxSensorMetadata(
        "Data limit",
        unit_of_measurement=DATA_GIGABITS,
        icon="mdi:download",
    ),
    "days_left": EboxSensorMetadata(
        "Days left",
        unit_of_measurement=TIME_DAYS,
        icon="mdi:calendar-today",
    ),
    "before_offpeak_download": EboxSensorMetadata(
        "Download before offpeak",
        unit_of_measurement=DATA_GIGABITS,
        icon="mdi:download",
    ),
    "before_offpeak_upload": EboxSensorMetadata(
        "Upload before offpeak",
        unit_of_measurement=DATA_GIGABITS,
        icon="mdi:upload",
    ),
    "before_offpeak_total": EboxSensorMetadata(
        "Total before offpeak",
        unit_of_measurement=DATA_GIGABITS,
        icon="mdi:download",
    ),
    "offpeak_download": EboxSensorMetadata(
        "Offpeak download",
        unit_of_measurement=DATA_GIGABITS,
        icon="mdi:download",
    ),
    "offpeak_upload": EboxSensorMetadata(
        "Offpeak Upload",
        unit_of_measurement=DATA_GIGABITS,
        icon="mdi:upload",
    ),
    "offpeak_total": EboxSensorMetadata(
        "Offpeak Total",
        unit_of_measurement=DATA_GIGABITS,
        icon="mdi:download",
    ),
    "download": EboxSensorMetadata(
        "Download",
        unit_of_measurement=DATA_GIGABITS,
        icon="mdi:download",
    ),
    "upload": EboxSensorMetadata(
        "Upload",
        unit_of_measurement=DATA_GIGABITS,
        icon="mdi:upload",
    ),
    "total": EboxSensorMetadata(
        "Total",
        unit_of_measurement=DATA_GIGABITS,
        icon="mdi:download",
    ),
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_VARIABLES): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the EBox sensor."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    httpsession = hass.helpers.aiohttp_client.async_get_clientsession()
    ebox_data = EBoxData(username, password, httpsession)

    name = config.get(CONF_NAME)

    try:
        await ebox_data.async_update()
    except PyEboxError as exp:
        _LOGGER.error("Failed login: %s", exp)
        raise PlatformNotReady from exp

    sensors = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        sensors.append(EBoxSensor(ebox_data, variable, name))

    async_add_entities(sensors, True)


class EBoxSensor(SensorEntity):
    """Implementation of a EBox sensor."""

    def __init__(self, ebox_data, sensor_type, name):
        """Initialize the sensor."""
        self.type = sensor_type
        metadata = SENSOR_TYPES[sensor_type]
        self._attr_name = f"{name} {metadata.name}"
        self._attr_unit_of_measurement = metadata.unit_of_measurement
        self._attr_icon = metadata.icon
        self.ebox_data = ebox_data
        self._state = None

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Get the latest data from EBox and update the state."""
        await self.ebox_data.async_update()
        if self.type in self.ebox_data.data:
            self._state = round(self.ebox_data.data[self.type], 2)


class EBoxData:
    """Get data from Ebox."""

    def __init__(self, username, password, httpsession):
        """Initialize the data object."""
        self.client = EboxClient(username, password, REQUESTS_TIMEOUT, httpsession)
        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from Ebox."""
        try:
            await self.client.fetch_data()
        except PyEboxError as exp:
            _LOGGER.error("Error on receive last EBox data: %s", exp)
            return
        # Update data
        self.data = self.client.get_data()
