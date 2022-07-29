"""Constants for Glances component."""
from __future__ import annotations

from dataclasses import dataclass
import sys

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import DATA_GIBIBYTES, DATA_MEBIBYTES, PERCENTAGE, TEMP_CELSIUS

DOMAIN = "glances"
CONF_VERSION = "version"

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "Glances"
DEFAULT_PORT = 61208
DEFAULT_VERSION = 3
DEFAULT_SCAN_INTERVAL = 60

DATA_UPDATED = "glances_data_updated"
SUPPORTED_VERSIONS = [2, 3]

if sys.maxsize > 2**32:
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
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="disk_use",
        type="fs",
        name_suffix="used",
        native_unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="disk_free",
        type="fs",
        name_suffix="free",
        native_unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="memory_use_percent",
        type="mem",
        name_suffix="RAM used percent",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="memory_use",
        type="mem",
        name_suffix="RAM used",
        native_unit_of_measurement=DATA_MEBIBYTES,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="memory_free",
        type="mem",
        name_suffix="RAM free",
        native_unit_of_measurement=DATA_MEBIBYTES,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="swap_use_percent",
        type="memswap",
        name_suffix="Swap used percent",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="swap_use",
        type="memswap",
        name_suffix="Swap used",
        native_unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="swap_free",
        type="memswap",
        name_suffix="Swap free",
        native_unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="processor_load",
        type="load",
        name_suffix="CPU load",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="process_running",
        type="processcount",
        name_suffix="Running",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="process_total",
        type="processcount",
        name_suffix="Total",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="process_thread",
        type="processcount",
        name_suffix="Thread",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="process_sleeping",
        type="processcount",
        name_suffix="Sleeping",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="cpu_use_percent",
        type="cpu",
        name_suffix="CPU used",
        native_unit_of_measurement=PERCENTAGE,
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="temperature_core",
        type="sensors",
        name_suffix="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="temperature_hdd",
        type="sensors",
        name_suffix="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="fan_speed",
        type="sensors",
        name_suffix="Fan speed",
        native_unit_of_measurement="RPM",
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="battery",
        type="sensors",
        name_suffix="Charge",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="docker_active",
        type="docker",
        name_suffix="Containers active",
        icon="mdi:docker",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="docker_cpu_use",
        type="docker",
        name_suffix="Containers CPU used",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:docker",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="docker_memory_use",
        type="docker",
        name_suffix="Containers RAM used",
        native_unit_of_measurement=DATA_MEBIBYTES,
        icon="mdi:docker",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="used",
        type="raid",
        name_suffix="Raid used",
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="available",
        type="raid",
        name_suffix="Raid available",
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)
