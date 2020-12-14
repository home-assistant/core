"""Support for monitoring the local system."""
import logging
import os
import socket
import sys

import psutil
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_RESOURCES,
    CONF_TYPE,
    DATA_GIBIBYTES,
    DATA_MEBIBYTES,
    DATA_RATE_MEGABYTES_PER_SECOND,
    PERCENTAGE,
    STATE_OFF,
    STATE_ON,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

CONF_ARG = "arg"

if sys.maxsize > 2 ** 32:
    CPU_ICON = "mdi:cpu-64-bit"
else:
    CPU_ICON = "mdi:cpu-32-bit"

# Schema: [name, unit of measurement, icon, device class, flag if mandatory arg]
SENSOR_TYPES = {
    "disk_free": ["Disk free", DATA_GIBIBYTES, "mdi:harddisk", None, False],
    "disk_use": ["Disk use", DATA_GIBIBYTES, "mdi:harddisk", None, False],
    "disk_use_percent": [
        "Disk use (percent)",
        PERCENTAGE,
        "mdi:harddisk",
        None,
        False,
    ],
    "ipv4_address": ["IPv4 address", "", "mdi:server-network", None, True],
    "ipv6_address": ["IPv6 address", "", "mdi:server-network", None, True],
    "last_boot": ["Last boot", "", "mdi:clock", "timestamp", False],
    "load_15m": ["Load (15m)", " ", CPU_ICON, None, False],
    "load_1m": ["Load (1m)", " ", CPU_ICON, None, False],
    "load_5m": ["Load (5m)", " ", CPU_ICON, None, False],
    "memory_free": ["Memory free", DATA_MEBIBYTES, "mdi:memory", None, False],
    "memory_use": ["Memory use", DATA_MEBIBYTES, "mdi:memory", None, False],
    "memory_use_percent": [
        "Memory use (percent)",
        PERCENTAGE,
        "mdi:memory",
        None,
        False,
    ],
    "network_in": ["Network in", DATA_MEBIBYTES, "mdi:server-network", None, True],
    "network_out": ["Network out", DATA_MEBIBYTES, "mdi:server-network", None, True],
    "packets_in": ["Packets in", " ", "mdi:server-network", None, True],
    "packets_out": ["Packets out", " ", "mdi:server-network", None, True],
    "throughput_network_in": [
        "Network throughput in",
        DATA_RATE_MEGABYTES_PER_SECOND,
        "mdi:server-network",
        None,
        True,
    ],
    "throughput_network_out": [
        "Network throughput out",
        DATA_RATE_MEGABYTES_PER_SECOND,
        "mdi:server-network",
        True,
    ],
    "process": ["Process", " ", CPU_ICON, None, True],
    "processor_use": ["Processor use (percent)", PERCENTAGE, CPU_ICON, None, False],
    "processor_temperature": [
        "Processor temperature",
        TEMP_CELSIUS,
        CPU_ICON,
        None,
        False,
    ],
    "swap_free": ["Swap free", DATA_MEBIBYTES, "mdi:harddisk", None, False],
    "swap_use": ["Swap use", DATA_MEBIBYTES, "mdi:harddisk", None, False],
    "swap_use_percent": ["Swap use (percent)", PERCENTAGE, "mdi:harddisk", None, False],
}


def check_required_arg(value):
    """Validate that the required "arg" for the sensor types that need it are set."""
    for sensor in value:
        sensor_type = sensor[CONF_TYPE]
        sensor_arg = sensor.get(CONF_ARG)

        if sensor_arg is None and SENSOR_TYPES[sensor_type][4]:
            raise vol.RequiredFieldInvalid(
                f"Mandatory 'arg' is missing for sensor type '{sensor_type}'."
            )

    return value


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_RESOURCES, default={CONF_TYPE: "disk_use"}): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_TYPE): vol.In(SENSOR_TYPES),
                        vol.Optional(CONF_ARG): cv.string,
                    }
                )
            ],
            check_required_arg,
        )
    }
)

IO_COUNTER = {
    "network_out": 0,
    "network_in": 1,
    "packets_out": 2,
    "packets_in": 3,
    "throughput_network_out": 0,
    "throughput_network_in": 1,
}

IF_ADDRS_FAMILY = {"ipv4_address": socket.AF_INET, "ipv6_address": socket.AF_INET6}

