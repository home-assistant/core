"""Support for Open Hardware Monitor Sensor Platform."""

from __future__ import annotations

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import (
    OpenHardwareMonitorConfigEntry,
    OpenHardwareMonitorDataCoordinator,
)
from .types import SensorNode

STATE_MIN_VALUE = "minimal_value"
STATE_MAX_VALUE = "maximum_value"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)
SCAN_INTERVAL = timedelta(seconds=30)
RETRY_INTERVAL = timedelta(seconds=30)

OHM_VALUE = "Value"
OHM_MIN = "Min"
OHM_MAX = "Max"
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

    sensor_data = coordinator.data
    entities = [
        OpenHardwareMonitorSensorDevice(
            node=sensor_data[k],
            coordinator=coordinator,
            # self, fullname, path, unit_of_measurement, id, child_names, json
        )
        for k in sensor_data
    ]
    async_add_entities(entities, True)


class OpenHardwareMonitorSensorDevice(
    CoordinatorEntity[OpenHardwareMonitorDataCoordinator], SensorEntity
):
    """Sensor entity used to display information from OpenHardwareMonitor."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        node: SensorNode,
        coordinator: OpenHardwareMonitorDataCoordinator,
    ) -> None:
        """Initialize an OpenHardwareMonitor sensor."""
        super().__init__(coordinator=coordinator)

        self._node = node
        self._fullname = node["FullName"]
        self.attributes = {}
        self._attr_unique_id = f"ohm-{self._fullname}"

        value_parts = node.get("Value", "").split(" ")
        self._unit_of_measurement = value_parts[1] if len(value_parts) > 1 else None
        self.value = self.parse_number(value_parts[0]) if len(value_parts) > 0 else None

        self._apply_data(node)
        self._attr_device_info = coordinator.resolve_device_info_for_node(node)

    @property
    def name(self):
        """Return the name of the device."""
        return self._fullname

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

    def _apply_data(self, node: SensorNode) -> None:
        # Update info
        self._node = node
        self._fullname = (
            node["FullName"]
            if node.get("FullName")
            else self._fullname or node[OHM_NAME]
        )

        # Update value
        value_parts = node.get("Value", "").split(" ")
        self._unit_of_measurement = (
            value_parts[1]
            if len(value_parts) > 1 and not self._unit_of_measurement
            else self._unit_of_measurement
        )
        self.value = (
            self.parse_number(value_parts[0]) if len(value_parts) > 0 else self.value
        )

        # Update attributes
        self.attributes.update(
            {
                "computer": node.get("ComputerName"),
                "paths": str(node.get("Paths")),
                "name": node[OHM_NAME],
                STATE_MIN_VALUE: self.parse_number(node[OHM_MIN].split(" ")[0]),
                STATE_MAX_VALUE: self.parse_number(node[OHM_MAX].split(" ")[0]),
                "id": node.get(OHM_ID),
                "sensorId": node.get("SensorId"),
                "type": node.get("Type"),
            }
        )

    def _handle_coordinator_update(self):
        if node := self.coordinator.get_sensor_node(self._fullname):
            self._apply_data(node)
        return super()._handle_coordinator_update()
