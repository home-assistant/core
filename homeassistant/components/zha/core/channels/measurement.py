"""Measurement channels module for Zigbee Home Automation."""
import zigpy.zcl.clusters.measurement as measurement

from .. import registries
from ..const import (
    REPORT_CONFIG_DEFAULT,
    REPORT_CONFIG_IMMEDIATE,
    REPORT_CONFIG_MAX_INT,
    REPORT_CONFIG_MIN_INT,
)
from .base import ZigbeeChannel


@registries.ZIGBEE_CHANNEL_REGISTRY.register(measurement.FlowMeasurement.cluster_id)
class FlowMeasurement(ZigbeeChannel):
    """Flow Measurement channel."""

    REPORT_CONFIG = [{"attr": "measured_value", "config": REPORT_CONFIG_DEFAULT}]


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.IlluminanceLevelSensing.cluster_id
)
class IlluminanceLevelSensing(ZigbeeChannel):
    """Illuminance Level Sensing channel."""

    REPORT_CONFIG = [{"attr": "level_status", "config": REPORT_CONFIG_DEFAULT}]


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.IlluminanceMeasurement.cluster_id
)
class IlluminanceMeasurement(ZigbeeChannel):
    """Illuminance Measurement channel."""

    REPORT_CONFIG = [{"attr": "measured_value", "config": REPORT_CONFIG_DEFAULT}]


@registries.BINARY_SENSOR_CLUSTERS.register(measurement.OccupancySensing.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(measurement.OccupancySensing.cluster_id)
class OccupancySensing(ZigbeeChannel):
    """Occupancy Sensing channel."""

    REPORT_CONFIG = [{"attr": "occupancy", "config": REPORT_CONFIG_IMMEDIATE}]


@registries.ZIGBEE_CHANNEL_REGISTRY.register(measurement.PressureMeasurement.cluster_id)
class PressureMeasurement(ZigbeeChannel):
    """Pressure measurement channel."""

    REPORT_CONFIG = [{"attr": "measured_value", "config": REPORT_CONFIG_DEFAULT}]


@registries.ZIGBEE_CHANNEL_REGISTRY.register(measurement.RelativeHumidity.cluster_id)
class RelativeHumidity(ZigbeeChannel):
    """Relative Humidity measurement channel."""

    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 50),
        }
    ]


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.TemperatureMeasurement.cluster_id
)
class TemperatureMeasurement(ZigbeeChannel):
    """Temperature measurement channel."""

    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 50),
        }
    ]
