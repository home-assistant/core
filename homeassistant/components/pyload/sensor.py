"""Support for monitoring pyLoad."""
from datetime import timedelta
import logging

from aiohttp.hdrs import CONTENT_TYPE
import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONTENT_TYPE_JSON,
    DATA_RATE_MEGABYTES_PER_SECOND,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "pyLoad"
DEFAULT_PORT = 8000

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)

SENSOR_TYPES = {"speed": ["speed", "Speed", DATA_RATE_MEGABYTES_PER_SECOND]}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=["speed"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_USERNAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the pyLoad sensors."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    protocol = "https" if config[CONF_SSL] else "http"
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    monitored_types = config.get(CONF_MONITORED_VARIABLES)
    url = f"{protocol}://{host}:{port}/api/"

    try:
        pyloadapi = PyLoadAPI(api_url=url, username=username, password=password)
        pyloadapi.update()
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.HTTPError,
    ) as conn_err:
        _LOGGER.error("Error setting up pyLoad API: %s", conn_err)
        return False

    devices = []
    for ng_type in monitored_types:
        new_sensor = PyLoadSensor(
            api=pyloadapi, sensor_type=SENSOR_TYPES.get(ng_type), client_name=name
        )
        devices.append(new_sensor)

    add_entities(devices, True)


class PyLoadSensor(Entity):
    """Representation of a pyLoad sensor."""

    def __init__(self, api, sensor_type, client_name):
        """Initialize a new pyLoad sensor."""
        self._name = f"{client_name} {sensor_type[1]}"
        self.type = sensor_type[0]
        self.api = api
        self._state = None
        self._unit_of_measurement = sensor_type[2]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Update state of sensor."""
        try:
            self.api.update()
        except requests.exceptions.ConnectionError:
            # Error calling the API, already logged in api.update()
            return

        if self.api.status is None:
            _LOGGER.debug(
                "Update of %s requested, but no status is available", self._name
            )
            return

        value = self.api.status.get(self.type)
        if value is None:
            _LOGGER.warning("Unable to locate value for %s", self.type)
            return

        if "speed" in self.type and value > 0:
            # Convert download rate from Bytes/s to MBytes/s
            self._state = round(value / 2 ** 20, 2)
        else:
            self._state = value


class PyLoadAPI:
    """Simple wrapper for pyLoad's API."""

    def __init__(self, api_url, username=None, password=None):
        """Initialize pyLoad API and set headers needed later."""
        self.api_url = api_url
        self.status = None
        self.headers = {CONTENT_TYPE: CONTENT_TYPE_JSON}

        if username is not None and password is not None:
            self.payload = {"username": username, "password": password}
            self.login = requests.post(f"{api_url}login", data=self.payload, timeout=5)
        self.update()

    def post(self, method, params=None):
        """Send a POST request and return the response as a dict."""
        payload = {"method": method}

        if params:
            payload["params"] = params

        try:
            response = requests.post(
                f"{self.api_url}statusServer",
                json=payload,
                cookies=self.login.cookies,
                headers=self.headers,
                timeout=5,
            )
            response.raise_for_status()
            _LOGGER.debug("JSON Response: %s", response.json())
            return response.json()

        except requests.exceptions.ConnectionError as conn_exc:
            _LOGGER.error("Failed to update pyLoad status. Error: %s", conn_exc)
            raise

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update cached response."""
        self.status = self.post("speed")
