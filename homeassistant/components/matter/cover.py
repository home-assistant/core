"""Matter cover."""

from dataclasses import dataclass
from enum import IntEnum
from math import floor
from typing import TYPE_CHECKING, Any, override

from chip.clusters import Objects as clusters
from matter_server.common.helpers.util import create_attribute_path
from matter_server.common.models import EventType
from propcache.api import cached_property

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .entity import MatterEntity, MatterEntityDescription
from .helpers import MatterConfigEntry
from .models import MatterDiscoverySchema

if TYPE_CHECKING:
    from matter_server.client.models.node import MatterEndpoint

# The MASK used for extracting bits 0 to 1 of the byte.
OPERATIONAL_STATUS_MASK = 0b11

# Cover state is derived from both the operational status and the current
# position, which some devices report as separate attribute updates shortly
# after each other (e.g. stopped before the final position). Debounce state
# writes to avoid writing intermittent states.
STATE_WRITE_DEBOUNCE_COOLDOWN = 0.1

# map Matter window cover types to HA device class
TYPE_MAP = {
    clusters.WindowCovering.Enums.Type.kRollerShade: CoverDeviceClass.SHADE,
    clusters.WindowCovering.Enums.Type.kRollerShade2Motor: CoverDeviceClass.SHADE,
    clusters.WindowCovering.Enums.Type.kRollerShadeExterior: CoverDeviceClass.SHADE,
    clusters.WindowCovering.Enums.Type.kRollerShadeExterior2Motor: (
        CoverDeviceClass.SHADE
    ),
    clusters.WindowCovering.Enums.Type.kAwning: CoverDeviceClass.AWNING,
    clusters.WindowCovering.Enums.Type.kDrapery: CoverDeviceClass.CURTAIN,
    clusters.WindowCovering.Enums.Type.kTiltBlindTiltOnly: CoverDeviceClass.BLIND,
    clusters.WindowCovering.Enums.Type.kTiltBlindLiftAndTilt: CoverDeviceClass.BLIND,
}

# Semantic tag namespace IDs (Matter 1.5 data model) used to disambiguate
# Closure devices. Namespace-Closure.xml (id 0x44) is the generic closure
# kind (window, gate, door, garage door, ...); Namespace-Closure-Covering.xml
# (id 0x46) narrows down what kind of covering it is when it's one;
# Namespace-ClosurePanel.xml (id 0x45) describes which axis a ClosurePanel
# child endpoint controls.
NAMESPACE_CLOSURE = 68
NAMESPACE_CLOSURE_PANEL = 69
NAMESPACE_CLOSURE_COVERING = 70

# Checked first: Closure.Covering + a more specific Covering.* tag always
# wins over the generic Closure.* tag below (e.g. Covering.Venetian).
CLOSURE_COVERING_TAG_TO_DEVICE_CLASS = {
    0: CoverDeviceClass.BLIND,  # Blind
    1: CoverDeviceClass.AWNING,  # Awning
    2: CoverDeviceClass.SHUTTER,  # Shutter
    3: CoverDeviceClass.BLIND,  # Venetian
    4: CoverDeviceClass.CURTAIN,  # Curtain
}
CLOSURE_TAG_TO_DEVICE_CLASS = {
    1: CoverDeviceClass.WINDOW,  # Window (e.g. a rotating roof window)
    4: CoverDeviceClass.GATE,  # Gate
    5: CoverDeviceClass.GARAGE,  # GarageDoor
    6: CoverDeviceClass.DOOR,  # Door
}


class ClosurePanelRole(IntEnum):
    """Functional role of a ClosurePanel child endpoint.

    Lift, Sliding and Rotate are all a panel's primary, continuous
    opening amount - a roof window rotating open (ClosureWindow.Roof)
    is exactly as much a 0-100% position as a blind's Lift, just
    achieved by a different physical motion - so they all drive
    current_cover_position. Tilt is the only secondary axis, paired
    with a primary one on venetian-blind-style panels.
    """

    POSITION = 0
    TILT = 1


class OperationalStatus(IntEnum):
    """Ongoing operations enumeration for coverings per Matter spec."""

    COVERING_IS_CURRENTLY_NOT_MOVING = 0b00
    COVERING_IS_CURRENTLY_OPENING = 0b01
    COVERING_IS_CURRENTLY_CLOSING = 0b10
    RESERVED = 0b11


