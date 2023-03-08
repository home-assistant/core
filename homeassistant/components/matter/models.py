"""Models used for the Matter integration."""

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from chip.clusters import Objects as clusters
from chip.clusters.Objects import ClusterAttributeDescriptor
from matter_server.client.models.device_types import DeviceType
from matter_server.client.models.node import MatterEndpoint

from homeassistant.const import Platform
from homeassistant.helpers.entity import EntityDescription


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

    # the home assistant platform for which an entity should be created
    platform: Platform

    # All attributes that need to be watched by entity (incl. primary)
    attributes_to_watch: list[type[ClusterAttributeDescriptor]]

    # the entity description to use
    entity_description: EntityDescription

    # entity class to use to instantiate the entity
    entity_class: type

    # [optional] function to call to convert the value from the primary attribute
    measurement_to_ha: Callable[[SensorValueTypes], SensorValueTypes] | None = None

    @property
    def primary_attribute(self) -> type[ClusterAttributeDescriptor]:
        """Return Primary Attribute belonging to the entity."""
        return self.attributes_to_watch[0]


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

    # [required] attributes that ALL need to be present
    # on the node for this scheme to pass (minimal one == primary)
    required_attributes: tuple[type[ClusterAttributeDescriptor], ...]

    # [optional] the value's endpoint must contain this devicetype(s)
    device_type: tuple[type[DeviceType] | DeviceType, ...] | None = None

    # [optional] the value's endpoint must NOT contain this devicetype(s)
    not_device_type: tuple[type[DeviceType] | DeviceType, ...] | None = None

    # [optional] the endpoint's vendor_id must match ANY of these values
    vendor_id: tuple[int, ...] | None = None

    # [optional] the endpoint's product_name must match ANY of these values
    product_name: tuple[str, ...] | None = None

    # [optional] the attribute's endpoint_id must match ANY of these values
    endpoint_id: tuple[int, ...] | None = None

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
