"""Measurement channels module for Zigbee Home Automation."""
from __future__ import annotations

from typing import TYPE_CHECKING

import zigpy.zcl
from zigpy.zcl.clusters import measurement

from .. import registries
from ..const import (
    REPORT_CONFIG_DEFAULT,
    REPORT_CONFIG_IMMEDIATE,
    REPORT_CONFIG_MAX_INT,
    REPORT_CONFIG_MIN_INT,
)
from .base import AttrReportConfig, ZigbeeChannel
from .helpers import is_hue_motion_sensor

if TYPE_CHECKING:
    from . import ChannelPool


@registries.ZIGBEE_CHANNEL_REGISTRY.register(measurement.FlowMeasurement.cluster_id)
class FlowMeasurement(ZigbeeChannel):
    """Flow Measurement channel."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="measured_value", config=REPORT_CONFIG_DEFAULT),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.IlluminanceLevelSensing.cluster_id
)
class IlluminanceLevelSensing(ZigbeeChannel):
    """Illuminance Level Sensing channel."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="level_status", config=REPORT_CONFIG_DEFAULT),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.IlluminanceMeasurement.cluster_id
)
class IlluminanceMeasurement(ZigbeeChannel):
    """Illuminance Measurement channel."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="measured_value", config=REPORT_CONFIG_DEFAULT),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(measurement.OccupancySensing.cluster_id)
class OccupancySensing(ZigbeeChannel):
    """Occupancy Sensing channel."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="occupancy", config=REPORT_CONFIG_IMMEDIATE),
    )

    def __init__(self, cluster: zigpy.zcl.Cluster, ch_pool: ChannelPool) -> None:
        """Initialize Occupancy channel."""
        super().__init__(cluster, ch_pool)
        if is_hue_motion_sensor(self):
            self.ZCL_INIT_ATTRS = (  # pylint: disable=invalid-name
                self.ZCL_INIT_ATTRS.copy()
            )
            self.ZCL_INIT_ATTRS["sensitivity"] = True


@registries.ZIGBEE_CHANNEL_REGISTRY.register(measurement.PressureMeasurement.cluster_id)
class PressureMeasurement(ZigbeeChannel):
    """Pressure measurement channel."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="measured_value", config=REPORT_CONFIG_DEFAULT),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(measurement.RelativeHumidity.cluster_id)
class RelativeHumidity(ZigbeeChannel):
    """Relative Humidity measurement channel."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 100),
        ),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(measurement.SoilMoisture.cluster_id)
class SoilMoisture(ZigbeeChannel):
    """Soil Moisture measurement channel."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 100),
        ),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(measurement.LeafWetness.cluster_id)
class LeafWetness(ZigbeeChannel):
    """Leaf Wetness measurement channel."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 100),
        ),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.TemperatureMeasurement.cluster_id
)
class TemperatureMeasurement(ZigbeeChannel):
    """Temperature measurement channel."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 50),
        ),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.CarbonMonoxideConcentration.cluster_id
)
class CarbonMonoxideConcentration(ZigbeeChannel):
    """Carbon Monoxide measurement channel."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        ),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.CarbonDioxideConcentration.cluster_id
)
class CarbonDioxideConcentration(ZigbeeChannel):
    """Carbon Dioxide measurement channel."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        ),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(measurement.PM25.cluster_id)
class PM25(ZigbeeChannel):
    """Particulate Matter 2.5 microns or less measurement channel."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.1),
        ),
    )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.FormaldehydeConcentration.cluster_id
)
class FormaldehydeConcentration(ZigbeeChannel):
    """Formaldehyde measurement channel."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        ),
    )
