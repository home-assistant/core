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

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.CarbonMonoxideConcentration.cluster_id
)
class CarbonMonoxideConcentration(ZigbeeChannel):
    """Carbon Monoxide measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.CarbonDioxideConcentration.cluster_id
)
class CarbonDioxideConcentration(ZigbeeChannel):
    """Carbon Dioxide measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.EthyleneConcentration.cluster_id
)
class EthyleneConcentration(ZigbeeChannel):
    """Ethylene measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.EthyleneOxideConcentration.cluster_id
)
class EthyleneOxideConcentration(ZigbeeChannel):
    """Ethylene Oxide measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.HydrogenConcentration.cluster_id
)
class HydrogenConcentration(ZigbeeChannel):
    """Hydrogen measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.HydrogenSulfideConcentration.cluster_id
)
class HydrogenSulfideConcentration(ZigbeeChannel):
    """Hydrogen Sulfide measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.NitricOxideConcentration.cluster_id
)
class NitricOxideConcentration(ZigbeeChannel):
    """Nitric Oxide measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.NitrogenDioxideConcentration.cluster_id
)
class NitrogenDioxideConcentration(ZigbeeChannel):
    """NitrogenDioxide measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.OxygenConcentration.cluster_id
)
class OxygenConcentration(ZigbeeChannel):
    """Oxygen measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.OzoneConcentration.cluster_id
)
class OzoneConcentration(ZigbeeChannel):
    """Ozone measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.SulfurDioxideConcentration.cluster_id
)
class SulfurDioxideConcentration(ZigbeeChannel):
    """Sulfur Dioxide measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.DissolvedOxygenConcentration.cluster_id
)
class DissolvedOxygenConcentration(ZigbeeChannel):
    """Dissolved Oxygen measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.BromateConcentration.cluster_id
)
class BromateConcentration(ZigbeeChannel):
    """Bromate measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.ChloraminesConcentration.cluster_id
)
class ChloraminesConcentration(ZigbeeChannel):
    """Chloramines measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.ChlorineConcentration.cluster_id
)
class ChlorineConcentration(ZigbeeChannel):
    """Chlorine measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.FecalColiformAndEColiFraction.cluster_id
)
class FecalColiformAndEColiFraction(ZigbeeChannel):
    """Fecal Coliform And EColi Fraction measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.FluorideConcentration.cluster_id
)
class FluorideConcentration(ZigbeeChannel):
    """Fluoride measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.HaloaceticAcidsConcentration.cluster_id
)
class HaloaceticAcidsConcentration(ZigbeeChannel):
    """Haloacetic Acids measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.TotalTrihalomethanesConcentration.cluster_id
)
class TotalTrihalomethanesConcentration(ZigbeeChannel):
    """Total Trihalomethanes measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.TotalColiformBacteriaFraction.cluster_id
)
class TotalColiformBacteriaFraction(ZigbeeChannel):
    """Total Coliform Bacteria Fraction measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.Turbidity.cluster_id
)
class Turbidity(ZigbeeChannel):
    """Turbidity measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]
@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.CopperConcentration.cluster_id
)
class CopperConcentration(ZigbeeChannel):
    """Copper measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.LeadConcentration.cluster_id
)
class LeadConcentration(ZigbeeChannel):
    """Lead measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.ManganeseConcentration.cluster_id
)
class ManganeseConcentration(ZigbeeChannel):
    """Manganese measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]
@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.SulfateConcentration.cluster_id
)
class SulfateConcentration(ZigbeeChannel):
    """Sulfate measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.BromodichloromethaneConcentration.cluster_id
)
class BromodichloromethaneConcentration(ZigbeeChannel):
    """Bromodichloromethane measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.BromoformConcentration.cluster_id
)
class BromoformConcentration(ZigbeeChannel):
    """Bromoform measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]
@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.ChlorodibromomethaneConcentration.cluster_id
)
class ChlorodibromomethaneConcentration(ZigbeeChannel):
    """Chlorodibromomethane measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.ChloroformConcentration.cluster_id
)
class ChloroformConcentration(ZigbeeChannel):
    """Chloroform measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.SodiumConcentration.cluster_id
)
class SodiumConcentration(ZigbeeChannel):
    """Sodium measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]
@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.PM25.cluster_id
)
class PM25(ZigbeeChannel):
    """PM25 measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]

@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    measurement.FormaldehydeConcentration.cluster_id
)
class FormaldehydeConcentration(ZigbeeChannel):
    """Formaldehyde measurement channel.""" 
    REPORT_CONFIG = [
        {
            "attr": "measured_value",
            "config": (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 0.000001),
        }
    ]
    
