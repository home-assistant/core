"""Support for QNAP NAS Sensors."""
import logging

from homeassistant.const import ATTR_NAME, CONF_MONITORED_CONDITIONS, DATA_GIBIBYTES
from homeassistant.helpers.entity import Entity

from .const import (
    _CPU_MON_COND,
    _DRIVE_MON_COND,
    _MEMORY_MON_COND,
    _NETWORK_MON_COND,
    _SYSTEM_MON_COND,
    _VOLUME_MON_COND,
    CONF_DRIVES,
    CONF_NICS,
    CONF_VOLUMES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

ATTR_DRIVE = "Drive"
ATTR_DRIVE_SIZE = "Drive Size"
ATTR_IP = "IP Address"
ATTR_MAC = "MAC Address"
ATTR_MASK = "Mask"
ATTR_MAX_SPEED = "Max Speed"
ATTR_MEMORY_SIZE = "Memory Size"
ATTR_MODEL = "Model"
ATTR_PACKETS_TX = "Packets (TX)"
ATTR_PACKETS_RX = "Packets (RX)"
ATTR_PACKETS_ERR = "Packets (Err)"
ATTR_SERIAL = "Serial #"
ATTR_TYPE = "Type"
ATTR_UPTIME = "Uptime"
ATTR_VOLUME_SIZE = "Volume Size"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    coordinator = hass.data[DOMAIN]
    unique_id = config_entry.unique_id
    config = config_entry.options
    sensors = []

    # Basic sensors
    for variable in config.get(CONF_MONITORED_CONDITIONS):
        if variable in _SYSTEM_MON_COND:
            sensors.append(
                QNAPSystemSensor(
                    coordinator, unique_id, variable, _SYSTEM_MON_COND[variable]
                )
            )
        if variable in _CPU_MON_COND:
            sensors.append(
                QNAPCPUSensor(coordinator, unique_id, variable, _CPU_MON_COND[variable])
            )
        if variable in _MEMORY_MON_COND:
            sensors.append(
                QNAPMemorySensor(
                    coordinator, unique_id, variable, _MEMORY_MON_COND[variable]
                )
            )

    # Network sensors
    for nic in config.get(CONF_NICS, coordinator.data["system_stats"]["nics"]):
        sensors += [
            QNAPNetworkSensor(
                coordinator, unique_id, variable, _NETWORK_MON_COND[variable], nic
            )
            for variable in config.get(CONF_MONITORED_CONDITIONS)
            if variable in _NETWORK_MON_COND
        ]

    # Drive sensors
    for drive in config.get(CONF_DRIVES, coordinator.data["smart_drive_health"]):
        sensors += [
            QNAPDriveSensor(
                coordinator, unique_id, variable, _DRIVE_MON_COND[variable], drive
            )
            for variable in config.get(CONF_MONITORED_CONDITIONS)
            if variable in _DRIVE_MON_COND
        ]

    # Volume sensors
    for volume in config.get(CONF_VOLUMES, coordinator.data["volumes"]):
        sensors += [
            QNAPVolumeSensor(
                coordinator, unique_id, variable, _VOLUME_MON_COND[variable], volume
            )
            for variable in config.get(CONF_MONITORED_CONDITIONS)
            if variable in _VOLUME_MON_COND
        ]

    async_add_entities(sensors, True)


def round_nicely(number):
    """Round a number based on its size (so it looks nice)."""
    if number < 10:
        return round(number, 2)
    if number < 100:
        return round(number, 1)

    return round(number)


class QNAPSensor(Entity):
    """Base class for a QNAP sensor."""

    def __init__(self, coordinator, uid, variable, variable_info, monitor_device=None):
        """Initialize the sensor."""
        self.var_id = variable
        self.var_name = variable_info[0]
        self.var_units = variable_info[1]
        self.var_icon = variable_info[2]
        self.monitor_device = monitor_device
        self.coordinator = coordinator
        self.uid = uid

    @property
    def unique_id(self):
        """Return unique_id."""
        return f"{self.uid}_{self.name}"

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        server_name = self.coordinator.data["system_stats"]["system"]["name"]

        if self.monitor_device is not None:
            return f"{server_name} {self.var_name} ({self.monitor_device})"
        return f"{server_name} {self.var_name}"

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self.var_icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self.var_units

    @property
    def device_info(self):
        """Return device information."""
        return {"identifiers": {(DOMAIN, self.uid)}}


class QNAPCPUSensor(QNAPSensor):
    """A QNAP sensor that monitors CPU stats."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.var_id == "cpu_temp":
            return self.coordinator.data["system_stats"]["cpu"]["temp_c"]
        if self.var_id == "cpu_usage":
            return self.coordinator.data["system_stats"]["cpu"]["usage_percent"]


class QNAPMemorySensor(QNAPSensor):
    """A QNAP sensor that monitors memory stats."""

    @property
    def state(self):
        """Return the state of the sensor."""
        free = float(self.coordinator.data["system_stats"]["memory"]["free"]) / 1024
        if self.var_id == "memory_free":
            return round_nicely(free)

        total = float(self.coordinator.data["system_stats"]["memory"]["total"]) / 1024

        used = total - free
        if self.var_id == "memory_used":
            return round_nicely(used)

        if self.var_id == "memory_percent_used":
            return round(used / total * 100)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            data = self.coordinator.data["system_stats"]["memory"]
            size = round_nicely(float(data["total"]) / 1024)
            return {ATTR_MEMORY_SIZE: f"{size} {DATA_GIBIBYTES}"}


class QNAPNetworkSensor(QNAPSensor):
    """A QNAP sensor that monitors network stats."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.var_id == "network_link_status":
            nic = self.coordinator.data["system_stats"]["nics"][self.monitor_device]
            return nic["link_status"]

        data = self.coordinator.data["bandwidth"][self.monitor_device]
        if self.var_id == "network_tx":
            return round_nicely(data["tx"] / 1024 / 1024)

        if self.var_id == "network_rx":
            return round_nicely(data["rx"] / 1024 / 1024)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            data = self.coordinator.data["system_stats"]["nics"][self.monitor_device]
            return {
                ATTR_IP: data["ip"],
                ATTR_MASK: data["mask"],
                ATTR_MAC: data["mac"],
                ATTR_MAX_SPEED: data["max_speed"],
                ATTR_PACKETS_TX: data["tx_packets"],
                ATTR_PACKETS_RX: data["rx_packets"],
                ATTR_PACKETS_ERR: data["err_packets"],
            }


class QNAPSystemSensor(QNAPSensor):
    """A QNAP sensor that monitors overall system health."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.var_id == "status":
            return self.coordinator.data["system_health"]

        if self.var_id == "system_temp":
            return int(self.coordinator.data["system_stats"]["system"]["temp_c"])

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            data = self.coordinator.data["system_stats"]
            days = int(data["uptime"]["days"])
            hours = int(data["uptime"]["hours"])
            minutes = int(data["uptime"]["minutes"])

            return {
                ATTR_NAME: data["system"]["name"],
                ATTR_MODEL: data["system"]["model"],
                ATTR_SERIAL: data["system"]["serial_number"],
                ATTR_UPTIME: f"{days:0>2d}d {hours:0>2d}h {minutes:0>2d}m",
            }


class QNAPDriveSensor(QNAPSensor):
    """A QNAP sensor that monitors HDD/SSD drive stats."""

    @property
    def state(self):
        """Return the state of the sensor."""
        data = self.coordinator.data["smart_drive_health"][self.monitor_device]

        if self.var_id == "drive_smart_status":
            return data["health"]

        if self.var_id == "drive_temp":
            return int(data["temp_c"]) if data["temp_c"] is not None else 0

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        server_name = self.coordinator.data["system_stats"]["system"]["name"]

        return f"{server_name} {self.var_name} (Drive {self.monitor_device})"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            data = self.coordinator.data["smart_drive_health"][self.monitor_device]
            return {
                ATTR_DRIVE: data["drive_number"],
                ATTR_MODEL: data["model"],
                ATTR_SERIAL: data["serial"],
                ATTR_TYPE: data["type"],
            }


class QNAPVolumeSensor(QNAPSensor):
    """A QNAP sensor that monitors storage volume stats."""

    @property
    def state(self):
        """Return the state of the sensor."""
        data = self.coordinator.data["volumes"][self.monitor_device]

        free_gb = int(data["free_size"]) / 1024 / 1024 / 1024
        if self.var_id == "volume_size_free":
            return round_nicely(free_gb)

        total_gb = int(data["total_size"]) / 1024 / 1024 / 1024

        used_gb = total_gb - free_gb
        if self.var_id == "volume_size_used":
            return round_nicely(used_gb)

        if self.var_id == "volume_percentage_used":
            return round(used_gb / total_gb * 100)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            data = self.coordinator.data["volumes"][self.monitor_device]
            total_gb = int(data["total_size"]) / 1024 / 1024 / 1024

            return {ATTR_VOLUME_SIZE: f"{round_nicely(total_gb)} {DATA_GIBIBYTES}"}
