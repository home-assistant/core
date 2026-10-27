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
    ROW = 0x05  # numeral provided in the Label field
    COLUMN = 0x06  # numeral provided in the Label field


# Entities whose (entity-description-level) translation_key this postfix
# logic applies to: the Generic Switch event and its current-position
# sensor, i.e. the stateless, non-output controls this is meant for. It
# deliberately excludes e.g. Identify buttons and output-unit entities
# (lights, outlets, covers), which #186033's child devices will eventually
# own, so the same endpoint doesn't get inconsistent names across its
# entities, and so there's no overlap with that migration's scope.
_SEMANTIC_TAG_SCOPED_TRANSLATION_KEYS = frozenset({"button", "switch_current_position"})

# Translation key suffix (see strings.json) for each combination of Common
# Position tags this recognizes. A combination not listed here is not used:
# the spec only guarantees distinct tags between siblings, not that every
# combination maps to a sensible English phrase.
_POSITION_TAG_SUFFIXES: dict[frozenset[int], str] = {
    frozenset({_CommonPositionNamespaceTag.TOP}): "top",
    frozenset({_CommonPositionNamespaceTag.BOTTOM}): "bottom",
    frozenset({_CommonPositionNamespaceTag.LEFT}): "left",
    frozenset({_CommonPositionNamespaceTag.RIGHT}): "right",
    frozenset({_CommonPositionNamespaceTag.MIDDLE}): "middle",
    frozenset(
        {_CommonPositionNamespaceTag.TOP, _CommonPositionNamespaceTag.LEFT}
    ): "top_left",
    frozenset(
        {_CommonPositionNamespaceTag.TOP, _CommonPositionNamespaceTag.RIGHT}
    ): "top_right",
    frozenset(
        {_CommonPositionNamespaceTag.BOTTOM, _CommonPositionNamespaceTag.LEFT}
    ): "bottom_left",
    frozenset(
        {_CommonPositionNamespaceTag.BOTTOM, _CommonPositionNamespaceTag.RIGHT}
    ): "bottom_right",
}

# Same idea for Switches tags, except CUSTOM (free-text label, handled
# separately) and ON/OFF/etc. combined with each other (not a real device
# pattern). TOGGLE + NEXT + PREVIOUS is the one combination seen in the
# wild (a 3-way rocker button).
_SWITCHES_TAG_SUFFIXES: dict[frozenset[int], str] = {
    frozenset({_SwitchesNamespaceTag.ON}): "on",
    frozenset({_SwitchesNamespaceTag.OFF}): "off",
    frozenset({_SwitchesNamespaceTag.TOGGLE}): "toggle",
    frozenset({_SwitchesNamespaceTag.UP}): "up",
    frozenset({_SwitchesNamespaceTag.DOWN}): "down",
    frozenset({_SwitchesNamespaceTag.NEXT}): "next",
    frozenset({_SwitchesNamespaceTag.PREVIOUS}): "previous",
    frozenset({_SwitchesNamespaceTag.ENTER_OK_SELECT}): "enter_ok_select",
    frozenset({_SwitchesNamespaceTag.OPEN}): "open",
    frozenset({_SwitchesNamespaceTag.CLOSE}): "close",
    frozenset({_SwitchesNamespaceTag.STOP}): "stop",
    frozenset(
        {
            _SwitchesNamespaceTag.TOGGLE,
            _SwitchesNamespaceTag.NEXT,
            _SwitchesNamespaceTag.PREVIOUS,
        }
    ): "toggle_next_previous",
}

