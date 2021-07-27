"""Constants for Glances component."""
from __future__ import annotations

import sys
from typing import NamedTuple

from homeassistant.const import (
    DATA_GIBIBYTES,
    DATA_MEBIBYTES,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)

DOMAIN = "glances"
CONF_VERSION = "version"

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "Glances"
DEFAULT_PORT = 61208
DEFAULT_VERSION = 3
DEFAULT_SCAN_INTERVAL = 60

DATA_UPDATED = "glances_data_updated"
SUPPORTED_VERSIONS = [2, 3]

if sys.maxsize > 2 ** 32:
    CPU_ICON = "mdi:cpu-64-bit"
else:
    CPU_ICON = "mdi:cpu-32-bit"


class GlancesSensorMetadata(NamedTuple):
    """Sensor metadata for an individual Glances sensor."""

    type: str
    name_suffix: str
    unit_of_measurement: str
    icon: str | None = None
    device_class: str | None = None


SENSOR_TYPES: dict[str, GlancesSensorMetadata] = {
    "disk_use_percent": GlancesSensorMetadata(
        type="fs",
        name_suffix="used percent",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:harddisk",
    ),
    "disk_use": GlancesSensorMetadata(
        type="fs",
        name_suffix="used",
        unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:harddisk",
    ),
    "disk_free": GlancesSensorMetadata(
        type="fs",
        name_suffix="free",
        unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:harddisk",
    ),
    "memory_use_percent": GlancesSensorMetadata(
        type="mem",
        name_suffix="RAM used percent",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
    ),
    "memory_use": GlancesSensorMetadata(
        type="mem",
        name_suffix="RAM used",
        unit_of_measurement=DATA_MEBIBYTES,
        icon="mdi:memory",
    ),
    "memory_free": GlancesSensorMetadata(
        type="mem",
        name_suffix="RAM free",
        unit_of_measurement=DATA_MEBIBYTES,
        icon="mdi:memory",
    ),
    "swap_use_percent": GlancesSensorMetadata(
        type="memswap",
        name_suffix="Swap used percent",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
    ),
    "swap_use": GlancesSensorMetadata(
        type="memswap",
        name_suffix="Swap used",
        unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:memory",
    ),
    "swap_free": GlancesSensorMetadata(
        type="memswap",
        name_suffix="Swap free",
        unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:memory",
    ),
    "processor_load": GlancesSensorMetadata(
        type="load",
        name_suffix="CPU load",
        unit_of_measurement="15 min",
        icon=CPU_ICON,
    ),
    "process_running": GlancesSensorMetadata(
        type="processcount",
        name_suffix="Running",
        unit_of_measurement="Count",
        icon=CPU_ICON,
    ),
    "process_total": GlancesSensorMetadata(
        type="processcount",
        name_suffix="Total",
        unit_of_measurement="Count",
        icon=CPU_ICON,
    ),
    "process_thread": GlancesSensorMetadata(
        type="processcount",
        name_suffix="Thread",
        unit_of_measurement="Count",
        icon=CPU_ICON,
    ),
    "process_sleeping": GlancesSensorMetadata(
        type="processcount",
        name_suffix="Sleeping",
        unit_of_measurement="Count",
        icon=CPU_ICON,
    ),
    "cpu_use_percent": GlancesSensorMetadata(
        type="cpu",
        name_suffix="CPU used",
        unit_of_measurement=PERCENTAGE,
        icon=CPU_ICON,
    ),
    "temperature_core": GlancesSensorMetadata(
        type="sensors",
        name_suffix="Temperature",
        unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    "temperature_hdd": GlancesSensorMetadata(
        type="sensors",
        name_suffix="Temperature",
        unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    "fan_speed": GlancesSensorMetadata(
        type="sensors",
        name_suffix="Fan speed",
        unit_of_measurement="RPM",
        icon="mdi:fan",
    ),
    "battery": GlancesSensorMetadata(
        type="sensors",
        name_suffix="Charge",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:battery",
    ),
    "docker_active": GlancesSensorMetadata(
        type="docker",
        name_suffix="Containers active",
        unit_of_measurement="",
        icon="mdi:docker",
    ),
    "docker_cpu_use": GlancesSensorMetadata(
        type="docker",
        name_suffix="Containers CPU used",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:docker",
    ),
    "docker_memory_use": GlancesSensorMetadata(
        type="docker",
        name_suffix="Containers RAM used",
        unit_of_measurement=DATA_MEBIBYTES,
        icon="mdi:docker",
    ),
}
