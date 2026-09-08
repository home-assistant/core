"""Support for Meshtastic sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfDensity,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfInformation,
    UnitOfLength,
    UnitOfMass,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfRatio,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import MeshtasticConfigEntry
from .coordinator import MeshtasticCoordinator
from .entity import MeshtasticEntity, MeshtasticNodeEntity
from .models import ConnectionState, MeshtasticNode, TelemetryFamily, TelemetryValue

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

#: ``EnvironmentMetrics.gas_resistance`` is documented as megaohms.
UNIT_MEGAOHM: Final = "MΩ"
#: ``EnvironmentMetrics.radiation`` is documented as microroentgen per hour.
UNIT_MICROROENTGEN_PER_HOUR: Final = "µR/h"

#: The firmware reports this battery level for a node that runs off USB and has
#: no battery at all (``MAGIC_USB_BATTERY_LEVEL``).
BATTERY_LEVEL_POWERED: Final = 101


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------


def _number(value: TelemetryValue | None) -> float | int | None:
    """Return a telemetry value when it is a plain number, otherwise None."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return value


def _metric(
    node: MeshtasticNode, family: TelemetryFamily, metric: str
) -> TelemetryValue | None:
    """Return one metric of a node's newest sample of a telemetry family."""
    sample = node.sample(family)
    return None if sample is None else sample.value(metric)


def _value(
    family: TelemetryFamily, metric: str
) -> Callable[[MeshtasticNode], StateType]:
    """Return a value function reading one metric of a telemetry family."""
    return lambda node: _number(_metric(node, family, metric))


def _present(family: TelemetryFamily, metric: str) -> Callable[[MeshtasticNode], bool]:
    """Return an existence function for one metric of a telemetry family."""
    return lambda node: _metric(node, family, metric) is not None


def _battery_level(node: MeshtasticNode) -> StateType:
    """Return the battery level, or None for a node that has no battery.

    Anything above 100 % is the firmware's "powered over USB" marker rather
    than a charge level, and reporting it as a percentage would be wrong.
    """
    level = _number(_metric(node, TelemetryFamily.DEVICE, "battery_level"))
    if level is None or level >= BATTERY_LEVEL_POWERED:
        return None
    return level


def _boot_time(node: MeshtasticNode) -> datetime | None:
    """Return when the node booted, derived from the uptime it reported."""
    sample = node.sample(TelemetryFamily.DEVICE)
    if sample is None or sample.reported_at is None:
        return None
    uptime = _number(sample.value("uptime_seconds"))
    if uptime is None:
        return None
    return sample.reported_at - timedelta(seconds=uptime)


def _gateway_node(coordinator: MeshtasticCoordinator) -> MeshtasticNode | None:
    """Return the gateway's own record in the node table."""
    return coordinator.data.nodes.get(coordinator.data.gateway.node_id)


def _gateway_value(
    family: TelemetryFamily, metric: str
) -> Callable[[MeshtasticCoordinator], StateType]:
    """Return a value function reading gateway telemetry."""

    def _read(coordinator: MeshtasticCoordinator) -> StateType:
        node = _gateway_node(coordinator)
        return None if node is None else _number(_metric(node, family, metric))

    return _read


def _gateway_battery_level(coordinator: MeshtasticCoordinator) -> StateType:
    """Return the gateway's battery level."""
    node = _gateway_node(coordinator)
    return None if node is None else _battery_level(node)


def _gateway_boot_time(coordinator: MeshtasticCoordinator) -> datetime | None:
    """Return when the gateway booted."""
    node = _gateway_node(coordinator)
    return None if node is None else _boot_time(node)


def _node_count(coordinator: MeshtasticCoordinator) -> int:
    """Return how many nodes introduced themselves to this gateway."""
    return sum(1 for node in coordinator.data.nodes.values() if not node.presumptive)


def _last_packet_received(coordinator: MeshtasticCoordinator) -> datetime | None:
    """Return when the gateway last heard anything from the mesh."""
    return max(
        (
            node.last_heard
            for node in coordinator.data.nodes.values()
            if node.last_heard is not None
        ),
        default=None,
    )


# ---------------------------------------------------------------------------
# Entity descriptions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class MeshtasticGatewaySensorEntityDescription(SensorEntityDescription):
    """Describes a Meshtastic sensor of the gateway node itself."""

    value_fn: Callable[[MeshtasticCoordinator], StateType | datetime]
    #: Link diagnostics stay available while the link is down; that is exactly
    #: when a user wants to look at them.
    always_available: bool = False


