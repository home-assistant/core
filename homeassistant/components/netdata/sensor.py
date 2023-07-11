"""Support gathering system information of hosts which are running netdata."""
from __future__ import annotations

import logging

from netdata import Netdata
from netdata.exceptions import NetdataError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_HOST,
    CONF_ICON,
    CONF_NAME,
    CONF_PORT,
    CONF_RESOURCES,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_DATA_GROUP = "data_group"
CONF_ELEMENT = "element"
CONF_INVERT = "invert"

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "Netdata"
DEFAULT_PORT = 19999

DEFAULT_ICON = "mdi:desktop-classic"

RESOURCE_SCHEMA = vol.Any(
    {
        vol.Required(CONF_DATA_GROUP): cv.string,
        vol.Required(CONF_ELEMENT): cv.string,
        vol.Optional(CONF_ICON, default=DEFAULT_ICON): cv.icon,
        vol.Optional(CONF_INVERT, default=False): cv.boolean,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_RESOURCES): vol.Schema({cv.string: RESOURCE_SCHEMA}),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Netdata sensor."""

    name = config[CONF_NAME]
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    resources = config[CONF_RESOURCES]

    netdata = NetdataData(Netdata(host, port=port, timeout=20.0))
    await netdata.async_update()

    if netdata.api.metrics is None:
        raise PlatformNotReady

    dev: list[SensorEntity] = []
    for entry, data in resources.items():
        icon = data[CONF_ICON]
        sensor = data[CONF_DATA_GROUP]
        element = data[CONF_ELEMENT]
        invert = data[CONF_INVERT]
        sensor_name = entry
        try:
            resource_data = netdata.api.metrics[sensor]
            unit = (
                PERCENTAGE
                if resource_data["units"] == "percentage"
                else resource_data["units"]
            )
        except KeyError:
            _LOGGER.error("Sensor is not available: %s", sensor)
            continue

        dev.append(
            NetdataSensor(
                netdata, name, sensor, sensor_name, element, icon, unit, invert
            )
        )

    dev.append(NetdataAlarms(netdata, name, host, port))
    async_add_entities(dev, True)


class NetdataSensor(SensorEntity):
    """Implementation of a Netdata sensor."""

    def __init__(self, netdata, name, sensor, sensor_name, element, icon, unit, invert):
        """Initialize the Netdata sensor."""
        self.netdata = netdata
        self._state = None
        self._sensor = sensor
        self._element = element
        self._sensor_name = self._sensor if sensor_name is None else sensor_name
        self._name = name
        self._icon = icon
        self._unit_of_measurement = unit
        self._invert = invert

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self._sensor_name}"

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def native_value(self):
        """Return the state of the resources."""
        return self._state

    @property
    def available(self) -> bool:
        """Could the resource be accessed during the last update call."""
        return self.netdata.available

    async def async_update(self) -> None:
        """Get the latest data from Netdata REST API."""
        await self.netdata.async_update()
        resource_data = self.netdata.api.metrics.get(self._sensor)
        self._state = round(resource_data["dimensions"][self._element]["value"], 2) * (
            -1 if self._invert else 1
        )


class NetdataAlarms(SensorEntity):
    """Implementation of a Netdata alarm sensor."""

    def __init__(self, netdata, name, host, port):
        """Initialize the Netdata alarm sensor."""
        self.netdata = netdata
        self._state = None
        self._name = name
        self._host = host
        self._port = port

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} Alarms"

    @property
    def native_value(self):
        """Return the state of the resources."""
        return self._state

    @property
    def icon(self):
        """Status symbol if type is symbol."""
        if self._state == "ok":
            return "mdi:check"
        if self._state == "warning":
            return "mdi:alert-outline"
        if self._state == "critical":
            return "mdi:alert"
        return "mdi:crosshairs-question"

    @property
    def available(self) -> bool:
        """Could the resource be accessed during the last update call."""
        return self.netdata.available

    async def async_update(self) -> None:
        """Get the latest alarms from Netdata REST API."""
        await self.netdata.async_update()
        alarms = self.netdata.api.alarms["alarms"]
        self._state = None
        number_of_alarms = len(alarms)
        number_of_relevant_alarms = number_of_alarms

        _LOGGER.debug("Host %s has %s alarms", self.name, number_of_alarms)

        for alarm in alarms:
            if alarms[alarm]["recipient"] == "silent":
                number_of_relevant_alarms = number_of_relevant_alarms - 1
            elif alarms[alarm]["status"] == "CLEAR":
                number_of_relevant_alarms = number_of_relevant_alarms - 1
            elif alarms[alarm]["status"] == "UNDEFINED":
                number_of_relevant_alarms = number_of_relevant_alarms - 1
            elif alarms[alarm]["status"] == "UNINITIALIZED":
                number_of_relevant_alarms = number_of_relevant_alarms - 1
            elif alarms[alarm]["status"] == "CRITICAL":
                self._state = "critical"
                return
        self._state = "ok" if number_of_relevant_alarms == 0 else "warning"


class NetdataData:
    """The class for handling the data retrieval."""

    def __init__(self, api):
        """Initialize the data object."""
        self.api = api
        self.available = True

    async def async_update(self):
        """Get the latest data from the Netdata REST API."""

        try:
            await self.api.get_allmetrics()
            await self.api.get_alarms()
            self.available = True
        except NetdataError:
            _LOGGER.error("Unable to retrieve data from Netdata")
            self.available = False
