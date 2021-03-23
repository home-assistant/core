"""Support for consuming values for the Volkszaehler API."""
from datetime import timedelta
import logging

from volkszaehler import Volkszaehler
from volkszaehler.exceptions import VolkszaehlerApiConnectionError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PORT,
    ENERGY_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_UUID = "uuid"

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "Volkszaehler"
DEFAULT_PORT = 80

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

SENSOR_TYPES = {
    "average": ["Average", POWER_WATT, "mdi:power-off"],
    "consumption": ["Consumption", ENERGY_WATT_HOUR, "mdi:power-plug"],
    "max": ["Max", POWER_WATT, "mdi:arrow-up"],
    "min": ["Min", POWER_WATT, "mdi:arrow-down"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_UUID): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["average"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Volkszaehler sensors."""

    host = config[CONF_HOST]
    name = config[CONF_NAME]
    port = config[CONF_PORT]
    uuid = config[CONF_UUID]
    conditions = config[CONF_MONITORED_CONDITIONS]

    session = async_get_clientsession(hass)
    vz_api = VolkszaehlerData(
        Volkszaehler(hass.loop, session, uuid, host=host, port=port)
    )

    await vz_api.async_update()

    if vz_api.api.data is None:
        raise PlatformNotReady

    dev = []
    for condition in conditions:
        dev.append(VolkszaehlerSensor(vz_api, name, condition))

    async_add_entities(dev, True)


class VolkszaehlerSensor(SensorEntity):
    """Implementation of a Volkszaehler sensor."""

    def __init__(self, vz_api, name, sensor_type):
        """Initialize the Volkszaehler sensor."""
        self.vz_api = vz_api
        self._name = name
        self.type = sensor_type
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format(self._name, SENSOR_TYPES[self.type][0])

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.type][2]

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SENSOR_TYPES[self.type][1]

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self.vz_api.available

    @property
    def state(self):
        """Return the state of the resources."""
        return self._state

    async def async_update(self):
        """Get the latest data from REST API."""
        await self.vz_api.async_update()

        if self.vz_api.api.data is not None:
            self._state = round(getattr(self.vz_api.api, self.type), 2)


class VolkszaehlerData:
    """The class for handling the data retrieval from the Volkszaehler API."""

    def __init__(self, api):
        """Initialize the data object."""
        self.api = api
        self.available = True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from the Volkszaehler REST API."""

        try:
            await self.api.get_data()
            self.available = True
        except VolkszaehlerApiConnectionError:
            _LOGGER.error("Unable to fetch data from the Volkszaehler API")
            self.available = False
