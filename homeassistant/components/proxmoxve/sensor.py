"""Sensor to read Proxmox VE data."""
import logging

from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    DATA_GIBIBYTES,
    DATA_MEBIBYTES,
    PERCENTAGE,
)
from homeassistant.helpers.entity import Entity

from . import CONF_CONTAINERS, CONF_NODES, CONF_VMS, PROXMOX_CLIENTS, ProxmoxItemType

ATTRIBUTION = "Data provided by Proxmox VE"
_LOGGER = logging.getLogger(__name__)

SENSOR_AVAIL_LXC = ProxmoxItemType.lxc
SENSOR_AVAIL_QEMU = ProxmoxItemType.qemu
SENSOR_AVAIL_ALL = [SENSOR_AVAIL_LXC, SENSOR_AVAIL_QEMU]


# Schema: [name, unit of measurement, icon, availablility]
SENSOR_TYPES = {
    "cpu_use_percent": ["CPU use", PERCENTAGE, "mdi:chip", None, SENSOR_AVAIL_ALL],
    "cpu": ["CPU count", None, "mdi:chip", None, SENSOR_AVAIL_ALL],
    "memory_free": [
        "Memory free",
        DATA_MEBIBYTES,
        "mdi:memory",
        None,
        SENSOR_AVAIL_ALL,
    ],
    "memory_use": ["Memory use", DATA_MEBIBYTES, "mdi:memory", None, SENSOR_AVAIL_ALL],
    "memory_use_percent": [
        "Memory use (percent)",
        PERCENTAGE,
        "mdi:memory",
        None,
        SENSOR_AVAIL_ALL,
    ],
    "mem": ["Memory size", DATA_MEBIBYTES, "mdi:memory", None, SENSOR_AVAIL_ALL],
    "disk_free": [
        "Disk free",
        DATA_GIBIBYTES,
        "mdi:harddisk",
        None,
        [SENSOR_AVAIL_LXC],
    ],
    "disk_use": ["Disk use", DATA_GIBIBYTES, "mdi:harddisk", None, [SENSOR_AVAIL_LXC]],
    "disk_use_percent": [
        "Disk use (percent)",
        PERCENTAGE,
        "mdi:harddisk",
        None,
        [SENSOR_AVAIL_LXC],
    ],
    "disk": ["Disk size", DATA_GIBIBYTES, "mdi:harddisk", None, SENSOR_AVAIL_ALL],
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    sensors = []

    for entry in discovery_info["entries"]:
        port = entry[CONF_PORT]

        for node in entry[CONF_NODES]:
            for virtual_machine in node[CONF_VMS]:
                for sensor in SENSOR_TYPES:
                    if ProxmoxItemType.qemu in SENSOR_TYPES[sensor][4]:
                        sensors.append(
                            ProxmoxSensor(
                                hass.data[PROXMOX_CLIENTS][
                                    f"{entry[CONF_HOST]}:{port}"
                                ],
                                node["node"],
                                ProxmoxItemType.qemu,
                                virtual_machine,
                                sensor,
                            )
                        )

            for container in node[CONF_CONTAINERS]:
                for sensor in SENSOR_TYPES:
                    if ProxmoxItemType.lxc in SENSOR_TYPES[sensor][4]:
                        sensors.append(
                            ProxmoxSensor(
                                hass.data[PROXMOX_CLIENTS][
                                    f"{entry[CONF_HOST]}:{port}"
                                ],
                                node["node"],
                                ProxmoxItemType.lxc,
                                container,
                                sensor,
                            )
                        )

    add_entities(sensors, True)


class ProxmoxSensor(Entity):
    """A sensor for reading Proxmox VE data."""

    def __init__(self, proxmox_client, item_node, item_type, item_id, sensor_type):
        """Initialize the sensor."""
        self._available = True
        self._device_class = SENSOR_TYPES[sensor_type][3]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self._item_node = item_node
        self._item_type = item_type
        self._item_id = item_id
        self._name = None
        self._proxmox_client = proxmox_client
        self._sensor_type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    def update(self):
        """Update sensore values."""
        items = (
            self._proxmox_client.get_api_client()
            .nodes(self._item_node)
            .get(self._item_type.name)
        )
        item = next(
            (item for item in items if item["vmid"] == str(self._item_id)), None
        )

        if item is None:
            _LOGGER.warning("Couldn't find VM/Container with the ID %s", self._item_id)
            return None

        self._name = (
            f"{self._item_node} {item['name']} {SENSOR_TYPES[self._sensor_type][0]}"
        )

        item["disk"] = int(item["disk"])
        item["maxdisk"] = int(item["maxdisk"])

        if self._sensor_type == "cpu":
            self._state = item["cpus"]
        elif self._sensor_type == "cpu_use_percent":
            self._state = round(item["cpu"] * 100, 1)
        elif self._sensor_type == "mem":
            self._state = round(item["maxmem"] / (1024 ** 2), 1)
        elif self._sensor_type == "memory_free":
            self._state = round((item["maxmem"] - item["mem"]) / (1024 ** 2), 1)
        elif self._sensor_type == "memory_use":
            self._state = round(item["mem"] / (1024 ** 2), 1)
        elif self._sensor_type == "memory_use_percent":
            self._state = round(item["mem"] / item["maxmem"] * 100, 1)
        elif self._sensor_type == "disk":
            self._state = round(item["maxdisk"] / (1024 ** 3), 1)
        elif self._sensor_type == "disk_free":
            if self._item_type == ProxmoxItemType.lxc:
                self._state = round((item["maxdisk"] - item["disk"]) / (1024 ** 3), 0)
        elif self._sensor_type == "disk_use":
            if self._item_type == ProxmoxItemType.lxc:
                self._state = round(item["disk"] / (1024 ** 3), 1)
        elif self._sensor_type == "disk_use_percent":
            if self._item_type == ProxmoxItemType.lxc:
                self._state = round(item["disk"] / item["maxdisk"] * 100, 1)
