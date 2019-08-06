"""
Measurement channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging

import zigpy.zcl.clusters.measurement as measurement

from . import ZIGBEE_CHANNEL_REGISTRY, AttributeListeningChannel
from ..const import (
    REPORT_CONFIG_DEFAULT,
    REPORT_CONFIG_IMMEDIATE,
    REPORT_CONFIG_MAX_INT,
    REPORT_CONFIG_MIN_INT,
)

_LOGGER = logging.getLogger(__name__)


@ZIGBEE_CHANNEL_REGISTRY.register
class FlowMeasurement(AttributeListeningChannel):
    """Flow Measurement channel."""

    CLUSTER_ID = measurement.FlowMeasurement.cluster_id
    REPORT_CONFIG = [{"attr": "measured_value", "config": REPORT_CONFIG_DEFAULT}]


@ZIGBEE_CHANNEL_REGISTRY.register
class IlluminanceLevelSensing(AttributeListeningChannel):
    """Illuminance Level Sensing channel."""

    CLUSTER_ID = measurement.IlluminanceLevelSensing.cluster_id
    REPORT_CONFIG = [{"attr": "level_status", "config": REPORT_CONFIG_DEFAULT}]


@ZIGBEE_CHANNEL_REGISTRY.register
class IlluminanceMeasurement(AttributeListeningChannel):
    """Illuminance Measurement channel."""

    CLUSTER_ID = measurement.IlluminanceMeasurement.cluster_id
    REPORT_CONFIG = [{"attr": "measured_value", "config": REPORT_CONFIG_DEFAULT}]


@ZIGBEE_CHANNEL_REGISTRY.register
class OccupancySensing(AttributeListeningChannel):
    """Occupancy Sensing channel."""

    CLUSTER_ID = measurement.OccupancySensing.cluster_id
    REPORT_CONFIG = [{"attr": "occupancy", "config": REPORT_CONFIG_IMMEDIATE}]


@ZIGBEE_CHANNEL_REGISTRY.register
class PressureMeasurement(AttributeListeningChannel):
    """Pressure measurement channel."""

    CLUSTER_ID = measurement.PressureMeasurement.cluster_id
    REPORT_CONFIG = [{"attr": "measured_value", "config": REPORT_CONFIG_DEFAULT}]


@ZIGBEE_CHANNEL_REGISTRY.register
class RelativeHumidity(AttributeListeningChannel):
    """Relative Humidity measurement channel."""

    CLUSTER_ID = measurement.RelativeHumidity.cluster_id
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 50),
        }
    ]


@ZIGBEE_CHANNEL_REGISTRY.register
class TemperatureMeasurement(AttributeListeningChannel):
    """Temperature measurement channel."""

    CLUSTER_ID = measurement.TemperatureMeasurement.cluster_id
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 50),
        }
    ]
