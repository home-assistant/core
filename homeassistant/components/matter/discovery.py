"""Map Matter Nodes and Attributes to Home Assistant entities."""

from __future__ import annotations

from collections.abc import Generator

from chip.clusters.Objects import ClusterAttributeDescriptor
from matter_server.client.models.node import MatterEndpoint

from homeassistant.const import Platform
from homeassistant.core import callback

from .binary_sensor import DISCOVERY_SCHEMAS as BINARY_SENSOR_SCHEMAS
from .button import DISCOVERY_SCHEMAS as BUTTON_SCHEMAS
from .climate import DISCOVERY_SCHEMAS as CLIMATE_SENSOR_SCHEMAS
from .const import FEATUREMAP_ATTRIBUTE_ID
from .cover import DISCOVERY_SCHEMAS as COVER_SCHEMAS
from .event import DISCOVERY_SCHEMAS as EVENT_SCHEMAS
from .fan import DISCOVERY_SCHEMAS as FAN_SCHEMAS
from .light import DISCOVERY_SCHEMAS as LIGHT_SCHEMAS
from .lock import DISCOVERY_SCHEMAS as LOCK_SCHEMAS
from .models import MatterDiscoverySchema, MatterEntityInfo
from .number import DISCOVERY_SCHEMAS as NUMBER_SCHEMAS
from .select import DISCOVERY_SCHEMAS as SELECT_SCHEMAS
from .sensor import DISCOVERY_SCHEMAS as SENSOR_SCHEMAS
from .switch import DISCOVERY_SCHEMAS as SWITCH_SCHEMAS
from .update import DISCOVERY_SCHEMAS as UPDATE_SCHEMAS
from .vacuum import DISCOVERY_SCHEMAS as VACUUM_SCHEMAS
from .valve import DISCOVERY_SCHEMAS as VALVE_SCHEMAS

DISCOVERY_SCHEMAS: dict[Platform, list[MatterDiscoverySchema]] = {
    Platform.BINARY_SENSOR: BINARY_SENSOR_SCHEMAS,
    Platform.BUTTON: BUTTON_SCHEMAS,
    Platform.CLIMATE: CLIMATE_SENSOR_SCHEMAS,
    Platform.COVER: COVER_SCHEMAS,
    Platform.EVENT: EVENT_SCHEMAS,
    Platform.FAN: FAN_SCHEMAS,
    Platform.LIGHT: LIGHT_SCHEMAS,
    Platform.LOCK: LOCK_SCHEMAS,
    Platform.NUMBER: NUMBER_SCHEMAS,
    Platform.SELECT: SELECT_SCHEMAS,
    Platform.SENSOR: SENSOR_SCHEMAS,
    Platform.SWITCH: SWITCH_SCHEMAS,
    Platform.UPDATE: UPDATE_SCHEMAS,
    Platform.VACUUM: VACUUM_SCHEMAS,
    Platform.VALVE: VALVE_SCHEMAS,
}
SUPPORTED_PLATFORMS = tuple(DISCOVERY_SCHEMAS)


@callback
def iter_schemas() -> Generator[MatterDiscoverySchema]:
    """Iterate over all available discovery schemas."""
    for platform_schemas in DISCOVERY_SCHEMAS.values():
        yield from platform_schemas


@callback
def async_discover_entities(
    endpoint: MatterEndpoint,
) -> Generator[MatterEntityInfo]:
    """Run discovery on MatterEndpoint and return matching MatterEntityInfo(s)."""
    discovered_attributes: set[type[ClusterAttributeDescriptor]] = set()
    device_info = endpoint.device_info
    for schema in iter_schemas():
        # abort if attribute(s) already discovered
        if any(x in schema.required_attributes for x in discovered_attributes):
            continue

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

        # check required device_type
        if schema.device_type is not None and not any(
            x in schema.device_type for x in endpoint.device_types
        ):
            continue

        # check absent device_type
        if schema.not_device_type is not None and any(
            x in schema.not_device_type for x in endpoint.device_types
        ):
            continue

        # check endpoint_id
        if (
            schema.endpoint_id is not None
            and endpoint.endpoint_id not in schema.endpoint_id
        ):
            continue

        # check required attributes
        if schema.required_attributes is not None and not all(
            endpoint.has_attribute(None, val_schema)
            for val_schema in schema.required_attributes
        ):
            continue

        # check for endpoint-attributes that may not be present
        if schema.absent_attributes is not None and any(
            endpoint.has_attribute(None, val_schema)
            for val_schema in schema.absent_attributes
        ):
            continue

        # check for clusters that may not be present
        if schema.absent_clusters is not None and any(
            endpoint.node.has_cluster(val_schema)
            for val_schema in schema.absent_clusters
        ):
            continue

        # check for required value in (primary) attribute
        primary_attribute = schema.required_attributes[0]
        primary_value = endpoint.get_attribute_value(None, primary_attribute)
        if schema.value_contains is not None and (
            isinstance(primary_value, list)
            and schema.value_contains not in primary_value
        ):
            continue

        # check for required value in cluster featuremap
        if schema.featuremap_contains is not None and (
            not bool(
                int(
                    endpoint.get_attribute_value(
                        primary_attribute.cluster_id, FEATUREMAP_ATTRIBUTE_ID
                    )
                )
                & schema.featuremap_contains
            )
        ):
            continue

        # all checks passed, this value belongs to an entity

        attributes_to_watch = list(schema.required_attributes)
        if schema.optional_attributes:
            # check optional attributes
            for optional_attribute in schema.optional_attributes:
                if optional_attribute in attributes_to_watch:
                    continue
                if endpoint.has_attribute(None, optional_attribute):
                    attributes_to_watch.append(optional_attribute)

        yield MatterEntityInfo(
            endpoint=endpoint,
            platform=schema.platform,
            attributes_to_watch=attributes_to_watch,
            entity_description=schema.entity_description,
            entity_class=schema.entity_class,
            discovery_schema=schema,
        )

        # prevent re-discovery of the primary attribute if not allowed
        if not schema.allow_multi:
            discovered_attributes.update(schema.required_attributes)