# Row/Column combined with each Switches suffix that's registered as a
# translation (see strings.json): a numbered rocker/rotary control.
_ROW_COLUMN_SWITCHES_SUFFIXES = frozenset({"up", "down", "toggle_next_previous"})


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
        needs_disambiguation = not self._endpoint.node.is_bridge_device and any(
            ep
            for ep in self._endpoint.node.endpoints.values()
            if ep != self._endpoint
            and ep.has_attribute(None, entity_info.primary_attribute)
        )
        if needs_disambiguation:
            self._name_postfix = str(self._endpoint.endpoint_id)
        # Always set translation_key for state_attributes translations.
        # For primary entities (no postfix), suppress the translated name,
        # so only the device name is used.
        if self._platform_translation_key and not self.translation_key:
            self._attr_translation_key = self._platform_translation_key
            if not self._name_postfix:
                self._attr_name = None

        # Matter labels can be used to modify the entity name by appending
        # the text.
        if name_modifier := self._get_name_modifier():
            self._name_postfix = name_modifier
        elif (
            needs_disambiguation
            and self.translation_key in _SEMANTIC_TAG_SCOPED_TRANSLATION_KEYS
            and (own_variant := self._semantic_tag_variant(self._endpoint))
            and not self._semantic_tag_disambiguation_conflicts(own_variant)
        ):
            # Semantic tags (Descriptor TagList) are a second source for a
            # name modifier, limited to the Generic Switch entities this is
            # meant for (see `_SEMANTIC_TAG_SCOPED_TRANSLATION_KEYS`) and
            # only applied if every sibling endpoint that needs
            # disambiguation gets a distinct one from it; otherwise the
            # numeric postfix set above is kept for all of them.
            kind, payload, placeholders = own_variant
            if kind == "translated":
                # one translation key per full combination (not individual
                # words glued together), so translators see the whole
                # phrase and can reorder it for their language. The new key's
                # own name string already carries the modifier, replacing
                # the numeric postfix set above.
                self._name_postfix = None
                self._attr_translation_key = f"{self.translation_key}_{payload}"
                if placeholders:
                    self._attr_translation_placeholders = dict(placeholders)
            else:
                # "number" (a plain, language-independent digit) or
                # "custom" (a vendor-supplied free-text label): used as-is,
                # no translation needed
                self._name_postfix = payload

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

    def _get_name_modifier(self) -> str | None:
        """Get the name modifier for the entity."""

        if found_labels := self._find_matching_labels():
            return found_labels[0]
        return None

    def _get_semantic_tags(
        self, endpoint: MatterEndpoint
    ) -> list[clusters.Globals.Structs.semtag]:
        """Get the semantic tags (Descriptor TagList) for an endpoint.

        A tag from a manufacturer-specific namespace (mfgCode set) is
        excluded: its namespace/tag ids are vendor-defined and must not be
        read as one of the standard namespaces below.
        """
        tags = endpoint.get_attribute_value(
            None, clusters.Descriptor.Attributes.TagList
        )
        return [tag for tag in tags or [] if tag.mfgCode in (None, NullValue)]

    def _semantic_tag_variant(
        self, endpoint: MatterEndpoint
    ) -> tuple[str, str, tuple[tuple[str, str], ...]] | None:
        """Return a language-independent identity for endpoint's semantic tags.

        ("translated", key_suffix, placeholders) for a structured
        combination of Common Position and/or Switches tags this
        recognizes (see `_POSITION_TAG_SUFFIXES`/`_SWITCHES_TAG_SUFFIXES`);
        ("number", value) for a plain Common Number tag; ("custom", label)
        for a vendor Custom tag label. None if nothing usable is present,
        or if the combination present isn't one this recognizes.

        Comparing this identity rather than the resolved text lets sibling
        endpoints be checked against each other for a naming conflict
        before platform translations are available (see
        `_semantic_tag_disambiguation_conflicts`).
        """
        namespace = clusters.Globals.Enums.namespace
        tags = self._get_semantic_tags(endpoint)
        position_tags = {
            tag.tag for tag in tags if tag.namespaceID == namespace.kCommonPosition
        }
        # CUSTOM is excluded here: it's not a structured action and has no
        # registered suffix, it's handled by the literal fallback below.
        switches_tags = {
            tag.tag
            for tag in tags
            if tag.namespaceID == namespace.kSwitches
            and tag.tag != _SwitchesNamespaceTag.CUSTOM
        }

        key_parts: list[str] = []
        placeholders: dict[str, str] = {}
        for axis, axis_tag in (
            ("row", _CommonPositionNamespaceTag.ROW),
            ("column", _CommonPositionNamespaceTag.COLUMN),
        ):
            if axis_tag not in position_tags:
                continue
            label = next(
                (
                    tag.label
                    for tag in tags
                    if tag.namespaceID == namespace.kCommonPosition
                    and tag.tag == axis_tag
                    and isinstance(tag.label, str)
                ),
                None,
            )
            if label is None:
                # the spec requires a numeral label here; without one this
                # tag can't be used
                return None
            key_parts.append(axis)
            placeholders[axis] = label

        if placeholders:
            # Row/Column (numeral labels) and the word-based positions
            # below are mutually exclusive on a single endpoint in the
            # combinations this recognizes.
            if position_tags - {
                _CommonPositionNamespaceTag.ROW,
                _CommonPositionNamespaceTag.COLUMN,
            }:
                return None
            # A Switches tag combines with Row/Column (a numbered
            # rocker/rotary control), but only one this is registered for.
            if switches_tags:
                suffix = _SWITCHES_TAG_SUFFIXES.get(frozenset(switches_tags))
                if suffix is None or suffix not in _ROW_COLUMN_SWITCHES_SUFFIXES:
                    return None
                key_parts.append(suffix)
        elif position_tags:
            # A word-based position, once resolved, is used on its own:
            # any Switches tags also present (e.g. a Custom label repeating
            # what the position already says) are not needed to tell this
            # endpoint apart from its siblings and are ignored.
            suffix = _POSITION_TAG_SUFFIXES.get(frozenset(position_tags))
            if suffix is None:
                return None
            key_parts.append(suffix)
        elif switches_tags:
            # No position at all: a Switches action tag is the fallback.
            suffix = _SWITCHES_TAG_SUFFIXES.get(frozenset(switches_tags))
            if suffix is None:
                return None
            key_parts.append(suffix)

        if key_parts:
            return (
                "translated",
                "_".join(key_parts),
                tuple(sorted(placeholders.items())),
            )

        number = next(
            (tag.tag for tag in tags if tag.namespaceID == namespace.kCommonNumber),
            None,
        )
        if number is not None:
            return ("number", str(number), ())

        custom_label = next(
            (
                tag.label
                for tag in tags
                if tag.namespaceID == namespace.kSwitches
                and tag.tag == _SwitchesNamespaceTag.CUSTOM
                and isinstance(tag.label, str)
            ),
            None,
        )
        if custom_label is not None:
            return ("custom", custom_label, ())

        return None

    def _endpoint_has_label_modifier(self, endpoint: MatterEndpoint) -> bool:
        """Return whether endpoint has a vendor label that would modify its name.

        Mirrors `_find_matching_labels`, for a sibling endpoint: such an
        endpoint already gets its name from that unrelated, pre-existing
        mechanism, so it doesn't need a semantic tag of its own to be
        considered covered by `_semantic_tag_disambiguation_conflicts`.
        """
        device_info = endpoint.device_info
        if device_info is None:
            return False
        labeling_list = VENDOR_LABELING_LIST.get(device_info.vendorID, {}).get(
            device_info.productID
        )
        if not labeling_list:
            return False
        user_label_list = (
            endpoint.get_attribute_value(None, clusters.UserLabel.Attributes.LabelList)
            or []
        )
        fixed_label_list = (
            endpoint.get_attribute_value(None, clusters.FixedLabel.Attributes.LabelList)
            or []
        )
        return any(
            lbl.label.lower() in labeling_list
            for lbl in (*user_label_list, *fixed_label_list)
        )

    def _semantic_tag_disambiguation_conflicts(
        self, own_variant: tuple[str, str, tuple[tuple[str, str], ...]]
    ) -> bool:
        """Return whether `own_variant` can't safely be used as a name modifier.

        True if a sibling endpoint that also needs disambiguation, and
        doesn't already get its name some other way (a vendor label), has
        no semantic-tag variant of its own, or has the same one as this
        endpoint: the spec only guarantees that the whole set of tags
        differs between such siblings, not that the subset this looks at
        does, or that it maps to a distinct name.
        """
        return any(
            not self._endpoint_has_label_modifier(ep)
            and self._semantic_tag_variant(ep) in (None, own_variant)
            for ep in self._endpoint.node.endpoints.values()
            if ep != self._endpoint
            and ep.has_attribute(None, self._entity_info.primary_attribute)
        )

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
    def name(self) -> str | UndefinedType | None:
        """Return the name of the entity."""
        if hasattr(self, "_attr_name"):
            # an explicit entity name was defined, we use that
            return self._attr_name
        name = super().name
        if name and self._name_postfix:
            name = f"{name} ({self._name_postfix})"
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
