"""Support for monitoring the local system."""
from __future__ import annotations

import asyncio
import datetime
import logging
import os
import socket
import sys
from typing import Any, TypedDict

import psutil
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_RESOURCES,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
    DATA_GIBIBYTES,
    DATA_MEBIBYTES,
    DATA_RATE_MEGABYTES_PER_SECOND,
    DEVICE_CLASS_TIMESTAMP,
    EVENT_HOMEASSISTANT_STOP,
    PERCENTAGE,
    STATE_OFF,
    STATE_ON,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.event import async_track_time_interval
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
    "last_boot": ["Last boot", None, "mdi:clock", DEVICE_CLASS_TIMESTAMP, False],
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


class SensorData(TypedDict):
    """Data for a sensor."""

    argument: Any
    state: str | None
    value: Any | None
    update_time: datetime.datetime | None
    last_exception: BaseException | None


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the system monitor sensors."""
    entities = []
    sensor_registry: dict[str, SensorData] = {}

    for resource in config[CONF_RESOURCES]:
        type_ = resource[CONF_TYPE]
        # Initialize the sensor argument if none was provided.
        # For disk monitoring default to "/" (root) to prevent runtime errors, if argument was not specified.
        if CONF_ARG not in resource:
            argument = ""
            if resource[CONF_TYPE].startswith("disk_"):
                argument = "/"
        else:
            argument = resource[CONF_ARG]

        # Verify if we can retrieve CPU / processor temperatures.
        # If not, do not create the entity and add a warning to the log
        if (
            type_ == "processor_temperature"
            and await hass.async_add_executor_job(_read_cpu_temperature) is None
        ):
            _LOGGER.warning("Cannot read CPU / processor temperature information")
            continue

        sensor_registry[type_] = SensorData(
            {
                "argument": argument,
                "state": None,
                "value": None,
                "update_time": None,
                "last_exception": None,
            }
        )
        entities.append(SystemMonitorSensor(sensor_registry, type_, argument))

    scan_interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    await async_setup_sensor_registry_updates(hass, sensor_registry, scan_interval)

    async_add_entities(entities)


async def async_setup_sensor_registry_updates(hass, sensor_registry, scan_interval):
    """Update the registry and create polling."""

    _update_lock = asyncio.Lock()

    def _update_sensors():
        """Update sensors and store the result in the registry."""
        for type_, data in sensor_registry.items():
            try:
                state, value, update_time = _update(
                    type_, data.argument, data.state, data.value, data.update_time
                )
            except Exception as ex:  # pylint: disable=broad-except
                data.last_exception = ex
            else:
                data.state = state
                data.value = value
                data.update_time = update_time
                data.last_exception = None

    async def async_update_data():
        """Update all sensors in one executor jump."""
        if _update_lock.locked():
            _LOGGER.warning(
                "Updating systemmitnor took longer than the scheduled update interval %s",
                scan_interval,
            )
            return

        async with _update_lock:
            await hass.async_add_executor_job(_update_sensors)

    polling_interval_remover = async_track_time_interval(
        hass, async_update_data, scan_interval
    )

    @callback
    def _async_stop_polling(*_):
        polling_interval_remover()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_polling)


class SystemMonitorSensor(SensorEntity):
    """Implementation of a system monitor sensor."""

    def __init__(self, sensor_registry, sensor_type, argument=""):
        """Initialize the sensor."""
        self._name = "{} {}".format(SENSOR_TYPES[sensor_type][0], argument)
        self._unique_id = slugify(f"{sensor_type}_{argument}")
        self._sensor_registry = sensor_registry
        self._type = sensor_type
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

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
        return SENSOR_TYPES[self._type][3]

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self._type][2]

    @property
    def state(self):
        """Return the state of the device."""
        return self.data.state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def available(self):
        """Return True if entity is available."""
        return self.data.last_exception is None

    @property
    def data(self):
        """Return registry entry for the data."""
        return self._sensor_registry[self._type]


def _update(type_, argument, last_state, last_value, last_update_time):
    """Get the latest system information."""
    state = None
    value = None
    update_time = None

    if type_ == "disk_use_percent":
        state = psutil.disk_usage(argument).percent
    elif type_ == "disk_use":
        state = round(psutil.disk_usage(argument).used / 1024 ** 3, 1)
    elif type_ == "disk_free":
        state = round(psutil.disk_usage(argument).free / 1024 ** 3, 1)
    elif type_ == "memory_use_percent":
        state = psutil.virtual_memory().percent
    elif type_ == "memory_use":
        virtual_memory = psutil.virtual_memory()
        state = round((virtual_memory.total - virtual_memory.available) / 1024 ** 2, 1)
    elif type_ == "memory_free":
        state = round(psutil.virtual_memory().available / 1024 ** 2, 1)
    elif type_ == "swap_use_percent":
        state = psutil.swap_memory().percent
    elif type_ == "swap_use":
        state = round(psutil.swap_memory().used / 1024 ** 2, 1)
    elif type_ == "swap_free":
        state = round(psutil.swap_memory().free / 1024 ** 2, 1)
    elif type_ == "processor_use":
        state = round(psutil.cpu_percent(interval=None))
    elif type_ == "processor_temperature":
        state = _read_cpu_temperature()
    elif type_ == "process":
        for proc in psutil.process_iter():
            try:
                if argument == proc.name():
                    state = STATE_ON
                    return
            except psutil.NoSuchProcess as err:
                _LOGGER.warning(
                    "Failed to load process with ID: %s, old name: %s",
                    err.pid,
                    err.name,
                )
        state = STATE_OFF
    elif type_ in ["network_out", "network_in"]:
        counters = psutil.net_io_counters(pernic=True)
        if argument in counters:
            counter = counters[argument][IO_COUNTER[type_]]
            state = round(counter / 1024 ** 2, 1)
        else:
            state = None
    elif type_ in ["packets_out", "packets_in"]:
        counters = psutil.net_io_counters(pernic=True)
        if argument in counters:
            state = counters[argument][IO_COUNTER[type_]]
        else:
            state = None
    elif type_ in ["throughput_network_out", "throughput_network_in"]:
        counters = psutil.net_io_counters(pernic=True)
        if argument in counters:
            counter = counters[argument][IO_COUNTER[type_]]
            now = dt_util.utcnow()
            if last_value and last_value < counter:
                state = round(
                    (counter - last_value)
                    / 1000 ** 2
                    / (now - last_update_time).seconds,
                    3,
                )
            else:
                state = None
            update_time = now
            value = counter
        else:
            state = None
    elif type_ in ["ipv4_address", "ipv6_address"]:
        addresses = psutil.net_if_addrs()
        if argument in addresses:
            for addr in addresses[argument]:
                if addr.family == IF_ADDRS_FAMILY[type_]:
                    state = addr.address
        else:
            state = None
    elif type_ == "last_boot":
        # Only update on initial setup
        if last_state is None:
            state = dt_util.as_local(
                dt_util.utc_from_timestamp(psutil.boot_time())
            ).isoformat()
    elif type_ == "load_1m":
        state = round(os.getloadavg()[0], 2)
    elif type_ == "load_5m":
        state = round(os.getloadavg()[1], 2)
    elif type_ == "load_15m":
        state = round(os.getloadavg()[2], 2)

    return state, value, update_time


def _read_cpu_temperature():
    """Attempt to read CPU / processor temperature."""
    temps = psutil.sensors_temperatures()

    for name, entries in temps.items():
        for i, entry in enumerate(entries, start=1):
            # In case the label is empty (e.g. on Raspberry PI 4),
            # construct it ourself here based on the sensor key name.
            _label = f"{name} {i}" if not entry.label else entry.label
            if _label in CPU_SENSOR_PREFIXES:
                return round(entry.current, 1)
