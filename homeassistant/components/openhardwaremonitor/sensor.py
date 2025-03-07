"""Support for Open Hardware Monitor Sensor Platform."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Mapping

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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, GROUP_DEVICES_PER_DEPTH_LEVEL
from .coordinator import OpenHardwareMonitorDataCoordinator
from .types import SensorNode

from . import OpenHardwareMonitorConfigEntry

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

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST): cv.string, vol.Optional(CONF_PORT, default=8085): cv.port}
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenHardwareMonitorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Open Hardware Monitor platform."""
    coordinator = config_entry.runtime_data
    if not coordinator.data:
        raise PlatformNotReady

    sensor_data = coordinator.data[:1]  # only test with 5
    entities = ([OpenHardwareMonitorSensorDevice(
            node=sensor_node,
            config_entry_data=config_entry.data
            #self, fullname, path, unit_of_measurement, id, child_names, json
        )
        for sensor_node in sensor_data
    ]
    )
    async_add_entities(entities, True)


class OpenHardwareMonitorSensorDevice(CoordinatorEntity[OpenHardwareMonitorDataCoordinator], SensorEntity):
    """Sensor entity used to display information from OpenHardwareMonitor."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        node: SensorNode,
        config_entry_data: Mapping[str, Any],
        data = None, name = None, path = None, unit_of_measurement = None, id = None, child_names = None, json = None
    ) -> None:
        """Initialize an OpenHardwareMonitor sensor."""
        if not child_names:
            child_names = node["Path"]
        if not name:
            name = node["Text"]
        if not id:
            id = node["id"]
        if not unit_of_measurement:
            unit_of_measurement = node["Value"].split(" ")[1]

        fullname = f"{" ".join(child_names)} {name}"
        
        
        # groupDevicesPerDepthLevel = data._config.get(GROUP_DEVICES_PER_DEPTH_LEVEL)
        # host = data._config.get(CONF_HOST)
        # port = data._config.get(CONF_PORT)
        # deviceName = " ".join(child_names[0:groupDevicesPerDepthLevel])
        
        groupDevicesPerDepthLevel = config_entry_data.get(GROUP_DEVICES_PER_DEPTH_LEVEL)
        host = config_entry_data.get(CONF_HOST)
        port = config_entry_data.get(CONF_PORT)
        deviceName = " ".join(child_names[0:groupDevicesPerDepthLevel])
        

        self._node = node
        self._name = name
        self._data = data
        # self._json = json
        self.path = path
        self._path_key = fullname
        self.id = id
        self.value = None
        self.attributes = {}
        self._unit_of_measurement = unit_of_measurement
        # self._attr_unique_id = f"ohm-{name}-{id}"
        
        self._apply_data(node)

        manufacturer = ""
        if groupDevicesPerDepthLevel == 1:
            # Computer device
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{host}:{port}")},
                name=str(child_names[0]),
                manufacturer="Computer",
            )
            return

        if groupDevicesPerDepthLevel == 2:
            manufacturer = "Hardware"
        else:
            manufacturer = "Group"

        model = ""
        if groupDevicesPerDepthLevel == 2:
            model = child_names[1]

        # Hardware or Group device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, deviceName)},
            via_device=(DOMAIN, f"{host}:{port}"),
            name=deviceName,
            manufacturer=manufacturer,
            model=model,
        )

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

    # async def async_update(self) -> None:
    #     """Update the device from a new JSON object."""
    #     # self._data.update()
    #     await self._data.async_update()

    #     array = self._data.data[OHM_CHILDREN]
    #     _attributes = {}

    #     for path_index, path_number in enumerate(self.path):
    #         values = array[path_number]

    #         if path_index == len(self.path) - 1:
    #             self.value = self.parse_number(values[OHM_VALUE].split(" ")[0])
    #             _attributes.update(
    #                 {
    #                     "name": values[OHM_NAME],
    #                     "path": self.path,
    #                     "id": self.id,
    #                     STATE_MIN_VALUE: self.parse_number(
    #                         values[OHM_MIN].split(" ")[0]
    #                     ),
    #                     STATE_MAX_VALUE: self.parse_number(
    #                         values[OHM_MAX].split(" ")[0]
    #                     ),
    #                 }
    #             )

    #             self.attributes = _attributes
    #             return
    #         array = array[path_number][OHM_CHILDREN]
    #         _attributes.update({f"level_{path_index}": values[OHM_NAME]})

    def _apply_data(self, node: SensorNode) -> None:
        self._node = node
        self.value = self.parse_number(node["Value"].split(" ")[0])
        self.attributes.update(
            {
                "name": node[OHM_NAME],
                "path": self.path,
                "id": self.id,
                STATE_MIN_VALUE: self.parse_number(
                    node[OHM_MIN].split(" ")[0]
                ),
                STATE_MAX_VALUE: self.parse_number(
                    node[OHM_MAX].split(" ")[0]
                ),
            }
        )

    def _handle_coordinator_update(self):
        if node := self.coordinator.get_sensor_node(self._path_key):
            self._apply_data(node)
        return super()._handle_coordinator_update()

