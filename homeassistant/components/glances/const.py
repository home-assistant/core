"""Constants for Glances component."""
from __future__ import annotations

from dataclasses import dataclass
import sys

from homeassistant.components.sensor import SensorEntityDescription
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


@dataclass
class GlancesSensorEntityDescription(SensorEntityDescription):
    """Describe Glances sensor entity."""

    type: str | None = None
    name_suffix: str | None = None


SENSOR_TYPES: tuple[GlancesSensorEntityDescription, ...] = (
    GlancesSensorEntityDescription(
        key="disk_use_percent",
        type="fs",
        name_suffix="used percent",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:harddisk",
    ),
    GlancesSensorEntityDescription(
        key="disk_use",
        type="fs",
        name_suffix="used",
        unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:harddisk",
    ),
    GlancesSensorEntityDescription(
        key="disk_free",
        type="fs",
        name_suffix="free",
        unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:harddisk",
    ),
    GlancesSensorEntityDescription(
        key="memory_use_percent",
        type="mem",
        name_suffix="RAM used percent",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
    ),
    GlancesSensorEntityDescription(
        key="memory_use",
        type="mem",
        name_suffix="RAM used",
        unit_of_measurement=DATA_MEBIBYTES,
        icon="mdi:memory",
    ),
    GlancesSensorEntityDescription(
        key="memory_free",
        type="mem",
        name_suffix="RAM free",
        unit_of_measurement=DATA_MEBIBYTES,
        icon="mdi:memory",
    ),
    GlancesSensorEntityDescription(
        key="swap_use_percent",
        type="memswap",
        name_suffix="Swap used percent",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
    ),
    GlancesSensorEntityDescription(
        key="swap_use",
        type="memswap",
        name_suffix="Swap used",
        unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:memory",
    ),
    GlancesSensorEntityDescription(
        key="swap_free",
        type="memswap",
        name_suffix="Swap free",
        unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:memory",
    ),
    GlancesSensorEntityDescription(
        key="processor_load",
        type="load",
        name_suffix="CPU load",
        unit_of_measurement="15 min",
        icon=CPU_ICON,
    ),
    GlancesSensorEntityDescription(
        key="process_running",
        type="processcount",
        name_suffix="Running",
        unit_of_measurement="Count",
        icon=CPU_ICON,
    ),
    GlancesSensorEntityDescription(
        key="process_total",
        type="processcount",
        name_suffix="Total",
        unit_of_measurement="Count",
        icon=CPU_ICON,
    ),
    GlancesSensorEntityDescription(
        key="process_thread",
        type="processcount",
        name_suffix="Thread",
        unit_of_measurement="Count",
        icon=CPU_ICON,
    ),
    GlancesSensorEntityDescription(
        key="process_sleeping",
        type="processcount",
        name_suffix="Sleeping",
        unit_of_measurement="Count",
        icon=CPU_ICON,
    ),
    GlancesSensorEntityDescription(
        key="cpu_use_percent",
        type="cpu",
        name_suffix="CPU used",
        unit_of_measurement=PERCENTAGE,
        icon=CPU_ICON,
    ),
    GlancesSensorEntityDescription(
        key="temperature_core",
        type="sensors",
        name_suffix="Temperature",
        unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    GlancesSensorEntityDescription(
        key="temperature_hdd",
        type="sensors",
        name_suffix="Temperature",
        unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    GlancesSensorEntityDescription(
        key="fan_speed",
        type="sensors",
        name_suffix="Fan speed",
        unit_of_measurement="RPM",
        icon="mdi:fan",
    ),
    GlancesSensorEntityDescription(
        key="battery",
        type="sensors",
        name_suffix="Charge",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:battery",
    ),
    GlancesSensorEntityDescription(
        key="docker_active",
        type="docker",
        name_suffix="Containers active",
        unit_of_measurement="",
        icon="mdi:docker",
    ),
    GlancesSensorEntityDescription(
        key="docker_cpu_use",
        type="docker",
        name_suffix="Containers CPU used",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:docker",
    ),
    GlancesSensorEntityDescription(
        key="docker_memory_use",
        type="docker",
        name_suffix="Containers RAM used",
        unit_of_measurement=DATA_MEBIBYTES,
        icon="mdi:docker",
    ),
)
