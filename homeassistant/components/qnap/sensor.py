"""Support for QNAP NAS Sensors."""
from datetime import timedelta
import logging

from qnapstats import QNAPStats
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_NAME,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DATA_GIBIBYTES,
    DATA_RATE_MEBIBYTES_PER_SECOND,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

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

CONF_DRIVES = "drives"
CONF_NICS = "nics"
CONF_VOLUMES = "volumes"
DEFAULT_NAME = "QNAP"
DEFAULT_PORT = 8080
DEFAULT_TIMEOUT = 5

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

NOTIFICATION_ID = "qnap_notification"
NOTIFICATION_TITLE = "QNAP Sensor Setup"

_SYSTEM_MON_COND = {
    "status": ["Status", None, "mdi:checkbox-marked-circle-outline"],
    "system_temp": ["System Temperature", TEMP_CELSIUS, "mdi:thermometer"],
}
_CPU_MON_COND = {
    "cpu_temp": ["CPU Temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "cpu_usage": ["CPU Usage", PERCENTAGE, "mdi:chip"],
}
_MEMORY_MON_COND = {
    "memory_free": ["Memory Available", DATA_GIBIBYTES, "mdi:memory"],
    "memory_used": ["Memory Used", DATA_GIBIBYTES, "mdi:memory"],
    "memory_percent_used": ["Memory Usage", PERCENTAGE, "mdi:memory"],
}
_NETWORK_MON_COND = {
    "network_link_status": ["Network Link", None, "mdi:checkbox-marked-circle-outline"],
    "network_tx": ["Network Up", DATA_RATE_MEBIBYTES_PER_SECOND, "mdi:upload"],
    "network_rx": ["Network Down", DATA_RATE_MEBIBYTES_PER_SECOND, "mdi:download"],
}
_DRIVE_MON_COND = {
    "drive_smart_status": ["SMART Status", None, "mdi:checkbox-marked-circle-outline"],
    "drive_temp": ["Temperature", TEMP_CELSIUS, "mdi:thermometer"],
}
_VOLUME_MON_COND = {
    "volume_size_used": ["Used Space", DATA_GIBIBYTES, "mdi:chart-pie"],
    "volume_size_free": ["Free Space", DATA_GIBIBYTES, "mdi:chart-pie"],
    "volume_percentage_used": ["Volume Used", PERCENTAGE, "mdi:chart-pie"],
}

_MONITORED_CONDITIONS = (
    list(_SYSTEM_MON_COND)
    + list(_CPU_MON_COND)
    + list(_MEMORY_MON_COND)
    + list(_NETWORK_MON_COND)
    + list(_DRIVE_MON_COND)
    + list(_VOLUME_MON_COND)
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS): vol.All(
            cv.ensure_list, [vol.In(_MONITORED_CONDITIONS)]
        ),
        vol.Optional(CONF_NICS): cv.ensure_list,
        vol.Optional(CONF_DRIVES): cv.ensure_list,
        vol.Optional(CONF_VOLUMES): cv.ensure_list,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the QNAP NAS sensor."""
    api = QNAPStatsAPI(config)
    api.update()

    # QNAP is not available
    if not api.data:
        raise PlatformNotReady

    sensors = []

    # Basic sensors
    for variable in config[CONF_MONITORED_CONDITIONS]:
        if variable in _SYSTEM_MON_COND:
            sensors.append(QNAPSystemSensor(api, variable, _SYSTEM_MON_COND[variable]))
        if variable in _CPU_MON_COND:
            sensors.append(QNAPCPUSensor(api, variable, _CPU_MON_COND[variable]))
        if variable in _MEMORY_MON_COND:
            sensors.append(QNAPMemorySensor(api, variable, _MEMORY_MON_COND[variable]))

    # Network sensors
    for nic in config.get(CONF_NICS, api.data["system_stats"]["nics"]):
        sensors += [
            QNAPNetworkSensor(api, variable, _NETWORK_MON_COND[variable], nic)
            for variable in config[CONF_MONITORED_CONDITIONS]
            if variable in _NETWORK_MON_COND
        ]

    # Drive sensors
    for drive in config.get(CONF_DRIVES, api.data["smart_drive_health"]):
        sensors += [
            QNAPDriveSensor(api, variable, _DRIVE_MON_COND[variable], drive)
            for variable in config[CONF_MONITORED_CONDITIONS]
            if variable in _DRIVE_MON_COND
        ]

    # Volume sensors
    for volume in config.get(CONF_VOLUMES, api.data["volumes"]):
        sensors += [
            QNAPVolumeSensor(api, variable, _VOLUME_MON_COND[variable], volume)
            for variable in config[CONF_MONITORED_CONDITIONS]
            if variable in _VOLUME_MON_COND
        ]

    add_entities(sensors)


def round_nicely(number):
    """Round a number based on its size (so it looks nice)."""
    if number < 10:
        return round(number, 2)
    if number < 100:
        return round(number, 1)

    return round(number)


class QNAPStatsAPI:
    """Class to interface with the API."""

    def __init__(self, config):
        """Initialize the API wrapper."""

        protocol = "https" if config[CONF_SSL] else "http"
        self._api = QNAPStats(
            f"{protocol}://{config.get(CONF_HOST)}",
            config.get(CONF_PORT),
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
            verify_ssl=config.get(CONF_VERIFY_SSL),
            timeout=config.get(CONF_TIMEOUT),
        )

        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update API information and store locally."""
        try:
            self.data["system_stats"] = self._api.get_system_stats()
            self.data["system_health"] = self._api.get_system_health()
            self.data["smart_drive_health"] = self._api.get_smart_disk_health()
            self.data["volumes"] = self._api.get_volumes()
            self.data["bandwidth"] = self._api.get_bandwidth()
        except:  # noqa: E722 pylint: disable=bare-except
            _LOGGER.exception("Failed to fetch QNAP stats from the NAS")


class QNAPSensor(Entity):
    """Base class for a QNAP sensor."""

    def __init__(self, api, variable, variable_info, monitor_device=None):
        """Initialize the sensor."""
        self.var_id = variable
        self.var_name = variable_info[0]
        self.var_units = variable_info[1]
        self.var_icon = variable_info[2]
        self.monitor_device = monitor_device
        self._api = api

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        server_name = self._api.data["system_stats"]["system"]["name"]

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

    def update(self):
        """Get the latest data for the states."""
        self._api.update()


class QNAPCPUSensor(QNAPSensor):
    """A QNAP sensor that monitors CPU stats."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.var_id == "cpu_temp":
            return self._api.data["system_stats"]["cpu"]["temp_c"]
        if self.var_id == "cpu_usage":
            return self._api.data["system_stats"]["cpu"]["usage_percent"]


class QNAPMemorySensor(QNAPSensor):
    """A QNAP sensor that monitors memory stats."""

    @property
    def state(self):
        """Return the state of the sensor."""
        free = float(self._api.data["system_stats"]["memory"]["free"]) / 1024
        if self.var_id == "memory_free":
            return round_nicely(free)

        total = float(self._api.data["system_stats"]["memory"]["total"]) / 1024

        used = total - free
        if self.var_id == "memory_used":
            return round_nicely(used)

        if self.var_id == "memory_percent_used":
            return round(used / total * 100)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._api.data:
            data = self._api.data["system_stats"]["memory"]
            size = round_nicely(float(data["total"]) / 1024)
            return {ATTR_MEMORY_SIZE: f"{size} {DATA_GIBIBYTES}"}


class QNAPNetworkSensor(QNAPSensor):
    """A QNAP sensor that monitors network stats."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.var_id == "network_link_status":
            nic = self._api.data["system_stats"]["nics"][self.monitor_device]
            return nic["link_status"]

        data = self._api.data["bandwidth"][self.monitor_device]
        if self.var_id == "network_tx":
            return round_nicely(data["tx"] / 1024 / 1024)

        if self.var_id == "network_rx":
            return round_nicely(data["rx"] / 1024 / 1024)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._api.data:
            data = self._api.data["system_stats"]["nics"][self.monitor_device]
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
            return self._api.data["system_health"]

        if self.var_id == "system_temp":
            return int(self._api.data["system_stats"]["system"]["temp_c"])

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._api.data:
            data = self._api.data["system_stats"]
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
        data = self._api.data["smart_drive_health"][self.monitor_device]

        if self.var_id == "drive_smart_status":
            return data["health"]

        if self.var_id == "drive_temp":
            return int(data["temp_c"]) if data["temp_c"] is not None else 0

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        server_name = self._api.data["system_stats"]["system"]["name"]

        return f"{server_name} {self.var_name} (Drive {self.monitor_device})"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._api.data:
            data = self._api.data["smart_drive_health"][self.monitor_device]
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
        data = self._api.data["volumes"][self.monitor_device]

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
        if self._api.data:
            data = self._api.data["volumes"][self.monitor_device]
            total_gb = int(data["total_size"]) / 1024 / 1024 / 1024

            return {ATTR_VOLUME_SIZE: f"{round_nicely(total_gb)} {DATA_GIBIBYTES}"}
