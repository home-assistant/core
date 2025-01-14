"""Support for Open Hardware Monitor Sensor Platform."""

from __future__ import annotations

from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
from homeassistant.util.dt import utcnow

_LOGGER = logging.getLogger(__name__)

STATE_MIN_VALUE = "minimal_value"
STATE_MAX_VALUE = "maximum_value"
STATE_VALUE = "value"
STATE_OBJECT = "object"
CONF_INTERVAL = "interval"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)
SCAN_INTERVAL = timedelta(seconds=30)
RETRY_INTERVAL = timedelta(seconds=30)

OHM_VALUE = "Value"
OHM_MIN = "Min"
OHM_MAX = "Max"
OHM_CHILDREN = "Children"
OHM_IMAGEURL = "ImageURL"
OHM_NAME = "Text"
OHM_ID = "id"
from .const import *

DOMAIN = "openhardwaremonitor"
PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST): cv.string, vol.Optional(CONF_PORT, default=8085): cv.port}
)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Open Hardware Monitor platform."""
    
    _LOGGER.warning("Host_pl: " + config_entry.data[CONNECTION_HOST])
    _LOGGER.warning("Port_pl: " + config_entry.data[CONNECTION_PORT])
    #data = OpenHardwareMonitorData(config_entry.data, hass)
    data = hass.data["monitor_instance"]
    if data.data is None:
        raise PlatformNotReady
    #await data.initialize(utcnow())
    async_add_entities(data.devices, True)

# async def async_setup_entry(
#     hass: HomeAssistant,
#     config_entry: ConfigEntry,
#     async_add_entities: AddEntitiesCallback,
# ) -> None:
#     """Set up the Roborock vacuum sensors."""
#     _LOGGER.warning("Host: " + config_entry.data[CONNECTION_HOST])
#     _LOGGER.warning("Port: " + config_entry.data[CONNECTION_PORT])
#     #setup_platform(hass, config=config_entry.data, async_add_entities=async_add_entities)
    
#     """Set up the Open Hardware Monitor platform."""
#     data = OpenHardwareMonitorData(config_entry.data, hass, async_add_entities)
#     #await data.initialize(utcnow())
#     if data.data is None:
#         raise PlatformNotReady

deviceGroupLevels = 2

class OpenHardwareMonitorDevice(SensorEntity):
    """Device used to display information from OpenHardwareMonitor."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, data, name, path, unit_of_measurement, id, child_names, json):
        """Initialize an OpenHardwareMonitor sensor."""
        currentLevel = len(child_names)
        groupDevicesPerDepthLevel = data._config.get(GROUP_DEVICES_PER_DEPTH_LEVEL)
        deviceName = " ".join(child_names[0:groupDevicesPerDepthLevel])

        self._name = name
        self._data = data
        self._json = json
        self.path = path
        self.id = id
        self.attributes = {}
        self._unit_of_measurement = unit_of_measurement

        
        host = data._config.get(CONNECTION_HOST)
        port = data._config.get(CONNECTION_PORT)
        manufacturer = ""
        if groupDevicesPerDepthLevel == 1:
            manufacturer = "Computer"
        elif groupDevicesPerDepthLevel == 2:
            manufacturer = "Hardware"
        else:
            manufacturer = "Group"
        
        model = ""
        _LOGGER.warning("|".join(child_names))
        _LOGGER.warning("cur: "+ str(currentLevel))
        if groupDevicesPerDepthLevel == 2:
            model = child_names[1]

        # self._attr_unique_id = f"ohm-{name}---{path}"
        self._attr_unique_id = f"ohm-{name}-{id}"
        self._attr_device_info = DeviceInfo(
            identifiers= {(DOMAIN, deviceName)},
            via_device=(DOMAIN, f"{host}:{port}"),
            # If desired, the name for the device could be different to the entity
            name = str(deviceName),
            manufacturer = manufacturer,
            model = model,
        )
        self._attr_state_class = SensorStateClass.MEASUREMENT

        self.value = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def native_value(self):
        """Return the state of the device."""
        if self.value == "-":
            return None
        return self.value

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the entity."""
        return self.attributes

    @property
    def device_info(self):
        """Information about this entity's device."""
        return self._attr_device_info

    @classmethod
    def parse_number(cls, string):
        """In some locales a decimal numbers uses ',' instead of '.'."""
        return string.replace(",", ".")

    async def async_update(self) -> None:
        """Update the device from a new JSON object."""
        #self._data.update()
        await self._data.async_update()

        array = self._data.data[OHM_CHILDREN]
        _attributes = {}

        for path_index, path_number in enumerate(self.path):
            values = array[path_number]

            if path_index == len(self.path) - 1:
                self.value = self.parse_number(values[OHM_VALUE].split(" ")[0])
                _attributes.update(
                    {
                        "name": values[OHM_NAME],
                        "path": self.path,
                        "id": self.id,
                        STATE_MIN_VALUE: self.parse_number(
                            values[OHM_MIN].split(" ")[0]
                        ),
                        STATE_MAX_VALUE: self.parse_number(
                            values[OHM_MAX].split(" ")[0]
                        ),
                    }
                )

                self.attributes = _attributes
                return
            array = array[path_number][OHM_CHILDREN]
            _attributes.update({f"level_{path_index}": values[OHM_NAME]})
    
    # @property
    # def entity_picture(self) -> str | None:
    #     """Return the icon of the entity."""
    #     host = self._data._config.get(CONNECTION_HOST)
    #     port = self._data._config.get(CONNECTION_PORT)
    #     base = f"http://{host}:{port}/"
    #     rel = self._json[OHM_IMAGEURL]
    #     url = f"{base}{rel}"
    #     _LOGGER.warning("IMG: " + str(url))
    #     return url