@dataclass(frozen=True, kw_only=True)
class MeshtasticNodeSensorEntityDescription(SensorEntityDescription):
    """Describes a Meshtastic sensor of a mesh node."""

    value_fn: Callable[[MeshtasticNode], StateType | datetime]
    #: Telemetry sensors only exist once the node reported that metric once.
    exists_fn: Callable[[MeshtasticNode], bool] = lambda _node: True


GATEWAY_SENSORS: Final[tuple[MeshtasticGatewaySensorEntityDescription, ...]] = (
    MeshtasticGatewaySensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_gateway_battery_level,
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_gateway_value(TelemetryFamily.DEVICE, "voltage"),
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="channel_utilization",
        translation_key="channel_utilization",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_gateway_value(TelemetryFamily.DEVICE, "channel_utilization"),
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="air_util_tx",
        translation_key="air_util_tx",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_gateway_value(TelemetryFamily.DEVICE, "air_util_tx"),
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="uptime_seconds",
        device_class=SensorDeviceClass.UPTIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_gateway_boot_time,
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="node_count",
        translation_key="node_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_node_count,
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="last_packet_received",
        translation_key="last_packet_received",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_last_packet_received,
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="connection_state",
        translation_key="connection_state",
        device_class=SensorDeviceClass.ENUM,
        options=[state.value for state in ConnectionState],
        entity_category=EntityCategory.DIAGNOSTIC,
        always_available=True,
        value_fn=lambda coordinator: coordinator.client.connection_state.value,
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="nodedb_count",
        translation_key="nodedb_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.gateway.nodedb_count,
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="num_online_nodes",
        translation_key="num_online_nodes",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_gateway_value(TelemetryFamily.LOCAL_STATS, "num_online_nodes"),
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="num_total_nodes",
        translation_key="num_total_nodes",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_gateway_value(TelemetryFamily.LOCAL_STATS, "num_total_nodes"),
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="heap_free_bytes",
        translation_key="heap_free_bytes",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.KILOBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_gateway_value(TelemetryFamily.LOCAL_STATS, "heap_free_bytes"),
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="heap_total_bytes",
        translation_key="heap_total_bytes",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.KILOBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_gateway_value(TelemetryFamily.LOCAL_STATS, "heap_total_bytes"),
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="num_packets_tx",
        translation_key="num_packets_tx",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_gateway_value(TelemetryFamily.LOCAL_STATS, "num_packets_tx"),
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="num_packets_rx",
        translation_key="num_packets_rx",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_gateway_value(TelemetryFamily.LOCAL_STATS, "num_packets_rx"),
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="num_packets_rx_bad",
        translation_key="num_packets_rx_bad",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_gateway_value(TelemetryFamily.LOCAL_STATS, "num_packets_rx_bad"),
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="num_rx_dupe",
        translation_key="num_rx_dupe",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_gateway_value(TelemetryFamily.LOCAL_STATS, "num_rx_dupe"),
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="num_tx_relay",
        translation_key="num_tx_relay",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_gateway_value(TelemetryFamily.LOCAL_STATS, "num_tx_relay"),
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="num_tx_relay_canceled",
        translation_key="num_tx_relay_canceled",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_gateway_value(TelemetryFamily.LOCAL_STATS, "num_tx_relay_canceled"),
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="num_tx_dropped",
        translation_key="num_tx_dropped",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_gateway_value(TelemetryFamily.LOCAL_STATS, "num_tx_dropped"),
    ),
    MeshtasticGatewaySensorEntityDescription(
        key="noise_floor",
        translation_key="noise_floor",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_gateway_value(TelemetryFamily.LOCAL_STATS, "noise_floor"),
    ),
)


