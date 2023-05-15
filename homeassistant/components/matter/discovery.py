"""Map Matter Nodes and Attributes to Home Assistant entities."""
from __future__ import annotations

from collections.abc import Generator

from chip.clusters.Objects import ClusterAttributeDescriptor
from matter_server.client.models.node import MatterEndpoint

from homeassistant.const import Platform
from homeassistant.core import callback

from .binary_sensor import DISCOVERY_SCHEMAS as BINARY_SENSOR_SCHEMAS
from .cover import DISCOVERY_SCHEMAS as COVER_SCHEMAS
from .light import DISCOVERY_SCHEMAS as LIGHT_SCHEMAS
from .lock import DISCOVERY_SCHEMAS as LOCK_SCHEMAS
from .models import MatterDiscoverySchema, MatterEntityInfo
from .sensor import DISCOVERY_SCHEMAS as SENSOR_SCHEMAS
from .switch import DISCOVERY_SCHEMAS as SWITCH_SCHEMAS

DISCOVERY_SCHEMAS: dict[Platform, list[MatterDiscoverySchema]] = {
    Platform.BINARY_SENSOR: BINARY_SENSOR_SCHEMAS,
    Platform.COVER: COVER_SCHEMAS,
    Platform.LIGHT: LIGHT_SCHEMAS,
    Platform.LOCK: LOCK_SCHEMAS,
    Platform.SENSOR: SENSOR_SCHEMAS,
    Platform.SWITCH: SWITCH_SCHEMAS,
}
SUPPORTED_PLATFORMS = tuple(DISCOVERY_SCHEMAS)


@callback
def iter_schemas() -> Generator[MatterDiscoverySchema, None, None]:
    """Iterate over all available discovery schemas."""
    for platform_schemas in DISCOVERY_SCHEMAS.values():
        yield from platform_schemas


@callback
def async_discover_entities(
    endpoint: MatterEndpoint,
) -> Generator[MatterEntityInfo, None, None]:
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

        # check for values that may not be present
        if schema.absent_attributes is not None and any(
            endpoint.has_attribute(None, val_schema)
            for val_schema in schema.absent_attributes
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
        )

        # prevent re-discovery of the same attributes
        if not schema.allow_multi:
            discovered_attributes.update(attributes_to_watch)
