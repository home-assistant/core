"""Matter entity base class."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import functools
import logging
from typing import TYPE_CHECKING, Any, Concatenate, cast, override

from chip.clusters import Objects as clusters
from chip.clusters.Objects import ClusterAttributeDescriptor, ClusterCommand, NullValue
from matter_server.common.errors import MatterError
from matter_server.common.helpers.util import (
    create_attribute_path,
    create_attribute_path_from_attribute,
)
from matter_server.common.models import EventType, ServerInfoMessage
from propcache.api import cached_property

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.translation import async_get_cached_translations
from homeassistant.helpers.typing import Undefined

from .const import DOMAIN, FEATUREMAP_ATTRIBUTE_ID, ID_TYPE_DEVICE_ID
from .helpers import (
    MatterConfigEntry,
    get_device_id,
    get_discovery_key,
    get_entity_unique_id,
)

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint

    from .models import MatterEntityInfo

LOGGER = logging.getLogger(__name__)

# Due to variances in labeling implementations, labels are vendor and product specific.
# This dictionary defines which labels to use for specific vendor/product combinations.
# The keys are vendor IDs, the values are dictionaries with product IDs as keys
# and lists of label names to use as values. If the value is None, no labels are used
VENDOR_LABELING_LIST: dict[int, dict[int, list[str] | None]] = {
    4488: {259: ["position"]},  # TP-Link Dual Outdoor Plug US
    4874: {105: ["orientation"]},  # Eve Energy dual Outlet US
    4961: {
        1: ["inovelliname", "label", "name", "button"],  # Inovelli VTM31
        2: ["label", "devicetype", "button"],  # Inovelli VTM35
        4: None,  # Inovelli VTM36
        16: ["label", "name", "button"],  # Inovelli VTM30
    },
    65521: {  # Test/DIY devices
        32768: ["ha_entitylabel"],
        32769: ["ha_entitylabel"],
        32770: ["ha_entitylabel"],
    },
    65522: {  # Test/DIY devices
        32768: ["ha_entitylabel"],
        32769: ["ha_entitylabel"],
        32770: ["ha_entitylabel"],
    },
}

NAMESPACE_COMMON_AREA = clusters.Globals.Enums.namespace.kCommonAreaNamespace

# Translation keys (strings.json -> "common") for the Common Area namespace
# (0x0010) semantic tags, as defined by the Matter specification. The tag
# value is the room or area the endpoint belongs to (e.g. a Thermostat
# endpoint tagged "Bedroom" on a bridged device with multiple Thermostats).
AREA_TAG_TRANSLATION_KEYS: dict[int, str] = {
    0x00: "area_aisle",
    0x01: "area_attic",
    0x02: "area_back_door",
    0x03: "area_back_yard",
    0x04: "area_balcony",
    0x05: "area_ballroom",
    0x06: "area_bathroom",
    0x07: "area_bedroom",
    0x08: "area_border",
    0x09: "area_boxroom",
    0x0A: "area_breakfast_room",
    0x0B: "area_carport",
    0x0C: "area_cellar",
    0x0D: "area_cloakroom",
    0x0E: "area_closet",
    0x0F: "area_conservatory",
    0x10: "area_corridor",
    0x11: "area_craft_room",
    0x12: "area_cupboard",
    0x13: "area_deck",
    0x14: "area_den",
    0x15: "area_dining",
    0x16: "area_drawing_room",
    0x17: "area_dressing_room",
    0x18: "area_driveway",
    0x19: "area_elevator",
    0x1A: "area_ensuite",
    0x1B: "area_entrance",
    0x1C: "area_entryway",
    0x1D: "area_family_room",
    0x1E: "area_foyer",
    0x1F: "area_front_door",
    0x20: "area_front_yard",
    0x21: "area_game_room",
    0x22: "area_garage",
    0x23: "area_garage_door",
    0x24: "area_garden",
    0x25: "area_garden_door",
    0x26: "area_guest_bathroom",
    0x27: "area_guest_bedroom",
    0x29: "area_guest_room",
    0x2A: "area_gym",
    0x2B: "area_hallway",
    0x2C: "area_hearth_room",
    0x2D: "area_kids_room",
    0x2E: "area_kids_bedroom",
    0x2F: "area_kitchen",
    0x31: "area_laundry_room",
    0x32: "area_lawn",
    0x33: "area_library",
    0x34: "area_living_room",
    0x35: "area_lounge",
    0x36: "area_media_tv_room",
    0x37: "area_mud_room",
    0x38: "area_music_room",
    0x39: "area_nursery",
    0x3A: "area_office",
    0x3B: "area_outdoor_kitchen",
    0x3C: "area_outside",
    0x3D: "area_pantry",
    0x3E: "area_parking_lot",
    0x3F: "area_parlor",
    0x40: "area_patio",
    0x41: "area_play_room",
    0x42: "area_pool_room",
    0x43: "area_porch",
    0x44: "area_primary_bathroom",
    0x45: "area_primary_bedroom",
    0x46: "area_ramp",
    0x47: "area_reception_room",
    0x48: "area_recreation_room",
    0x4A: "area_roof",
    0x4B: "area_sauna",
    0x4C: "area_scullery",
    0x4D: "area_sewing_room",
    0x4E: "area_shed",
    0x4F: "area_side_door",
    0x50: "area_side_yard",
    0x51: "area_sitting_room",
    0x52: "area_snug",
    0x53: "area_spa",
    0x54: "area_staircase",
    0x55: "area_steam_room",
    0x56: "area_storage_room",
    0x57: "area_studio",
    0x58: "area_study",
    0x59: "area_sun_room",
    0x5A: "area_swimming_pool",
    0x5B: "area_terrace",
    0x5C: "area_utility_room",
    0x5D: "area_ward",
    0x5E: "area_workshop",
    0x5F: "area_toilet",
}


def catch_matter_error[_R, **P](
    func: Callable[Concatenate[MatterEntity, P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[MatterEntity, P], Coroutine[Any, Any, _R]]:
    """Catch Matter errors and convert to Home Assistant error."""

    @functools.wraps(func)
    async def wrapper(self: MatterEntity, *args: P.args, **kwargs: P.kwargs) -> _R:
        """Catch Matter errors and convert to Home Assistant error."""
        try:
            return await func(self, *args, **kwargs)
        except MatterError as err:
            error_msg = str(err) or err.__class__.__name__
            raise HomeAssistantError(error_msg) from err

    return wrapper


@dataclass(frozen=True, kw_only=True)
class MatterEntityDescription(EntityDescription):
    """Describe the Matter entity."""

    # convert the value from the primary attribute to the value used by HA
    device_to_ha: Callable[[Any], Any] | None = None
    ha_to_device: Callable[[Any], Any] | None = None
    command_timeout: int | None = None


class MatterEntity(Entity):
    """Entity class for Matter devices."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _name_postfix: str | None = None
    _name_postfix_is_area_tag = False
    _platform_translation_key: str | None = None
    # Cooldown in seconds to debounce state writes on updates from the device.
    # Platforms which derive their state from multiple attributes can set this
    # to coalesce attribute updates which arrive as separate events.
    _write_state_debounce_cooldown: float | None = None
    _write_state_debouncer: Debouncer[None] | None = None
    _removal_scheduled = False

    def __init__(
        self,
        matter_client: MatterClient,
        endpoint: MatterEndpoint,
        entity_info: MatterEntityInfo,
    ) -> None:
        """Initialize the entity."""
        self.matter_client = matter_client
        self._endpoint = endpoint
        self._entity_info = entity_info
        self.entity_description = entity_info.entity_description
        # for fast lookups we create a mapping to the attribute paths
        self._attributes_map: dict[type, str] = {}
        # The server info is set when the client connects to the server.
        server_info = cast(ServerInfoMessage, self.matter_client.server_info)
        # create unique_id based on "Operational Instance Name" and endpoint/device type
        node_device_id = get_device_id(server_info, endpoint)
        self._attr_unique_id = get_entity_unique_id(
            node_device_id, endpoint, entity_info
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{ID_TYPE_DEVICE_ID}_{node_device_id}")}
        )
        self._attr_available = (
            self._endpoint.node.available and self._get_bridged_reachable()
        )
        # mark endpoint postfix if the device has the primary
        # attribute on multiple endpoints
        sibling_endpoints = [
            ep
            for ep in self._endpoint.node.endpoints.values()
            if ep != self._endpoint
            and ep.has_attribute(None, entity_info.primary_attribute)
        ]
        if not self._endpoint.node.is_bridge_device and sibling_endpoints:
            self._name_postfix = str(self._endpoint.endpoint_id)
        # Common Area tags name the endpoint after its room. This is set before
        # the primary entity name is suppressed below, so bridged endpoints keep it.
        if area_key := self._get_area_tag_key(self._endpoint):
            if any(self._get_area_tag_key(ep) == area_key for ep in sibling_endpoints):
                self._name_postfix = str(self._endpoint.endpoint_id)
            else:
                self._name_postfix = area_key
                self._name_postfix_is_area_tag = True
        # Always set translation_key for state_attributes translations.
        # For primary entities (no postfix), suppress the translated name,
        # so only the device name is used.
        if self._platform_translation_key and not self.translation_key:
            self._attr_translation_key = self._platform_translation_key
            if not self._name_postfix:
                self._attr_name = None

        # Matter labels can be used to modify the entity name
        # by appending the text.
        if found_labels := self._find_matching_labels():
            self._name_postfix = found_labels[0]
            self._name_postfix_is_area_tag = False

        # make sure to update the attributes once
        self._update_from_device()

    def _find_matching_labels(self) -> list[str]:
        """Find all labels for a Matter entity."""

        device_info = self._endpoint.device_info
        labeling_list = (
            VENDOR_LABELING_LIST.get(device_info.vendorID, {}).get(
                device_info.productID
            )
            if device_info is not None
            else None
        )

        # get the labels from the UserLabel and FixedLabel clusters
        user_label_list: list[clusters.UserLabel.Structs.LabelStruct] = (
            self.get_matter_attribute_value(clusters.UserLabel.Attributes.LabelList)
            or []
        )
        fixed_label_list: list[clusters.FixedLabel.Structs.LabelStruct] = (
            self.get_matter_attribute_value(clusters.FixedLabel.Attributes.LabelList)
            or []
        )

        found_labels: list[str] = [
            lbl.value
            for label in labeling_list or []
            for lbl in (*user_label_list, *fixed_label_list)
            if lbl.label.lower() == label
        ]
        return found_labels

    @staticmethod
    def _get_area_tag_key(endpoint: MatterEndpoint) -> str | None:
        """Get the translation key for the endpoint's Common Area tag, if any."""

        tag_list: list[clusters.Globals.Structs.semtag] = (
            endpoint.get_attribute_value(None, clusters.Descriptor.Attributes.TagList)
            or []
        )
        for tag in tag_list:
            if (
                tag.mfgCode not in (None, NullValue)
                or tag.namespaceID != NAMESPACE_COMMON_AREA
            ):
                continue
            if translation_key := AREA_TAG_TRANSLATION_KEYS.get(tag.tag):
                return translation_key
        return None

    @override
    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await super().async_added_to_hass()

        if self._write_state_debounce_cooldown is not None:
            self._write_state_debouncer = Debouncer(
                self.hass,
                LOGGER,
                cooldown=self._write_state_debounce_cooldown,
                immediate=False,
                function=self.async_write_ha_state,
            )

        # Subscribe to attribute updates.
        sub_paths: list[str] = []
        for attr_cls in self._entity_info.attributes_to_watch:
            attr_path = self.get_matter_attribute_path(attr_cls)
            if attr_path in sub_paths:
                # prevent duplicate subscriptions
                continue
            self._attributes_map[attr_cls] = attr_path
            sub_paths.append(attr_path)
            self.async_on_remove(
                self.matter_client.subscribe_events(
                    callback=self._on_matter_event,
                    event_filter=EventType.ATTRIBUTE_UPDATED,
                    node_filter=self._endpoint.node.node_id,
                    attr_path_filter=attr_path,
                )
            )
        # subscribe to node (availability changes)
        self.async_on_remove(
            self.matter_client.subscribe_events(
                callback=self._on_matter_event,
                event_filter=EventType.NODE_UPDATED,
                node_filter=self._endpoint.node.node_id,
            )
        )
        # Subscribe to BridgedDeviceBasicInformation Reachable
        # attribute (AttributeId: 17) for devices connected via a
        # Matter bridge, to reflect real reachability status.
        if self._endpoint.has_attribute(
            None, clusters.BridgedDeviceBasicInformation.Attributes.Reachable
        ):
            reachable_attr_path = self.get_matter_attribute_path(
                clusters.BridgedDeviceBasicInformation.Attributes.Reachable
            )
            if reachable_attr_path not in sub_paths:
                sub_paths.append(reachable_attr_path)
                self.async_on_remove(
                    self.matter_client.subscribe_events(
                        callback=self._on_matter_event,
                        event_filter=EventType.ATTRIBUTE_UPDATED,
                        node_filter=self._endpoint.node.node_id,
                        attr_path_filter=reachable_attr_path,
                    )
                )
        # If we are a composed device subscribe to the parent's Reachable attribute
        if self._compose_parent is not None and self._compose_parent.has_attribute(
            None, clusters.BridgedDeviceBasicInformation.Attributes.Reachable
        ):
            parent_reachable_attr_path = create_attribute_path(
                self._compose_parent.endpoint_id,
                clusters.BridgedDeviceBasicInformation.Attributes.Reachable.cluster_id,
                clusters.BridgedDeviceBasicInformation.Attributes.Reachable.attribute_id,
            )
            if parent_reachable_attr_path not in sub_paths:
                sub_paths.append(parent_reachable_attr_path)
                self.async_on_remove(
                    self.matter_client.subscribe_events(
                        callback=self._on_matter_event,
                        event_filter=EventType.ATTRIBUTE_UPDATED,
                        node_filter=self._compose_parent.node.node_id,
                        attr_path_filter=parent_reachable_attr_path,
                    )
                )
        # subscribe to FeatureMap attribute (as that can dynamically change)
        self.async_on_remove(
            self.matter_client.subscribe_events(
                callback=self._on_featuremap_update,
                event_filter=EventType.ATTRIBUTE_UPDATED,
                node_filter=self._endpoint.node.node_id,
                attr_path_filter=create_attribute_path(
                    endpoint=self._endpoint.endpoint_id,
                    cluster_id=self._entity_info.primary_attribute.cluster_id,
                    attribute_id=FEATUREMAP_ATTRIBUTE_ID,
                ),
            )
        )

    @cached_property
    @override
    def name(self) -> str | Undefined | None:
        """Return the name of the entity."""
        if hasattr(self, "_attr_name"):
            # an explicit entity name was defined, we use that
            return self._attr_name
        name = super().name
        if name and self._name_postfix:
            postfix = self._name_postfix
            if self._name_postfix_is_area_tag:
                translations = async_get_cached_translations(
                    self.hass, self.hass.config.language, "common", DOMAIN
                )
                postfix = translations.get(
                    f"component.{DOMAIN}.common.{postfix}", postfix
                )
            name = f"{name} ({postfix})"
        return name

    @cached_property
    def _compose_parent(self) -> MatterEndpoint | None:
        """Return the composed parent endpoint, if any."""
        return self._endpoint.node.get_compose_parent(self._endpoint.endpoint_id)

    @callback
    def _get_bridged_reachable(self) -> bool:
        """Return reachability state for bridged endpoints, True if not applicable."""
        # if we are the endpoint of a composed device, we have to check the
        # parent endpoint's reachable attribute
        if self._compose_parent is not None:
            compose_parent_reachable = self._compose_parent.get_attribute_value(
                None, clusters.BridgedDeviceBasicInformation.Attributes.Reachable
            )
            # assume unreachable only if there is an attribute present that
            # explicitly states reachable=false for the parent
            if compose_parent_reachable is not None and not compose_parent_reachable:
                return False
        # check if our endpoint has a reachable attribute
        # absence of reachable attribute is assumed as reachable (non-bridged devices)
        reachable = self.get_matter_attribute_value(
            clusters.BridgedDeviceBasicInformation.Attributes.Reachable
        )
        if reachable is None:
            return True
        return bool(reachable)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Handle being removed from Home Assistant."""
        await super().async_will_remove_from_hass()
        if self._write_state_debouncer is not None:
            self._write_state_debouncer.async_shutdown()
            self._write_state_debouncer = None

    @callback
    def _on_matter_event(self, event: EventType, data: Any = None) -> None:
        """Call on update from the device."""
        if event is EventType.NODE_UPDATED and self._required_attribute_removed():
            self._async_remove_unsupported()
            return
        self._attr_available = (
            self._endpoint.node.available and self._get_bridged_reachable()
        )
        self._update_from_device()
        if self._write_state_debouncer is not None:
            self._write_state_debouncer.async_schedule_call()
        else:
            self.async_write_ha_state()

    @callback
    def _on_featuremap_update(self, event: EventType, data: int | None) -> None:
        """Handle FeatureMap attribute updates."""
        if data is None:
            return
        # handle edge case where a Feature is removed from a cluster
        if self._feature_removed(data):
            # this entity is no longer supported by the device
            self._async_remove_unsupported()
            return
        # all other cases, just update the entity
        self._on_matter_event(event, data)

    @callback
    def _feature_removed(self, feature_map: int | None) -> bool:
        """Return if the FeatureMap no longer has the feature this entity needs."""
        featuremap_contains = self._entity_info.discovery_schema.featuremap_contains
        return (
            feature_map is not None
            and featuremap_contains is not None
            and not bool(feature_map & featuremap_contains)
        )

    @callback
    def _required_attribute_removed(self) -> bool:
        """Return if the node data no longer has a required attribute."""
        # Entities of an endpoint that left the node data are left to the endpoint removal
        if not self._endpoint.has_attribute(
            None, clusters.Descriptor.Attributes.DeviceTypeList
        ):
            return False
        return not all(
            self._endpoint.has_attribute(None, attribute)
            for attribute in self._entity_info.discovery_schema.required_attributes
        )

    @callback
    def _unsupported(self) -> bool:
        """Return if the device no longer supports this entity."""
        return self._required_attribute_removed() or self._feature_removed(
            self._endpoint.get_attribute_value(
                self._entity_info.primary_attribute.cluster_id,
                FEATUREMAP_ATTRIBUTE_ID,
            )
        )

    @callback
    def _async_remove_unsupported(self) -> None:
        """Remove this entity because the device no longer supports it."""
        if self._removal_scheduled:
            return
        self._removal_scheduled = True
        # Removing unsubscribes the entity, which must wait until the client has
        # finished calling the subscribers of the current event
        self.hass.loop.call_soon(self._async_remove_from_registry)

    @callback
    def _async_remove_from_registry(self) -> None:
        """Remove this entity from the entity registry if it is still unsupported."""
        self._removal_scheduled = False
        # a later event of the same batch may have restored the support
        if not self._unsupported():
            return
        entry = cast(MatterConfigEntry, self.platform.config_entry)
        # let discovery add the entity again if the device supports it later
        entry.runtime_data.adapter.discovered_entities.discard(
            get_discovery_key(self._endpoint, self._entity_info)
        )
        er.async_get(self.hass).async_remove(self.entity_id)

    @callback
    def _update_from_device(self) -> None:
        """Update data from Matter device."""

    @callback
    def get_matter_attribute_value(
        self, attribute: type[ClusterAttributeDescriptor], null_as_none: bool = True
    ) -> Any:
        """Get current value for given attribute."""
        value = self._endpoint.get_attribute_value(None, attribute)
        if null_as_none and value == NullValue:
            return None
        return value

    @callback
    def get_matter_attribute_path(
        self, attribute: type[ClusterAttributeDescriptor]
    ) -> str:
        """Return AttributePath by providing the endpoint and Attribute class."""
        return create_attribute_path(
            self._endpoint.endpoint_id, attribute.cluster_id, attribute.attribute_id
        )

    @catch_matter_error
    async def send_device_command(
        self,
        command: ClusterCommand,
        **kwargs: Any,
    ) -> Any:
        """Send device command on the primary attribute's endpoint."""
        return await self.matter_client.send_device_command(
            node_id=self._endpoint.node.node_id,
            endpoint_id=self._endpoint.endpoint_id,
            command=command,
            **kwargs,
        )

    @catch_matter_error
    async def write_attribute(
        self,
        value: Any,
        matter_attribute: type[ClusterAttributeDescriptor] | None = None,
    ) -> Any:
        """Write an attribute(value) on the primary endpoint.

        If matter_attribute is not provided, the primary attribute is used.
        """
        if matter_attribute is None:
            matter_attribute = self._entity_info.primary_attribute
        return await self.matter_client.write_attribute(
            node_id=self._endpoint.node.node_id,
            attribute_path=create_attribute_path_from_attribute(
                self._endpoint.endpoint_id,
                matter_attribute,
            ),
            value=value,
        )