def _extract_struct_field(value: Any, index: int, attr_name: str) -> Any:
    """Extract a field from a Matter struct value.

    Matter server can expose cluster struct attributes either as objects or
    simple dictionaries keyed by the TLV field index. We normalize access by
    first checking dict keys and falling back to attribute lookup.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        if index in value:
            return value[index]
        if (index_str := str(index)) in value:
            return value[index_str]
    return getattr(value, attr_name, None)


def _get_closure_device_class(tag_list: Any) -> CoverDeviceClass:
    """Return the HA device class for a Closure endpoint from its TagList."""
    fallback_device_class: CoverDeviceClass | None = None
    for tag in tag_list or ():
        namespace_id = _extract_struct_field(tag, 1, "namespaceID")
        tag_id = _extract_struct_field(tag, 2, "tag")
        if namespace_id == NAMESPACE_CLOSURE_COVERING:
            if (
                device_class := CLOSURE_COVERING_TAG_TO_DEVICE_CLASS.get(tag_id)
            ) is not None:
                return device_class
        elif namespace_id == NAMESPACE_CLOSURE and fallback_device_class is None:
            fallback_device_class = CLOSURE_TAG_TO_DEVICE_CLASS.get(tag_id)
    return fallback_device_class or CoverDeviceClass.GARAGE


CLOSURE_PANEL_TAG_TO_ROLE = {
    0: ClosurePanelRole.POSITION,  # Lift
    1: ClosurePanelRole.TILT,  # Tilt
    2: ClosurePanelRole.POSITION,  # Sliding
    3: ClosurePanelRole.POSITION,  # Rotate
}


def _get_closure_panel_role(tag_list: Any) -> ClosurePanelRole | None:
    """Return the functional role of a ClosurePanel endpoint from its TagList."""
    for tag in tag_list or ():
        if _extract_struct_field(tag, 1, "namespaceID") != NAMESPACE_CLOSURE_PANEL:
            continue
        role = CLOSURE_PANEL_TAG_TO_ROLE.get(_extract_struct_field(tag, 2, "tag"))
        if role is not None:
            return role
    return None


def _percent100ths_to_ha_position(value: int | None) -> int | None:
    """Convert a Matter percent100ths value to a HA 0-100 cover position.

    Matter position is inverted compared to HA (100% is closed, 0% is open).
    """
    if value is None:
        return None
    return 100 - floor(value / 100)


def _ha_position_to_percent100ths(position: int) -> int:
    """Convert a HA 0-100 cover position to a Matter percent100ths value."""
    return (100 - position) * 100


def _feature_supported(
    endpoint: MatterEndpoint,
    feature_map_attribute: type[clusters.ClusterAttributeDescriptor],
    feature: int,
) -> bool:
    """Return True if the given endpoint's FeatureMap contains `feature`."""
    feature_map = endpoint.get_attribute_value(None, feature_map_attribute)
    if not isinstance(feature_map, int):
        return False
    return bool(feature_map & feature)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MatterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter Cover from Config Entry."""
    matter = config_entry.runtime_data.adapter
    matter.register_platform_handler(Platform.COVER, async_add_entities)


@dataclass(frozen=True, kw_only=True)
class MatterCoverEntityDescription(CoverEntityDescription, MatterEntityDescription):
    """Describe Matter Cover entities."""


class MatterCover(MatterEntity, CoverEntity):
    """Representation of a Matter Cover."""

    _write_state_debounce_cooldown = STATE_WRITE_DEBOUNCE_COOLDOWN
    entity_description: MatterCoverEntityDescription

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return true if cover is closed, None if no position."""
        if not self._entity_info.endpoint.has_attribute(
            None, clusters.WindowCovering.Attributes.CurrentPositionLiftPercent100ths
        ):
            return None

        return (
            self.current_cover_position == 0
            if self.current_cover_position is not None
            else None
        )

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover movement."""
        await self.send_device_command(clusters.WindowCovering.Commands.StopMotion())

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.send_device_command(clusters.WindowCovering.Commands.UpOrOpen())

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.send_device_command(clusters.WindowCovering.Commands.DownOrClose())

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        await self.send_device_command(
            clusters.WindowCovering.Commands.GoToLiftPercentage(
                _ha_position_to_percent100ths(position)
            )
        )

    @override
    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Set the cover tilt to a specific position."""
        position = kwargs[ATTR_TILT_POSITION]
        await self.send_device_command(
            clusters.WindowCovering.Commands.GoToTiltPercentage(
                _ha_position_to_percent100ths(position)
            )
        )

    @callback
    @override
    def _update_from_device(self) -> None:
        """Update from device."""
        operational_status = self.get_matter_attribute_value(
            clusters.WindowCovering.Attributes.OperationalStatus
        )

        assert operational_status is not None

        LOGGER.debug(
            "Operational status %s for %s",
            f"{operational_status:#010b}",
            self.entity_id,
        )

        state = operational_status & OPERATIONAL_STATUS_MASK
        match state:
            case OperationalStatus.COVERING_IS_CURRENTLY_OPENING:
                self._attr_is_opening = True
                self._attr_is_closing = False
            case OperationalStatus.COVERING_IS_CURRENTLY_CLOSING:
                self._attr_is_opening = False
                self._attr_is_closing = True
            case _:
                self._attr_is_opening = False
                self._attr_is_closing = False

        if self._entity_info.endpoint.has_attribute(
            None, clusters.WindowCovering.Attributes.CurrentPositionLiftPercent100ths
        ):
            current_cover_position = self.get_matter_attribute_value(
                clusters.WindowCovering.Attributes.CurrentPositionLiftPercent100ths
            )
            self._attr_current_cover_position = _percent100ths_to_ha_position(
                current_cover_position
            )

            LOGGER.debug(
                "Current position for %s - raw: %s - corrected: %s",
                self.entity_id,
                current_cover_position,
                self.current_cover_position,
            )

        if self._entity_info.endpoint.has_attribute(
            None, clusters.WindowCovering.Attributes.CurrentPositionTiltPercent100ths
        ):
            current_cover_tilt_position = self.get_matter_attribute_value(
                clusters.WindowCovering.Attributes.CurrentPositionTiltPercent100ths
            )
            self._attr_current_cover_tilt_position = _percent100ths_to_ha_position(
                current_cover_tilt_position
            )

            LOGGER.debug(
                "Current tilt position for %s - raw: %s - corrected: %s",
                self.entity_id,
                current_cover_tilt_position,
                self.current_cover_tilt_position,
            )

        # map matter type to HA deviceclass
        device_type: clusters.WindowCovering.Enums.Type = (
            self.get_matter_attribute_value(clusters.WindowCovering.Attributes.Type)
        )
        self._attr_device_class = TYPE_MAP.get(device_type, CoverDeviceClass.AWNING)

        supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )
        commands = self.get_matter_attribute_value(
            clusters.WindowCovering.Attributes.AcceptedCommandList
        )
        if clusters.WindowCovering.Commands.GoToLiftPercentage.command_id in commands:
            supported_features |= CoverEntityFeature.SET_POSITION
        if clusters.WindowCovering.Commands.GoToTiltPercentage.command_id in commands:
            supported_features |= CoverEntityFeature.SET_TILT_POSITION
        self._attr_supported_features = supported_features


