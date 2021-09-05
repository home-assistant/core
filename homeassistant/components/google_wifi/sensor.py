"""Support for retrieving status info from Google Wifi/OnHub routers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    STATE_UNKNOWN,
    TIME_DAYS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle, dt

_LOGGER = logging.getLogger(__name__)

ATTR_CURRENT_VERSION = "current_version"
ATTR_LAST_RESTART = "last_restart"
ATTR_LOCAL_IP = "local_ip"
ATTR_NEW_VERSION = "new_version"
ATTR_STATUS = "status"
ATTR_UPTIME = "uptime"

DEFAULT_HOST = "testwifi.here"
DEFAULT_NAME = "google_wifi"

ENDPOINT = "/api/v1/status"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1)


@dataclass
class GoogleWifiRequiredKeysMixin:
    """Mixin for required keys."""

    primary_key: str
    sensor_key: str


@dataclass
class GoogleWifiSensorEntityDescription(
    SensorEntityDescription, GoogleWifiRequiredKeysMixin
):
    """Describes GoogleWifi sensor entity."""


SENSOR_TYPES: tuple[GoogleWifiSensorEntityDescription, ...] = (
    GoogleWifiSensorEntityDescription(
        key=ATTR_CURRENT_VERSION,
        primary_key="software",
        sensor_key="softwareVersion",
        icon="mdi:checkbox-marked-circle-outline",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_NEW_VERSION,
        primary_key="software",
        sensor_key="updateNewVersion",
        icon="mdi:update",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_UPTIME,
        primary_key="system",
        sensor_key="uptime",
        native_unit_of_measurement=TIME_DAYS,
        icon="mdi:timelapse",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_LAST_RESTART,
        primary_key="system",
        sensor_key="uptime",
        icon="mdi:restart",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_LOCAL_IP,
        primary_key="wan",
        sensor_key="localIpAddress",
        icon="mdi:access-point-network",
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_STATUS,
        primary_key="wan",
        sensor_key="online",
        icon="mdi:google",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Google Wifi sensor."""
    name = config[CONF_NAME]
    host = config[CONF_HOST]
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]

    api = GoogleWifiAPI(host, monitored_conditions)
    entities = [
        GoogleWifiSensor(api, name, description)
        for description in SENSOR_TYPES
        if description.key in monitored_conditions
    ]
    add_entities(entities, True)


class GoogleWifiSensor(SensorEntity):
    """Representation of a Google Wifi sensor."""

    entity_description: GoogleWifiSensorEntityDescription

    def __init__(self, api, name, description: GoogleWifiSensorEntityDescription):
        """Initialize a Google Wifi sensor."""
        self.entity_description = description
        self._api = api
        self._attr_name = f"{name}_{description.key}"

    @property
    def available(self):
        """Return availability of Google Wifi API."""
        return self._api.available

    def update(self):
        """Get the latest data from the Google Wifi API."""
        self._api.update()
        if self.available:
            self._attr_native_value = self._api.data[self.entity_description.key]
        else:
            self._attr_native_value = None


class GoogleWifiAPI:
    """Get the latest data and update the states."""

    def __init__(self, host, conditions):
        """Initialize the data object."""
        uri = "http://"
        resource = f"{uri}{host}{ENDPOINT}"
        self._request = requests.Request("GET", resource).prepare()
        self.raw_data = None
        self.conditions = conditions
        self.data = {
            ATTR_CURRENT_VERSION: STATE_UNKNOWN,
            ATTR_NEW_VERSION: STATE_UNKNOWN,
            ATTR_UPTIME: STATE_UNKNOWN,
            ATTR_LAST_RESTART: STATE_UNKNOWN,
            ATTR_LOCAL_IP: STATE_UNKNOWN,
            ATTR_STATUS: STATE_UNKNOWN,
        }
        self.available = True
        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the router."""
        try:
            with requests.Session() as sess:
                response = sess.send(self._request, timeout=10)
            self.raw_data = response.json()
            self.data_format()
            self.available = True
        except (ValueError, requests.exceptions.ConnectionError):
            _LOGGER.warning("Unable to fetch data from Google Wifi")
            self.available = False
            self.raw_data = None

    def data_format(self):
        """Format raw data into easily accessible dict."""
        for description in SENSOR_TYPES:
            if description.key not in self.conditions:
                continue
            attr_key = description.key
            try:
                if description.primary_key in self.raw_data:
                    sensor_value = self.raw_data[description.primary_key][
                        description.sensor_key
                    ]
                    # Format sensor for better readability
                    if attr_key == ATTR_NEW_VERSION and sensor_value == "0.0.0.0":
                        sensor_value = "Latest"
                    elif attr_key == ATTR_UPTIME:
                        sensor_value = round(sensor_value / (3600 * 24), 2)
                    elif attr_key == ATTR_LAST_RESTART:
                        last_restart = dt.now() - timedelta(seconds=sensor_value)
                        sensor_value = last_restart.strftime("%Y-%m-%d %H:%M:%S")
                    elif attr_key == ATTR_STATUS:
                        if sensor_value:
                            sensor_value = "Online"
                        else:
                            sensor_value = "Offline"
                    elif (
                        attr_key == ATTR_LOCAL_IP and not self.raw_data["wan"]["online"]
                    ):
                        sensor_value = STATE_UNKNOWN

                    self.data[attr_key] = sensor_value
            except KeyError:
                _LOGGER.error(
                    "Router does not support %s field. "
                    "Please remove %s from monitored_conditions",
                    description.sensor_key,
                    attr_key,
                )
                self.data[attr_key] = STATE_UNKNOWN