class OpenHardwareMonitorData_old:
    """Class used to pull data from OHM and create sensors."""

    def __init__(self, config, hass):
        """Initialize the Open Hardware Monitor data-handler."""
        self.data = None
        self._config = config
        self._hass = hass
        self.devices = []
        #self.initialize(utcnow())

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Hit by the timer with the configured interval."""
        if self.data is None:
            await self.initialize(utcnow())
        else:
            await self.refresh()

    async def refresh(self):
        """Download and parse JSON from OHM."""
        data_url = (
            f"http://{self._config.get(CONF_HOST)}:"
            f"{self._config.get(CONF_PORT)}/data.json"
        )
        _LOGGER.warning("URL: " + str(data_url))

        try:
            response = requests.get(data_url, timeout=30)
            self.data = response.json()
        except requests.exceptions.ConnectionError:
            _LOGGER.debug("ConnectionError: Is OpenHardwareMonitor running?")

    async def initialize(self, now, async_add_entities):
        """Parse of the sensors and adding of devices."""
        await self.refresh()

        if self.data is None:
            return

        self.devices = self.parse_children(self.data, [], [], [])
        
        async_add_entities(
            self.data.devices, True)

    def parse_children(self, json, devices, path, names):
        """Recursively loop through child objects, finding the values."""
        result = devices.copy()

        if json[OHM_CHILDREN]:
            for child_index in range(len(json[OHM_CHILDREN])):
                child_path = path.copy()
                child_path.append(child_index)

                child_names = names.copy()
                if path:
                    child_names.append(json[OHM_NAME])

                obj = json[OHM_CHILDREN][child_index]

                added_devices = self.parse_children(
                    obj, devices, child_path, child_names
                )

                result = result + added_devices
            return result

        if json[OHM_VALUE].find(" ") == -1:
            return result

        id = str(json[OHM_ID])
        unit_of_measurement = json[OHM_VALUE].split(" ")[1]
        child_names = names.copy()
        child_names.append(json[OHM_NAME])
        fullname = " ".join(child_names)

        dev = OpenHardwareMonitorDevice(self, fullname, path, unit_of_measurement, id, child_names)

        result.append(dev)
        return result