class MatterClosure(MatterEntity, CoverEntity):
    """Representation of a Matter Closure (garage door, blind, roof window, etc.) cover.

    The ClosureControl cluster on this entity's own endpoint provides coarse
    Open/Close/Stop (no arbitrary position). Devices with a continuous
    opening amount and/or a distinct Tilt axis (e.g. venetian blinds, roof
    windows) additionally expose one or more child ClosurePanel endpoints,
    listed in this endpoint's Descriptor PartsList and each carrying its own
    ClosureDimension cluster for fine positioning. Those children are
    resolved lazily via `_closure_panels` and drive
    `current_cover_position`/`current_cover_tilt_position`.
    """

    _write_state_debounce_cooldown = STATE_WRITE_DEBOUNCE_COOLDOWN

    @cached_property
    def _closure_panels(self) -> dict[ClosurePanelRole, MatterEndpoint]:
        """Return the ClosurePanel child endpoints, if any, by functional role."""
        node = self._endpoint.node
        panels: dict[ClosurePanelRole, MatterEndpoint] = {}
        for child_id in node.get_compose_child_ids(self._endpoint.endpoint_id) or ():
            child = node.endpoints[child_id]
            if not child.has_cluster(clusters.ClosureDimension):
                continue
            tag_list = child.get_attribute_value(
                None, clusters.Descriptor.Attributes.TagList
            )
            if (role := _get_closure_panel_role(tag_list)) is not None:
                panels[role] = child
        return panels

    @override
    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await super().async_added_to_hass()
        # Subscribe to the ClosurePanel child endpoints' state:
        # these live on a different endpoint than the ones already
        # subscribed to by the base class for `self._endpoint`.
        for panel in self._closure_panels.values():
            self._unsubscribes.append(
                self.matter_client.subscribe_events(
                    callback=self._on_matter_event,
                    event_filter=EventType.ATTRIBUTE_UPDATED,
                    node_filter=self._endpoint.node.node_id,
                    attr_path_filter=create_attribute_path(
                        panel.endpoint_id,
                        clusters.ClosureDimension.Attributes.CurrentState.cluster_id,
                        clusters.ClosureDimension.Attributes.CurrentState.attribute_id,
                    ),
                )
            )

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the closure."""
        command_kwargs: dict[str, Any] = {
            "position": clusters.ClosureControl.Enums.TargetPositionEnum.kMoveToFullyOpen
        }
        if self._motion_latching_supported():
            command_kwargs["latch"] = False
        await self.send_device_command(
            clusters.ClosureControl.Commands.MoveTo(**command_kwargs),
            timed_request_timeout_ms=1000,
        )

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the closure."""
        command_kwargs: dict[str, Any] = {
            "position": clusters.ClosureControl.Enums.TargetPositionEnum.kMoveToFullyClosed
        }
        if self._motion_latching_supported():
            command_kwargs["latch"] = False
        await self.send_device_command(
            clusters.ClosureControl.Commands.MoveTo(**command_kwargs),
            timed_request_timeout_ms=1000,
        )

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop movement."""
        await self.send_device_command(
            clusters.ClosureControl.Commands.Stop(),
            timed_request_timeout_ms=1000,
        )

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover's position, via its primary ClosurePanel child endpoint."""
        panel = self._closure_panels[ClosurePanelRole.POSITION]
        await self._set_panel_target(panel, kwargs[ATTR_POSITION])

    @override
    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Set the cover's Tilt position, via its ClosurePanel child endpoint."""
        panel = self._closure_panels[ClosurePanelRole.TILT]
        await self._set_panel_target(panel, kwargs[ATTR_TILT_POSITION])

    async def _set_panel_target(self, panel: MatterEndpoint, position: int) -> None:
        """Send SetTarget to a ClosurePanel child endpoint.

        A latched panel rejects SetTarget with InvalidInState until it's
        explicitly unlatched, so unlatch as part of the move when the panel
        supports it (mirrors the parent's MoveTo `latch=False` above).
        """
        command_kwargs: dict[str, Any] = {
            "position": _ha_position_to_percent100ths(position)
        }
        if _feature_supported(
            panel,
            clusters.ClosureDimension.Attributes.FeatureMap,
            clusters.ClosureDimension.Bitmaps.Feature.kMotionLatching,
        ):
            command_kwargs["latch"] = False
        await self.send_device_command(
            clusters.ClosureDimension.Commands.SetTarget(**command_kwargs),
            endpoint=panel,
            timed_request_timeout_ms=1000,
        )

    @callback
    @override
    def _update_from_device(self) -> None:
        """Update the entity from ClosureControl and ClosureDimension attributes."""
        self._attr_device_class = _get_closure_device_class(
            self.get_matter_attribute_value(clusters.Descriptor.Attributes.TagList)
        )

        overall_current_state = self.get_matter_attribute_value(
            clusters.ClosureControl.Attributes.OverallCurrentState
        )
        main_state = self.get_matter_attribute_value(
            clusters.ClosureControl.Attributes.MainState
        )
        overall_target_state = self.get_matter_attribute_value(
            clusters.ClosureControl.Attributes.OverallTargetState
        )

        position = _extract_struct_field(overall_current_state, 0, "position")
        target_position = _extract_struct_field(overall_target_state, 0, "position")

        if isinstance(position, int):
            position = clusters.ClosureControl.Enums.CurrentPositionEnum(position)
        if isinstance(target_position, int):
            target_position = clusters.ClosureControl.Enums.TargetPositionEnum(
                target_position
            )
        if isinstance(main_state, int):
            main_state = clusters.ClosureControl.Enums.MainStateEnum(main_state)

        if position is None:
            self._attr_is_closed = None
        else:
            self._attr_is_closed = (
                position
                == clusters.ClosureControl.Enums.CurrentPositionEnum.kFullyClosed
            )

        self._attr_is_opening = False
        self._attr_is_closing = False
        if main_state == clusters.ClosureControl.Enums.MainStateEnum.kMoving:
            if (
                target_position
                == clusters.ClosureControl.Enums.TargetPositionEnum.kMoveToFullyOpen
            ):
                self._attr_is_opening = True
            elif (
                target_position
                == clusters.ClosureControl.Enums.TargetPositionEnum.kMoveToFullyClosed
            ):
                self._attr_is_closing = True

        supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )
        if position_panel := self._closure_panels.get(ClosurePanelRole.POSITION):
            position_state = position_panel.get_attribute_value(
                None, clusters.ClosureDimension.Attributes.CurrentState
            )
            self._attr_current_cover_position = _percent100ths_to_ha_position(
                _extract_struct_field(position_state, 0, "position")
            )
            supported_features |= CoverEntityFeature.SET_POSITION
        if tilt := self._closure_panels.get(ClosurePanelRole.TILT):
            tilt_state = tilt.get_attribute_value(
                None, clusters.ClosureDimension.Attributes.CurrentState
            )
            self._attr_current_cover_tilt_position = _percent100ths_to_ha_position(
                _extract_struct_field(tilt_state, 0, "position")
            )
            supported_features |= CoverEntityFeature.SET_TILT_POSITION
        self._attr_supported_features = supported_features

    def _motion_latching_supported(self) -> bool:
        """Return True if the parent's MotionLatching feature is supported."""
        return _feature_supported(
            self._endpoint,
            clusters.ClosureControl.Attributes.FeatureMap,
            clusters.ClosureControl.Bitmaps.Feature.kMotionLatching,
        )


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.COVER,
        entity_description=MatterCoverEntityDescription(
            key="MatterCover",
            name=None,
        ),
        entity_class=MatterCover,
        required_attributes=(
            clusters.WindowCovering.Attributes.OperationalStatus,
            clusters.WindowCovering.Attributes.Type,
        ),
        absent_attributes=(
            clusters.WindowCovering.Attributes.CurrentPositionLiftPercent100ths,
            clusters.WindowCovering.Attributes.CurrentPositionTiltPercent100ths,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.COVER,
        entity_description=MatterCoverEntityDescription(
            key="MatterCoverPositionAwareLift", name=None
        ),
        entity_class=MatterCover,
        required_attributes=(
            clusters.WindowCovering.Attributes.OperationalStatus,
            clusters.WindowCovering.Attributes.Type,
            clusters.WindowCovering.Attributes.CurrentPositionLiftPercent100ths,
        ),
        absent_attributes=(
            clusters.WindowCovering.Attributes.CurrentPositionTiltPercent100ths,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.COVER,
        entity_description=MatterCoverEntityDescription(
            key="MatterCoverPositionAwareTilt", name=None
        ),
        entity_class=MatterCover,
        required_attributes=(
            clusters.WindowCovering.Attributes.OperationalStatus,
            clusters.WindowCovering.Attributes.Type,
            clusters.WindowCovering.Attributes.CurrentPositionTiltPercent100ths,
        ),
        absent_attributes=(
            clusters.WindowCovering.Attributes.CurrentPositionLiftPercent100ths,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.COVER,
        entity_description=MatterCoverEntityDescription(
            key="MatterCoverPositionAwareLiftAndTilt", name=None
        ),
        entity_class=MatterCover,
        required_attributes=(
            clusters.WindowCovering.Attributes.OperationalStatus,
            clusters.WindowCovering.Attributes.Type,
            clusters.WindowCovering.Attributes.CurrentPositionLiftPercent100ths,
            clusters.WindowCovering.Attributes.CurrentPositionTiltPercent100ths,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.COVER,
        entity_description=MatterCoverEntityDescription(
            key="MatterClosure",
            name=None,
        ),
        entity_class=MatterClosure,
        required_attributes=(clusters.ClosureControl.Attributes.OverallCurrentState,),
        optional_attributes=(
            clusters.ClosureControl.Attributes.MainState,
            clusters.ClosureControl.Attributes.OverallTargetState,
        ),
        allow_none_value=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.COVER,
        entity_description=MatterCoverEntityDescription(
            key="MatterClosureMotionLatching",
            name=None,
        ),
        entity_class=MatterClosure,
        required_attributes=(clusters.ClosureControl.Attributes.OverallCurrentState,),
        optional_attributes=(
            clusters.ClosureControl.Attributes.MainState,
            clusters.ClosureControl.Attributes.OverallTargetState,
        ),
        allow_none_value=True,
        featuremap_contains=clusters.ClosureControl.Bitmaps.Feature.kMotionLatching,
    ),
]
