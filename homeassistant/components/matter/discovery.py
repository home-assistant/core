"""Map Matter Nodes and Attributes to Home Assistant entities."""
from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import asdict, dataclass
from typing import Any

from chip.clusters import Objects as clusters
from chip.clusters.Objects import ClusterAttributeDescriptor
from matter_server.client.models import device_types
from matter_server.client.models.node import MatterEndpoint
from matter_server.common.helpers.util import (
    create_attribute_path,
    parse_attribute_path,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.light import LightEntityDescription
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntityDescription
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    Platform,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityDescription

from .binary_sensor import MatterBinarySensor
from .light import MatterLight
from .sensor import MatterSensor
from .switch import MatterSwitch


class DataclassMustHaveAtLeastOne:
    """A dataclass that must have at least one input parameter that is not None."""

    def __post_init__(self) -> None:
        """Post dataclass initialization."""
        if all(val is None for val in asdict(self).values()):
            raise ValueError("At least one input parameter must not be None")


SensorValueTypes = type[
    clusters.uint | int | clusters.Nullable | clusters.float32 | float
]


@dataclass
class MatterEntityInfo:
    """Info discovered from (primary) Matter Attribute to create entity."""

    # MatterEndpoint to which the value(s) belongs
    endpoint: MatterEndpoint

    # the primary value in the form of an AttributePath string
    primary_attribute: type[ClusterAttributeDescriptor]

    # the home assistant platform for which an entity should be created
    platform: Platform

    # All attributes that need to be watched by entity (incl. primary)
    attributes_to_watch: set[type[ClusterAttributeDescriptor]]

    # the entity description to use
    entity_description: EntityDescription

    # entity class to use to instantiate the entity
    entity_class: type

    # [optional] function to call to convert the value from the primary attribute
    measurement_to_ha: Callable[[SensorValueTypes], SensorValueTypes] | None = None


@dataclass
class MatterDiscoverySchema:
    """Matter discovery schema.

    The Matter endpoint and it's (primary) Attribute for an entity must match these conditions.
    """

    # specify the hass platform for which this scheme applies (e.g. light, sensor)
    platform: Platform

    # platform-specific entity description
    entity_description: EntityDescription

    # entity class to use to instantiate the entity
    entity_class: type

    # DISCOVERY OPTIONS

    # primary attribute belonging to this discovery scheme
    primary_attribute: type[ClusterAttributeDescriptor]

    # [optional] the value's endpoint must contain this devicetype(s)
    device_type: type[device_types.DeviceType] | None = None

    # [optional] the endpoint's vendor_id must match ANY of these values
    vendor_id: tuple[int, ...] | None = None

    # [optional] the endpoint's product_name must match ANY of these values
    product_name: tuple[str, ...] | None = None

    # [optional] the attribute's endpoint_id must match ANY of these values
    endpoint_id: tuple[int, ...] | None = None

    # [optional] additional attributes that ALL need to be present
    # on the node for this scheme to pass
    required_attributes: tuple[type[ClusterAttributeDescriptor], ...] | None = None

    # [optional] additional attributes that MAY NOT be present
    # on the node for this scheme to pass
    absent_attributes: tuple[type[ClusterAttributeDescriptor], ...] | None = None

    # [optional] additional attributes that may be present
    # these attributes are copied over to attributes_to_watch and
    # are not discovered by other entities
    optional_attributes: tuple[type[ClusterAttributeDescriptor], ...] | None = None

    # [optional] bool to specify if this primary value may be discovered
    # by multiple platforms
    allow_multi: bool = False

    # [optional] function to call to convert the value from the primary attribute
    measurement_to_ha: Callable[[Any], Any] | None = None


DISCOVERY_SCHEMAS = [
    #
    # binary_sensor platform
    #
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=BinarySensorEntityDescription(
            key="ContactSensor",
            device_class=BinarySensorDeviceClass.DOOR,
            name="Contact",
        ),
        entity_class=MatterBinarySensor,
        primary_attribute=clusters.BooleanState.Attributes.StateValue,
    ),
    # device specific: translate Hue motion to sensor to HA Motion sensor
    # instead of generic occupancy sensor
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=BinarySensorEntityDescription(
            key="HueMotionSensor",
            device_class=BinarySensorDeviceClass.MOTION,
            name="Motion",
        ),
        entity_class=MatterBinarySensor,
        primary_attribute=clusters.OccupancySensing.Attributes.Occupancy,
        vendor_id=(4107,),
        product_name=("Hue motion sensor",),
        measurement_to_ha=lambda x: (x & 1 == 1) if x is not None else None,
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=BinarySensorEntityDescription(
            key="OccupancySensor",
            device_class=BinarySensorDeviceClass.OCCUPANCY,
            name="Occupancy",
        ),
        entity_class=MatterBinarySensor,
        primary_attribute=clusters.OccupancySensing.Attributes.Occupancy,
        # The first bit = if occupied
        measurement_to_ha=lambda x: (x & 1 == 1) if x is not None else None,
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=BinarySensorEntityDescription(
            key="BatteryChargeLevel",
            device_class=BinarySensorDeviceClass.BATTERY,
            name="Battery Status",
        ),
        entity_class=MatterBinarySensor,
        primary_attribute=clusters.PowerSource.Attributes.BatChargeLevel,
        # only add binary battery sensor if a regular percentage based is not available
        absent_attributes=(clusters.PowerSource.Attributes.BatPercentRemaining,),
        measurement_to_ha=lambda x: x != clusters.PowerSource.Enums.BatChargeLevel.kOk,
    ),
    #
    # light platform
    #
    MatterDiscoverySchema(
        platform=Platform.LIGHT,
        entity_description=LightEntityDescription(key="ExtendedMatterLight"),
        entity_class=MatterLight,
        primary_attribute=clusters.OnOff.Attributes.OnOff,
        optional_attributes=(
            clusters.LevelControl.Attributes.CurrentLevel,
            clusters.ColorControl.Attributes.ColorMode,
            clusters.ColorControl.Attributes.CurrentHue,
            clusters.ColorControl.Attributes.CurrentSaturation,
            clusters.ColorControl.Attributes.CurrentX,
            clusters.ColorControl.Attributes.CurrentY,
            clusters.ColorControl.Attributes.ColorTemperatureMireds,
        ),
        # restrict device type to prevent discovery in switch platform
        device_type=device_types.DimmableLight,
    ),
    MatterDiscoverySchema(
        platform=Platform.LIGHT,
        entity_description=LightEntityDescription(key="OnOffMatterLight"),
        entity_class=MatterLight,
        primary_attribute=clusters.OnOff.Attributes.OnOff,
        # restrict device type to prevent discovery in switch platform
        device_type=device_types.OnOffLight,
    ),
    #
    # sensor platform
    #
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=SensorEntityDescription(
            key="TemperatureSensor",
            name="Temperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        ),
        entity_class=MatterSensor,
        primary_attribute=clusters.TemperatureMeasurement.Attributes.MeasuredValue,
        measurement_to_ha=lambda x: x / 100,
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=SensorEntityDescription(
            key="PressureSensor",
            name="Pressure",
            native_unit_of_measurement=UnitOfPressure.KPA,
            device_class=SensorDeviceClass.PRESSURE,
        ),
        entity_class=MatterSensor,
        primary_attribute=clusters.PressureMeasurement.Attributes.MeasuredValue,
        measurement_to_ha=lambda x: x / 10,
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=SensorEntityDescription(
            key="FlowSensor",
            name="Flow",
            native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
            device_class=SensorDeviceClass.WATER,  # what is the device class here ?
        ),
        entity_class=MatterSensor,
        primary_attribute=clusters.FlowMeasurement.Attributes.MeasuredValue,
        measurement_to_ha=lambda x: x / 10,
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=SensorEntityDescription(
            key="HumiditySensor",
            name="Humidity",
            native_unit_of_measurement=PERCENTAGE,
            device_class=SensorDeviceClass.HUMIDITY,
        ),
        entity_class=MatterSensor,
        primary_attribute=clusters.RelativeHumidityMeasurement.Attributes.MeasuredValue,
        measurement_to_ha=lambda x: x / 100,
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=SensorEntityDescription(
            key="LightSensor",
            name="Illuminance",
            native_unit_of_measurement=LIGHT_LUX,
            device_class=SensorDeviceClass.ILLUMINANCE,
        ),
        entity_class=MatterSensor,
        primary_attribute=clusters.IlluminanceMeasurement.Attributes.MeasuredValue,
        measurement_to_ha=lambda x: round(pow(10, ((x - 1) / 10000)), 1),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=SensorEntityDescription(
            key="PowerSource",
            name="Battery",
            native_unit_of_measurement=PERCENTAGE,
            device_class=SensorDeviceClass.BATTERY,
        ),
        entity_class=MatterSensor,
        primary_attribute=clusters.PowerSource.Attributes.BatPercentRemaining,
    ),
    #
    # switch platform
    #
    MatterDiscoverySchema(
        platform=Platform.SWITCH,
        entity_description=SwitchEntityDescription(
            key="MatterPlug", device_class=SwitchDeviceClass.OUTLET
        ),
        entity_class=MatterSwitch,
        primary_attribute=clusters.OnOff.Attributes.OnOff,
        # do not set device type here to catch all (remaining)
        # devices that support the OnOff cluster (e.g. powerplugs)
    ),
]


