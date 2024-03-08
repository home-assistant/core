"""Measurement cluster handlers module for Zigbee Home Automation."""
from __future__ import annotations

from typing import TYPE_CHECKING

import zigpy.zcl
from zigpy.zcl.clusters.measurement import (
    PM25,
    CarbonDioxideConcentration,
    CarbonMonoxideConcentration,
    FlowMeasurement,
    FormaldehydeConcentration,
    IlluminanceLevelSensing,
    IlluminanceMeasurement,
    LeafWetness,
    OccupancySensing,
    PressureMeasurement,
    RelativeHumidity,
    SoilMoisture,
    TemperatureMeasurement,
)

from .. import registries
from ..const import (
    REPORT_CONFIG_DEFAULT,
    REPORT_CONFIG_IMMEDIATE,
    REPORT_CONFIG_MAX_INT,
    REPORT_CONFIG_MIN_INT,
)
from . import AttrReportConfig, ClusterHandler
from .helpers import is_hue_motion_sensor, is_sonoff_presence_sensor

if TYPE_CHECKING:
    from ..endpoint import Endpoint


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(FlowMeasurement.cluster_id)
class FlowMeasurementClusterHandler(ClusterHandler):
    """Flow Measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=FlowMeasurement.AttributeDefs.measured_value.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(IlluminanceLevelSensing.cluster_id)
class IlluminanceLevelSensingClusterHandler(ClusterHandler):
    """Illuminance Level Sensing cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=IlluminanceLevelSensing.AttributeDefs.level_status.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(IlluminanceMeasurement.cluster_id)
class IlluminanceMeasurementClusterHandler(ClusterHandler):
    """Illuminance Measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=IlluminanceMeasurement.AttributeDefs.measured_value.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(OccupancySensing.cluster_id)
class OccupancySensingClusterHandler(ClusterHandler):
    """Occupancy Sensing cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=OccupancySensing.AttributeDefs.occupancy.name,
            config=REPORT_CONFIG_IMMEDIATE,
        ),
    )

    def __init__(self, cluster: zigpy.zcl.Cluster, endpoint: Endpoint) -> None:
        """Initialize Occupancy cluster handler."""
        super().__init__(cluster, endpoint)
        if is_hue_motion_sensor(self):
            self.ZCL_INIT_ATTRS = self.ZCL_INIT_ATTRS.copy()
            self.ZCL_INIT_ATTRS["sensitivity"] = True
        if is_sonoff_presence_sensor(self):
            self.ZCL_INIT_ATTRS = self.ZCL_INIT_ATTRS.copy()
            self.ZCL_INIT_ATTRS["ultrasonic_o_to_u_delay"] = True
            self.ZCL_INIT_ATTRS["ultrasonic_u_to_o_threshold"] = True


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(PressureMeasurement.cluster_id)
class PressureMeasurementClusterHandler(ClusterHandler):
    """Pressure measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=PressureMeasurement.AttributeDefs.measured_value.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(RelativeHumidity.cluster_id)
class RelativeHumidityClusterHandler(ClusterHandler):
    """Relative Humidity measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=RelativeHumidity.AttributeDefs.measured_value.name,
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 100),
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(SoilMoisture.cluster_id)
class SoilMoistureClusterHandler(ClusterHandler):
    """Soil Moisture measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=SoilMoisture.AttributeDefs.measured_value.name,
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 100),
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(LeafWetness.cluster_id)
class LeafWetnessClusterHandler(ClusterHandler):
    """Leaf Wetness measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=LeafWetness.AttributeDefs.measured_value.name,
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 100),
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(TemperatureMeasurement.cluster_id)
class TemperatureMeasurementClusterHandler(ClusterHandler):
    """Temperature measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=TemperatureMeasurement.AttributeDefs.measured_value.name,
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 50),
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    CarbonMonoxideConcentration.cluster_id
)
class CarbonMonoxideConcentrationClusterHandler(ClusterHandler):
    """Carbon Monoxide measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=CarbonMonoxideConcentration.AttributeDefs.measured_value.name,
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    CarbonDioxideConcentration.cluster_id
)
class CarbonDioxideConcentrationClusterHandler(ClusterHandler):
    """Carbon Dioxide measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=CarbonDioxideConcentration.AttributeDefs.measured_value.name,
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(PM25.cluster_id)
class PM25ClusterHandler(ClusterHandler):
    """Particulate Matter 2.5 microns or less measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=PM25.AttributeDefs.measured_value.name,
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.1),
        ),
    )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    FormaldehydeConcentration.cluster_id
)
class FormaldehydeConcentrationClusterHandler(ClusterHandler):
    """Formaldehyde measurement cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=FormaldehydeConcentration.AttributeDefs.measured_value.name,
            config=(REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        ),
    )
