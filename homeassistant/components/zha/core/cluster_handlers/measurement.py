"""Measurement cluster handlers module for Zigbee Home Automation."""
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
from . import AttrReportConfig, ClusterHandler
from .helpers import is_hue_motion_sensor

if TYPE_CHECKING:
    from ..endpoint import Endpoint


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    measurement.FlowMeasurement.cluster_id
)
class FlowMeasurement(ClusterHandler):
    """Flow Measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="measured_value", config=REPORT_CONFIG_DEFAULT),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    measurement.IlluminanceLevelSensing.cluster_id
)
class IlluminanceLevelSensing(ClusterHandler):
    """Illuminance Level Sensing cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="level_status", config=REPORT_CONFIG_DEFAULT),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    measurement.IlluminanceMeasurement.cluster_id
)
class IlluminanceMeasurement(ClusterHandler):
    """Illuminance Measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="measured_value", config=REPORT_CONFIG_DEFAULT),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    measurement.OccupancySensing.cluster_id
)
class OccupancySensing(ClusterHandler):
    """Occupancy Sensing cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="occupancy", config=REPORT_CONFIG_IMMEDIATE),
    )

    def __init__(self, cluster: zigpy.zcl.Cluster, endpoint: Endpoint) -> None:
        """Initialize Occupancy cluster handler."""
        super().__init__(cluster, endpoint)
        if is_hue_motion_sensor(self):
            self.ZCL_INIT_ATTRS = self.ZCL_INIT_ATTRS.copy()
            self.ZCL_INIT_ATTRS["sensitivity"] = True


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    measurement.PressureMeasurement.cluster_id
)
class PressureMeasurement(ClusterHandler):
    """Pressure measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(attr="measured_value", config=REPORT_CONFIG_DEFAULT),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    measurement.RelativeHumidity.cluster_id
)
class RelativeHumidity(ClusterHandler):
    """Relative Humidity measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 100),
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    measurement.SoilMoisture.cluster_id
)
class SoilMoisture(ClusterHandler):
    """Soil Moisture measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 100),
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(measurement.LeafWetness.cluster_id)
class LeafWetness(ClusterHandler):
    """Leaf Wetness measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 100),
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    measurement.TemperatureMeasurement.cluster_id
)
class TemperatureMeasurement(ClusterHandler):
    """Temperature measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 50),
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    measurement.CarbonMonoxideConcentration.cluster_id
)
class CarbonMonoxideConcentration(ClusterHandler):
    """Carbon Monoxide measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    measurement.CarbonDioxideConcentration.cluster_id
)
class CarbonDioxideConcentration(ClusterHandler):
    """Carbon Dioxide measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(measurement.PM25.cluster_id)
class PM25(ClusterHandler):
    """Particulate Matter 2.5 microns or less measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.1),
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    measurement.FormaldehydeConcentration.cluster_id
)
class FormaldehydeConcentration(ClusterHandler):
    """Formaldehyde measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr="measured_value",
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        ),
    )