# There might be additional keys to be added for different
# platforms / hardware combinations.
# Taken from last version of "glances" integration before they moved to
# a generic temperature sensor logic.
# https://github.com/home-assistant/core/blob/5e15675593ba94a2c11f9f929cdad317e27ce190/homeassistant/components/glances/sensor.py#L199
CPU_SENSOR_PREFIXES = [
    "amdgpu 1",
    "aml_thermal",
    "Core 0",
    "Core 1",
    "CPU Temperature",
    "CPU",
    "cpu-thermal 1",
    "cpu_thermal 1",
    "exynos-therm 1",
    "Package id 0",
    "Physical id 0",
    "radeon 1",
    "soc-thermal 1",
    "soc_thermal 1",
]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the system monitor sensors."""
    dev = []
    for resource in config[CONF_RESOURCES]:
        # Initialize the sensor argument if none was provided.
        # For disk monitoring default to "/" (root) to prevent runtime errors, if argument was not specified.
        if CONF_ARG not in resource:
            if resource[CONF_TYPE].startswith("disk_"):
                resource[CONF_ARG] = "/"
            else:
                resource[CONF_ARG] = ""

        # Verify if we can retrieve CPU / processor temperatures.
        # If not, do not create the entity and add a warning to the log
        if resource[CONF_TYPE] == "processor_temperature":
            if SystemMonitorSensor.read_cpu_temperature() is None:
                _LOGGER.warning("Cannot read CPU / processor temperature information.")
                continue

        dev.append(SystemMonitorSensor(resource[CONF_TYPE], resource[CONF_ARG]))

    add_entities(dev, True)


class SystemMonitorSensor(Entity):
    """Implementation of a system monitor sensor."""

    def __init__(self, sensor_type, argument=""):
        """Initialize the sensor."""
        self._name = "{} {}".format(SENSOR_TYPES[sensor_type][0], argument)
        self._unique_id = slugify(f"{sensor_type}_{argument}")
        self.argument = argument
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._available = True
        if sensor_type in ["throughput_network_out", "throughput_network_in"]:
            self._last_value = None
            self._last_update_time = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name.rstrip()

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._unique_id

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return SENSOR_TYPES[self.type][3]

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.type][2]

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
        """Get the latest system information."""
        if self.type == "disk_use_percent":
            self._state = psutil.disk_usage(self.argument).percent
        elif self.type == "disk_use":
            self._state = round(psutil.disk_usage(self.argument).used / 1024 ** 3, 1)
        elif self.type == "disk_free":
            self._state = round(psutil.disk_usage(self.argument).free / 1024 ** 3, 1)
        elif self.type == "memory_use_percent":
            self._state = psutil.virtual_memory().percent
        elif self.type == "memory_use":
            virtual_memory = psutil.virtual_memory()
            self._state = round(
                (virtual_memory.total - virtual_memory.available) / 1024 ** 2, 1
            )
        elif self.type == "memory_free":
            self._state = round(psutil.virtual_memory().available / 1024 ** 2, 1)
        elif self.type == "swap_use_percent":
            self._state = psutil.swap_memory().percent
        elif self.type == "swap_use":
            self._state = round(psutil.swap_memory().used / 1024 ** 2, 1)
        elif self.type == "swap_free":
            self._state = round(psutil.swap_memory().free / 1024 ** 2, 1)
        elif self.type == "processor_use":
            self._state = round(psutil.cpu_percent(interval=None))
        elif self.type == "processor_temperature":
            self._state = self.read_cpu_temperature()
        elif self.type == "process":
            for proc in psutil.process_iter():
                try:
                    if self.argument == proc.name():
                        self._state = STATE_ON
                        return
                except psutil.NoSuchProcess as err:
                    _LOGGER.warning(
                        "Failed to load process with id: %s, old name: %s",
                        err.pid,
                        err.name,
                    )
            self._state = STATE_OFF
        elif self.type == "network_out" or self.type == "network_in":
            counters = psutil.net_io_counters(pernic=True)
            if self.argument in counters:
                counter = counters[self.argument][IO_COUNTER[self.type]]
                self._state = round(counter / 1024 ** 2, 1)
            else:
                self._state = None
        elif self.type == "packets_out" or self.type == "packets_in":
            counters = psutil.net_io_counters(pernic=True)
            if self.argument in counters:
                self._state = counters[self.argument][IO_COUNTER[self.type]]
            else:
                self._state = None
        elif (
            self.type == "throughput_network_out"
            or self.type == "throughput_network_in"
        ):
            counters = psutil.net_io_counters(pernic=True)
            if self.argument in counters:
                counter = counters[self.argument][IO_COUNTER[self.type]]
                now = dt_util.utcnow()
                if self._last_value and self._last_value < counter:
                    self._state = round(
                        (counter - self._last_value)
                        / 1000 ** 2
                        / (now - self._last_update_time).seconds,
                        3,
                    )
                else:
                    self._state = None
                self._last_update_time = now
                self._last_value = counter
            else:
                self._state = None
        elif self.type == "ipv4_address" or self.type == "ipv6_address":
            addresses = psutil.net_if_addrs()
            if self.argument in addresses:
                for addr in addresses[self.argument]:
                    if addr.family == IF_ADDRS_FAMILY[self.type]:
                        self._state = addr.address
            else:
                self._state = None
        elif self.type == "last_boot":
            self._state = dt_util.as_local(
                dt_util.utc_from_timestamp(psutil.boot_time())
            ).isoformat()
        elif self.type == "load_1m":
            self._state = round(os.getloadavg()[0], 2)
        elif self.type == "load_5m":
            self._state = round(os.getloadavg()[1], 2)
        elif self.type == "load_15m":
            self._state = round(os.getloadavg()[2], 2)

    @staticmethod
    def read_cpu_temperature():
        """Attempt to read CPU / processor temperature."""
        temps = psutil.sensors_temperatures()

        for name, entries in temps.items():
            i = 1
            for entry in entries:
                # In case the label is empty (e.g. on Raspberry PI 4),
                # construct it ourself here based on the sensor key name.
                if not entry.label:
                    _label = f"{name} {i}"
                else:
                    _label = entry.label

                if _label in CPU_SENSOR_PREFIXES:
                    return round(entry.current, 1)

                i += 1
