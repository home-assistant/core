"""Support for monitoring pyLoad."""
from __future__ import annotations

from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONTENT_TYPE_JSON,
    UnitOfDataRate,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "pyLoad"
DEFAULT_PORT = 8000

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)

SENSOR_TYPES = {
    "speed": SensorEntityDescription(
        key="speed",
        name="Speed",
        native_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
    )
}

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


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the pyLoad sensors."""
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    protocol = "https" if config[CONF_SSL] else "http"
    name = config[CONF_NAME]
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    monitored_types = config[CONF_MONITORED_VARIABLES]
    url = f"{protocol}://{host}:{port}/api/"

    try:
        pyloadapi = PyLoadAPI(api_url=url, username=username, password=password)
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.HTTPError,
    ) as conn_err:
        _LOGGER.error("Error setting up pyLoad API: %s", conn_err)
        return

    devices = []
    for ng_type in monitored_types:
        new_sensor = PyLoadSensor(
            api=pyloadapi, sensor_type=SENSOR_TYPES[ng_type], client_name=name
        )
        devices.append(new_sensor)

    add_entities(devices, True)


class PyLoadSensor(SensorEntity):
    """Representation of a pyLoad sensor."""

    def __init__(
        self, api: PyLoadAPI, sensor_type: SensorEntityDescription, client_name
    ) -> None:
        """Initialize a new pyLoad sensor."""
        self._attr_name = f"{client_name} {sensor_type.name}"
        self.type = sensor_type.key
        self.api = api
        self.entity_description = sensor_type

    def update(self) -> None:
        """Update state of sensor."""
        try:
            self.api.update()
        except requests.exceptions.ConnectionError:
            # Error calling the API, already logged in api.update()
            return

        if self.api.status is None:
            _LOGGER.debug(
                "Update of %s requested, but no status is available", self.name
            )
            return

        if (value := self.api.status.get(self.type)) is None:
            _LOGGER.warning("Unable to locate value for %s", self.type)
            return

        if "speed" in self.type and value > 0:
            # Convert download rate from Bytes/s to MBytes/s
            self._attr_native_value = round(value / 2**20, 2)
        else:
            self._attr_native_value = value


class PyLoadAPI:
    """Simple wrapper for pyLoad's API."""

    def __init__(self, api_url, username=None, password=None):
        """Initialize pyLoad API and set headers needed later."""
        self.api_url = api_url
        self.status = None
        self.headers = {"Content-Type": CONTENT_TYPE_JSON}

        if username is not None and password is not None:
            self.payload = {"username": username, "password": password}
            self.login = requests.post(f"{api_url}login", data=self.payload, timeout=5)
        self.update()

    def post(self):
        """Send a POST request and return the response as a dict."""
        try:
            response = requests.post(
                f"{self.api_url}statusServer",
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
        self.status = self.post()
