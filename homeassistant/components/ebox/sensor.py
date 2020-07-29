"""
Support for EBox.

Get data from 'My Usage Page' page: https://client.ebox.ca/myusage
"""
from datetime import timedelta
import logging

from pyebox import EboxClient
from pyebox.client import PyEboxError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    DATA_GIGABITS,
    TIME_DAYS,
    UNIT_PERCENTAGE,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

PRICE = "CAD"

DEFAULT_NAME = "EBox"

REQUESTS_TIMEOUT = 15
SCAN_INTERVAL = timedelta(minutes=15)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

SENSOR_TYPES = {
    "usage": ["Usage", UNIT_PERCENTAGE, "mdi:percent"],
    "balance": ["Balance", PRICE, "mdi:cash-usd"],
    "limit": ["Data limit", DATA_GIGABITS, "mdi:download"],
    "days_left": ["Days left", TIME_DAYS, "mdi:calendar-today"],
    "before_offpeak_download": [
        "Download before offpeak",
        DATA_GIGABITS,
        "mdi:download",
    ],
    "before_offpeak_upload": ["Upload before offpeak", DATA_GIGABITS, "mdi:upload"],
    "before_offpeak_total": ["Total before offpeak", DATA_GIGABITS, "mdi:download"],
    "offpeak_download": ["Offpeak download", DATA_GIGABITS, "mdi:download"],
    "offpeak_upload": ["Offpeak Upload", DATA_GIGABITS, "mdi:upload"],
    "offpeak_total": ["Offpeak Total", DATA_GIGABITS, "mdi:download"],
    "download": ["Download", DATA_GIGABITS, "mdi:download"],
    "upload": ["Upload", DATA_GIGABITS, "mdi:upload"],
    "total": ["Total", DATA_GIGABITS, "mdi:download"],
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
        raise PlatformNotReady

    sensors = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        sensors.append(EBoxSensor(ebox_data, variable, name))

    async_add_entities(sensors, True)


class EBoxSensor(Entity):
    """Implementation of a EBox sensor."""

    def __init__(self, ebox_data, sensor_type, name):
        """Initialize the sensor."""
        self.client_name = name
        self.type = sensor_type
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self.ebox_data = ebox_data
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

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