NODE_SENSORS: Final[tuple[MeshtasticNodeSensorEntityDescription, ...]] = (
    # -- link quality, from the packets the gateway heard ------------------
    MeshtasticNodeSensorEntityDescription(
        key="last_heard",
        translation_key="last_heard",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda node: node.last_heard,
    ),
    MeshtasticNodeSensorEntityDescription(
        key="snr",
        translation_key="snr",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda node: node.snr,
    ),
    MeshtasticNodeSensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda node: node.rssi,
    ),
    MeshtasticNodeSensorEntityDescription(
        key="hops_away",
        translation_key="hops_away",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda node: node.hops_away,
    ),
    # -- DeviceMetrics -----------------------------------------------------
    MeshtasticNodeSensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_battery_level,
        exists_fn=_present(TelemetryFamily.DEVICE, "battery_level"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value(TelemetryFamily.DEVICE, "voltage"),
        exists_fn=_present(TelemetryFamily.DEVICE, "voltage"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="channel_utilization",
        translation_key="channel_utilization",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value(TelemetryFamily.DEVICE, "channel_utilization"),
        exists_fn=_present(TelemetryFamily.DEVICE, "channel_utilization"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="air_util_tx",
        translation_key="air_util_tx",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value(TelemetryFamily.DEVICE, "air_util_tx"),
        exists_fn=_present(TelemetryFamily.DEVICE, "air_util_tx"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="uptime_seconds",
        device_class=SensorDeviceClass.UPTIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_boot_time,
        exists_fn=_present(TelemetryFamily.DEVICE, "uptime_seconds"),
    ),
    # -- EnvironmentMetrics ------------------------------------------------
    MeshtasticNodeSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "temperature"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "temperature"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="relative_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "relative_humidity"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "relative_humidity"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="barometric_pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "barometric_pressure"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "barometric_pressure"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="gas_resistance",
        translation_key="gas_resistance",
        native_unit_of_measurement=UNIT_MEGAOHM,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "gas_resistance"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "gas_resistance"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="iaq",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "iaq"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "iaq"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="lux",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "lux"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "lux"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="white_lux",
        translation_key="white_lux",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "white_lux"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "white_lux"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="ir_lux",
        translation_key="ir_lux",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "ir_lux"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "ir_lux"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="uv_lux",
        translation_key="uv_lux",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "uv_lux"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "uv_lux"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "wind_speed"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "wind_speed"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="wind_direction",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "wind_direction"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "wind_direction"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="wind_gust",
        translation_key="wind_gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "wind_gust"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "wind_gust"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="wind_lull",
        translation_key="wind_lull",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "wind_lull"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "wind_lull"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="environment_voltage",
        translation_key="environment_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "voltage"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "voltage"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="environment_current",
        translation_key="environment_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "current"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "current"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "distance"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "distance"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "weight"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "weight"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="radiation",
        translation_key="radiation",
        native_unit_of_measurement=UNIT_MICROROENTGEN_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "radiation"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "radiation"),
    ),
    # The library renders ``rainfall_1h`` as ``rainfall1h``, which is why the
    # entity key and the metric name differ here.
    MeshtasticNodeSensorEntityDescription(
        key="rainfall_1h",
        translation_key="rainfall_1h",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "rainfall1h"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "rainfall1h"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="rainfall_24h",
        translation_key="rainfall_24h",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "rainfall24h"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "rainfall24h"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="soil_moisture",
        device_class=SensorDeviceClass.MOISTURE,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "soil_moisture"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "soil_moisture"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="soil_temperature",
        translation_key="soil_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_value(TelemetryFamily.ENVIRONMENT, "soil_temperature"),
        exists_fn=_present(TelemetryFamily.ENVIRONMENT, "soil_temperature"),
    ),
    # -- PowerMetrics; channels 4 to 8 are deprecated in the protocol ------
    MeshtasticNodeSensorEntityDescription(
        key="power_ch1_voltage",
        translation_key="power_ch1_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_value(TelemetryFamily.POWER, "ch1_voltage"),
        exists_fn=_present(TelemetryFamily.POWER, "ch1_voltage"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="power_ch1_current",
        translation_key="power_ch1_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_value(TelemetryFamily.POWER, "ch1_current"),
        exists_fn=_present(TelemetryFamily.POWER, "ch1_current"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="power_ch2_voltage",
        translation_key="power_ch2_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_value(TelemetryFamily.POWER, "ch2_voltage"),
        exists_fn=_present(TelemetryFamily.POWER, "ch2_voltage"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="power_ch2_current",
        translation_key="power_ch2_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_value(TelemetryFamily.POWER, "ch2_current"),
        exists_fn=_present(TelemetryFamily.POWER, "ch2_current"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="power_ch3_voltage",
        translation_key="power_ch3_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_value(TelemetryFamily.POWER, "ch3_voltage"),
        exists_fn=_present(TelemetryFamily.POWER, "ch3_voltage"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="power_ch3_current",
        translation_key="power_ch3_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_value(TelemetryFamily.POWER, "ch3_current"),
        exists_fn=_present(TelemetryFamily.POWER, "ch3_current"),
    ),
    # -- AirQualityMetrics; the protocol names them by particle size, so
    # ``pm10_standard`` is PM1.0 and ``pm100_standard`` is PM10.0.
    MeshtasticNodeSensorEntityDescription(
        key="pm10_standard",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value(TelemetryFamily.AIR_QUALITY, "pm10_standard"),
        exists_fn=_present(TelemetryFamily.AIR_QUALITY, "pm10_standard"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="pm25_standard",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value(TelemetryFamily.AIR_QUALITY, "pm25_standard"),
        exists_fn=_present(TelemetryFamily.AIR_QUALITY, "pm25_standard"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="pm40_standard",
        device_class=SensorDeviceClass.PM4,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value(TelemetryFamily.AIR_QUALITY, "pm40_standard"),
        exists_fn=_present(TelemetryFamily.AIR_QUALITY, "pm40_standard"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="pm100_standard",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value(TelemetryFamily.AIR_QUALITY, "pm100_standard"),
        exists_fn=_present(TelemetryFamily.AIR_QUALITY, "pm100_standard"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value(TelemetryFamily.AIR_QUALITY, "co2"),
        exists_fn=_present(TelemetryFamily.AIR_QUALITY, "co2"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="pm_voc_idx",
        translation_key="pm_voc_idx",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value(TelemetryFamily.AIR_QUALITY, "pm_voc_idx"),
        exists_fn=_present(TelemetryFamily.AIR_QUALITY, "pm_voc_idx"),
    ),
    MeshtasticNodeSensorEntityDescription(
        key="pm_nox_idx",
        translation_key="pm_nox_idx",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value(TelemetryFamily.AIR_QUALITY, "pm_nox_idx"),
        exists_fn=_present(TelemetryFamily.AIR_QUALITY, "pm_nox_idx"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeshtasticConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meshtastic sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator
    gateway_id = coordinator.gateway.node_id

    async_add_entities(
        MeshtasticGatewaySensor(coordinator, description)
        for description in GATEWAY_SENSORS
    )

    #: Entity description keys already created, per node id.
    known: dict[str, set[str]] = {}

    @callback
    def _add_node_sensors() -> None:
        """Add sensors for nodes and metrics that turned up since last time.

        A metric can start being reported long after the node first appeared,
        so this re-checks the whole table rather than only new nodes.
        """
        entities: list[MeshtasticNodeSensor] = []
        for node_id, node in coordinator.data.nodes.items():
            # A node that has only ever been relayed has no identity yet, and
            # the gateway's own metrics live on the gateway device itself.
            if node.presumptive or node_id == gateway_id:
                continue
            created = known.setdefault(node_id, set())
            for description in NODE_SENSORS:
                if description.key in created or not description.exists_fn(node):
                    continue
                created.add(description.key)
                entities.append(MeshtasticNodeSensor(coordinator, node, description))
        async_add_entities(entities)

    _add_node_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_node_sensors))


class MeshtasticGatewaySensor(MeshtasticEntity, SensorEntity):
    """A sensor reporting on the node Home Assistant is connected to."""

    entity_description: MeshtasticGatewaySensorEntityDescription

    def __init__(
        self,
        coordinator: MeshtasticCoordinator,
        description: MeshtasticGatewaySensorEntityDescription,
    ) -> None:
        """Initialise a gateway sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.coordinator)

    @property
    @override
    def available(self) -> bool:
        """Return True when the sensor can report something useful."""
        if self.entity_description.always_available:
            return True
        return super().available


class MeshtasticNodeSensor(MeshtasticNodeEntity, SensorEntity):
    """A sensor reporting on one node of the mesh."""

    entity_description: MeshtasticNodeSensorEntityDescription

    def __init__(
        self,
        coordinator: MeshtasticCoordinator,
        node: MeshtasticNode,
        description: MeshtasticNodeSensorEntityDescription,
    ) -> None:
        """Initialise a mesh-node sensor."""
        super().__init__(coordinator, node, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the value of the sensor."""
        if (node := self.node) is None:
            return None
        return self.entity_description.value_fn(node)
