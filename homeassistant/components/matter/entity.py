"""Matter entity base class."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import IntEnum
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
from homeassistant.helpers.typing import UndefinedType

from .const import DOMAIN, FEATUREMAP_ATTRIBUTE_ID, ID_TYPE_DEVICE_ID
from .helpers import get_device_id

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint

    from .discovery import MatterEntityInfo

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


class _SwitchesNamespaceTag(IntEnum):
    """Tag values of the Matter "Switches" semantic tag namespace (0x43)."""

    ON = 0x00
    OFF = 0x01
    TOGGLE = 0x02
    UP = 0x03
    DOWN = 0x04
    NEXT = 0x05
    PREVIOUS = 0x06
    ENTER_OK_SELECT = 0x07
    CUSTOM = 0x08  # textual description provided in the Label field
    OPEN = 0x09
    CLOSE = 0x0A
    STOP = 0x0B


class _CommonPositionNamespaceTag(IntEnum):
    """Tag values of the Matter "Common Position" semantic tag namespace (0x08)."""

    LEFT = 0x00
    RIGHT = 0x01
    TOP = 0x02
    BOTTOM = 0x03
    MIDDLE = 0x04


# Translation key suffix (see strings.json) for each standard Switches tag,
# except CUSTOM which carries a free-text vendor label instead.
_SWITCHES_TAG_TRANSLATION_KEYS: dict[int, str] = {
    _SwitchesNamespaceTag.ON: "on",
    _SwitchesNamespaceTag.OFF: "off",
    _SwitchesNamespaceTag.TOGGLE: "toggle",
    _SwitchesNamespaceTag.UP: "up",
    _SwitchesNamespaceTag.DOWN: "down",
    _SwitchesNamespaceTag.NEXT: "next",
    _SwitchesNamespaceTag.PREVIOUS: "previous",
    _SwitchesNamespaceTag.ENTER_OK_SELECT: "enter_ok_select",
    _SwitchesNamespaceTag.OPEN: "open",
    _SwitchesNamespaceTag.CLOSE: "close",
    _SwitchesNamespaceTag.STOP: "stop",
}

# Order matters: when a device combines two of these tags (e.g. Top + Right
# for a corner position), they are read out in this canonical order so the
# result reads naturally ("Top Right", not "Right Top"), regardless of the
# order the device lists them in.
_COMMON_POSITION_TAG_TRANSLATION_KEYS: dict[int, str] = {
    _CommonPositionNamespaceTag.TOP: "top",
    _CommonPositionNamespaceTag.BOTTOM: "bottom",
    _CommonPositionNamespaceTag.MIDDLE: "middle",
    _CommonPositionNamespaceTag.LEFT: "left",
    _CommonPositionNamespaceTag.RIGHT: "right",
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
    _name_postfix_needs_translation = False
    _platform_translation_key: str | None = None
    # Cooldown in seconds to debounce state writes on updates from the device.
    # Platforms which derive their state from multiple attributes can set this
    # to coalesce attribute updates which arrive as separate events.
    _write_state_debounce_cooldown: float | None = None
    _write_state_debouncer: Debouncer[None] | None = None

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
        self._unsubscribes: list[Callable] = []
        # for fast lookups we create a mapping to the attribute paths
        self._attributes_map: dict[type, str] = {}
        # The server info is set when the client connects to the server.
        server_info = cast(ServerInfoMessage, self.matter_client.server_info)
        # create unique_id based on "Operational Instance Name" and endpoint/device type
        node_device_id = get_device_id(server_info, endpoint)
        self._attr_unique_id = (
            f"{node_device_id}-"
            f"{endpoint.endpoint_id}-"
            f"{entity_info.entity_description.key}-"
            f"{entity_info.primary_attribute.cluster_id}-"
            f"{entity_info.primary_attribute.attribute_id}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{ID_TYPE_DEVICE_ID}_{node_device_id}")}
        )
        self._attr_available = (
            self._endpoint.node.available and self._get_bridged_reachable()
        )
        # mark endpoint postfix if the device has the primary
        # attribute on multiple endpoints
        if not self._endpoint.node.is_bridge_device and any(
            ep
            for ep in self._endpoint.node.endpoints.values()
            if ep != self._endpoint
            and ep.has_attribute(None, entity_info.primary_attribute)
        ):
            self._name_postfix = str(self._endpoint.endpoint_id)
        # Always set translation_key for state_attributes translations.
        # For primary entities (no postfix), suppress the translated name,
        # so only the device name is used.
        if self._platform_translation_key and not self.translation_key:
            self._attr_translation_key = self._platform_translation_key
            if not self._name_postfix:
                self._attr_name = None

        # Matter labels or semantic tags (Descriptor TagList) can be used to
        # modify the entity name by appending the text. Structured semantic
        # tags (position/action) are preferred over a Custom tag's free-text
        # label, which often just repeats the entity's own generic name
        # (e.g. a "button 1" label on an entity already named "Button").
        if name_modifier := self._get_name_modifier():
            self._name_postfix = name_modifier
        elif self._has_translatable_semantic_tag_name_modifier():
            # the translated word is only known once platform translations
            # are available, so defer the lookup to `name`
            self._name_postfix_needs_translation = True
        elif name_modifier := self._find_untranslated_semantic_tag_name_modifier():
            self._name_postfix = name_modifier

        # make sure to update the attributes once
        self._update_from_device()

    def _find_matching_labels(self) -> list[str]:
        """Find all labels for a Matter entity."""

        device_info = self._endpoint.device_info
        labeling_list = VENDOR_LABELING_LIST.get(device_info.vendorID, {}).get(
            device_info.productID
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

    def _get_name_modifier(self) -> str | None:
        """Get the name modifier for the entity."""

        if found_labels := self._find_matching_labels():
            return found_labels[0]
        return None

    def _get_semantic_tags(self) -> list[clusters.Globals.Structs.semtag]:
        """Get the semantic tags (Descriptor TagList) for the endpoint."""
        return (
            self.get_matter_attribute_value(clusters.Descriptor.Attributes.TagList)
            or []
        )

    def _has_translatable_semantic_tag_name_modifier(self) -> bool:
        """Return whether the endpoint has a semantic tag that needs translation.

        Used to decide, at __init__ time, whether the (higher-priority)
        translated tier applies, without yet resolving the actual translated
        word, which requires platform translations that are not available
        until the entity has been added to hass (see `name`).
        """
        namespace = clusters.Globals.Enums.namespace
        return any(
            (
                tag.namespaceID == namespace.kCommonPosition
                and tag.tag in _COMMON_POSITION_TAG_TRANSLATION_KEYS
            )
            or (
                tag.namespaceID == namespace.kSwitches
                and tag.tag in _SWITCHES_TAG_TRANSLATION_KEYS
            )
            for tag in self._get_semantic_tags()
        )

    def _find_untranslated_semantic_tag_name_modifier(self) -> str | None:
        """Find a name modifier from the endpoint's semantic tags.

        Only used as a fallback when no structured, translatable tag
        (Common Position or Switches action) is present. Handles the tags
        that need no translation: a Common Number tag (whose value is a
        plain, language-independent digit) or, as a last resort, an explicit
        vendor-supplied Custom tag label.
        """
        namespace = clusters.Globals.Enums.namespace
        tags = self._get_semantic_tags()
        for tag in tags:
            if tag.namespaceID == namespace.kCommonNumber:
                return str(tag.tag)
        for tag in tags:
            if (
                tag.namespaceID == namespace.kSwitches
                and tag.tag == _SwitchesNamespaceTag.CUSTOM
                and isinstance(tag.label, str)
            ):
                return tag.label
        return None

    def _find_translated_semantic_tag_name_modifier(self) -> str | None:
        """Find a translated name modifier from the endpoint's semantic tags.

        Handles the tags whose meaning is a word that needs translation
        (a position or an action), so it can only run once platform
        translations are available (see `_name_postfix_needs_translation`).
        A namespace can carry multiple tags at once (e.g. Top + Right for a
        corner position), in which case all of them are combined.
        """
        namespace = clusters.Globals.Enums.namespace
        tags = self._get_semantic_tags()
        if words := self._translate_semantic_tags(
            tags, namespace.kCommonPosition, _COMMON_POSITION_TAG_TRANSLATION_KEYS
        ):
            return " ".join(words)
        if words := self._translate_semantic_tags(
            tags, namespace.kSwitches, _SWITCHES_TAG_TRANSLATION_KEYS
        ):
            return " ".join(words)
        return None

    def _translate_semantic_tags(
        self,
        tags: list[clusters.Globals.Structs.semtag],
        namespace_id: int,
        translation_keys: dict[int, str],
    ) -> list[str]:
        """Translate all semantic tags of a given namespace present on the endpoint.

        Words are combined in the canonical order of `translation_keys`,
        regardless of the order the device lists the tags in.
        """
        device_tags = {tag.tag for tag in tags if tag.namespaceID == namespace_id}
        words = []
        for tag_id, translation_key in translation_keys.items():
            if tag_id not in device_tags:
                continue
            if translated := self._translate_semantic_tag(translation_key):
                words.append(translated)
        return words

    def _translate_semantic_tag(self, translation_key: str) -> str | None:
        """Look up the translated word for a semantic tag."""
        platform_data = self.platform_data
        full_key = (
            f"component.{platform_data.platform_name}.entity.{platform_data.domain}"
            f".matter_semantic_tag_{translation_key}.name"
        )
        return platform_data.platform_translations.get(full_key)

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
            self._unsubscribes.append(
                self.matter_client.subscribe_events(
                    callback=self._on_matter_event,
                    event_filter=EventType.ATTRIBUTE_UPDATED,
                    node_filter=self._endpoint.node.node_id,
                    attr_path_filter=attr_path,
                )
            )
        # subscribe to node (availability changes)
        self._unsubscribes.append(
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
                self._unsubscribes.append(
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
                self._unsubscribes.append(
                    self.matter_client.subscribe_events(
                        callback=self._on_matter_event,
                        event_filter=EventType.ATTRIBUTE_UPDATED,
                        node_filter=self._compose_parent.node.node_id,
                        attr_path_filter=parent_reachable_attr_path,
                    )
                )
        # subscribe to FeatureMap attribute (as that can dynamically change)
        self._unsubscribes.append(
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
    def name(self) -> str | UndefinedType | None:
        """Return the name of the entity."""
        if hasattr(self, "_attr_name"):
            # an explicit entity name was defined, we use that
            return self._attr_name
        name = super().name
        postfix = self._name_postfix
        if self._name_postfix_needs_translation and (
            translated := self._find_translated_semantic_tag_name_modifier()
        ):
            postfix = translated
        if name and postfix:
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
        if (
            self._entity_info.discovery_schema.featuremap_contains is not None
            and not bool(data & self._entity_info.discovery_schema.featuremap_contains)
        ):
            # this entity is no longer supported by the device
            ent_reg = er.async_get(self.hass)
            ent_reg.async_remove(self.entity_id)

            return
        # all other cases, just update the entity
        self._on_matter_event(event, data)

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
