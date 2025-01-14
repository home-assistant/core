"""Support for Open Hardware Monitor Sensor Platform."""

from __future__ import annotations

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

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

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {vol.Required(CONNECTION_HOST): cv.string, vol.Optional(CONNECTION_PORT, default=8085): cv.port}
)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Open Hardware Monitor platform."""
    #data = OpenHardwareMonitorData(config_entry.data, hass)
    data = hass.data["monitor_instance"]
    if data.data is None:
        raise PlatformNotReady
    #await data.initialize(utcnow())
    async_add_entities(data.devices, True)

class OpenHardwareMonitorDevice(SensorEntity):
    """Device used to display information from OpenHardwareMonitor."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, data, name, path, unit_of_measurement, id, child_names, json):
        """Initialize an OpenHardwareMonitor sensor."""
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
        if groupDevicesPerDepthLevel == 2:
            model = child_names[1]

        self._attr_unique_id = f"ohm-{name}-{id}"
        self._attr_device_info = DeviceInfo(
            identifiers= {(DOMAIN, deviceName)},
            via_device=(DOMAIN, f"{host}:{port}"),
            # If desired, the name for the device could be different to the entity
            name = str(deviceName),
            manufacturer = manufacturer,
            model = model,
        )

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
