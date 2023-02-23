"""Map Matter Nodes and Attributes to Home Assistant entities."""
from __future__ import annotations

from collections.abc import Generator

from chip.clusters.Objects import ClusterAttributeDescriptor
from matter_server.client.models.node import MatterEndpoint
from matter_server.common.helpers.util import (
    create_attribute_path,
    parse_attribute_path,
)

from homeassistant.const import Platform
from homeassistant.core import callback

from .binary_sensor import DISCOVERY_SCHEMAS as BINARY_SENSOR_SCHEMAS
from .light import DISCOVERY_SCHEMAS as LIGHT_SCHEMAS
from .models import MatterDiscoverySchema, MatterEntityInfo
from .sensor import DISCOVERY_SCHEMAS as SENSOR_SCHEMAS
from .switch import DISCOVERY_SCHEMAS as SWITCH_SCHEMAS

DISCOVERY_SCHEMAS: dict[Platform, list[MatterDiscoverySchema]] = {
    Platform.BINARY_SENSOR: BINARY_SENSOR_SCHEMAS,
    Platform.LIGHT: LIGHT_SCHEMAS,
    Platform.SENSOR: SENSOR_SCHEMAS,
    Platform.SWITCH: SWITCH_SCHEMAS,
}
SUPPORTED_PLATFORMS = tuple(DISCOVERY_SCHEMAS.keys())


@callback
def iter_schemas() -> Generator[MatterDiscoverySchema, None, None]:
    """Iterate over all available discovery schemas."""
    for platform_schemas in DISCOVERY_SCHEMAS.values():
        for schema in platform_schemas:
            yield schema


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
    for schema in iter_schemas():
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
            type(x) in schema.device_type for x in endpoint.device_types
        ):
            continue

        # # check absent device_type
        if schema.not_device_type is not None and any(
            type(x) in schema.not_device_type for x in endpoint.device_types
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

        attributes_to_watch = list(schema.required_attributes)
        if schema.optional_attributes:
            # check optional attributes
            for optional_attribute in schema.optional_attributes:
                if any(
                    check_attribute(val, optional_attribute, endpoint.endpoint_id)
                    for val in endpoint.node.node_data.attributes
                ):
                    if optional_attribute in attributes_to_watch:
                        continue
                    attributes_to_watch.append(optional_attribute)

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