@callback
def async_discover_entities(
    endpoint: MatterEndpoint,
) -> Generator[MatterEntityInfo, None, None]:
    """Run discovery on MatterEndpoint and return matching MatterEntityInfo(s)."""
    discovered_attributes: set[str] = set()
    # use the raw values as that is the easiest and fastest way to inspect all attributes we have
    for attribute_path in endpoint.node.node_data.attributes:
        if not attribute_path.startswith(f"{endpoint.endpoint_id}/"):
            continue
        # We don't want to rediscover an already processed attribute
        if attribute_path in discovered_attributes:
            continue
        yield from async_discover_single(
            endpoint, attribute_path, discovered_attributes
        )


@callback
def async_discover_single(
    endpoint: MatterEndpoint,
    attribute_path: str,
    discovered_attributes: set[str],
) -> Generator[MatterEntityInfo, None, None]:
    """Run discovery on a single Matter Attribute and return matching schema info."""
    device_info = endpoint.device_info
    for schema in DISCOVERY_SCHEMAS:
        # check vendor_id
        if (
            schema.vendor_id is not None
            and device_info.vendorID not in schema.vendor_id
        ):
            continue

        # check product_name
        if (
            schema.product_name is not None
            and device_info.productName not in schema.product_name
        ):
            continue

        # check device_type
        if schema.device_type is not None and schema.device_type not in (
            type(x) for x in endpoint.device_types
        ):
            continue

        # check endpoint_id
        if (
            schema.endpoint_id is not None
            and endpoint.endpoint_id not in schema.endpoint_id
        ):
            continue

        # check primary attribute
        if not check_attribute(
            attribute_path, schema.primary_attribute, endpoint.endpoint_id
        ):
            continue

        # check additional required values
        if schema.required_attributes is not None and not all(
            any(
                check_attribute(val, val_schema, endpoint.endpoint_id)
                for val in endpoint.node.node_data.attributes
            )
            for val_schema in schema.required_attributes
        ):
            continue

        # check for values that may not be present
        if schema.absent_attributes is not None and any(
            any(
                check_attribute(val, val_schema, endpoint.endpoint_id)
                for val in endpoint.node.node_data.attributes
            )
            for val_schema in schema.absent_attributes
        ):
            continue

        # all checks passed, this value belongs to an entity

        attributes_to_watch = {schema.primary_attribute}
        if schema.required_attributes:
            attributes_to_watch.update(schema.required_attributes)
        if schema.optional_attributes:
            # check optional attributes
            for optional_attribute in schema.optional_attributes:
                if any(
                    check_attribute(val, optional_attribute, endpoint.endpoint_id)
                    for val in endpoint.node.node_data.attributes
                ):
                    attributes_to_watch.add(optional_attribute)

        # prevent re-discovery of the same attributes
        for attribute_to_watch in attributes_to_watch:
            path = create_attribute_path(
                endpoint.endpoint_id,
                attribute_to_watch.cluster_id,
                attribute_to_watch.attribute_id,
            )
            discovered_attributes.add(path)

        yield MatterEntityInfo(
            endpoint=endpoint,
            primary_attribute=schema.primary_attribute,
            platform=schema.platform,
            attributes_to_watch=attributes_to_watch,
            entity_description=schema.entity_description,
            entity_class=schema.entity_class,
            measurement_to_ha=schema.measurement_to_ha,
        )

        if not schema.allow_multi:
            # return early since this value may not be discovered
            # by other schemas/platforms
            return


@callback
def check_attribute(
    attribute_path: str,
    schema_attribute: ClusterAttributeDescriptor,
    required_endpoint_id: int,
) -> bool:
    """Check if attribute matches schema."""
    endpoint_id, cluster_id, attribute_id = parse_attribute_path(attribute_path)
    if endpoint_id != required_endpoint_id:
        return False
    if schema_attribute.cluster_id != cluster_id:
        return False
    if schema_attribute.attribute_id != attribute_id:
        return False
    return True
