"""Matter event entities from Node events.

This module handles both button-style switches and rotary/linear encoders.
Encoder devices (detected by MultiPressMax > 8) get proper direction and
magnitude events instead of being shoehorned into "multi_press_N" button events.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, override

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types
from matter_server.common.models import EventType, MatterNodeEvent

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MatterEntity, MatterEntityDescription
from .helpers import MatterConfigEntry
from .models import MatterDiscoverySchema

SwitchFeature = clusters.Switch.Bitmaps.Feature

# Devices with MultiPressMax above this threshold are treated as encoders
ENCODER_THRESHOLD = 8


class EncoderType(Enum):
    """Type of encoder - affects wrap-around behavior."""

    ROTARY = "rotary"  # Circular, position wraps (e.g., scroll wheel)
    LINEAR = "linear"  # Has endpoints, no wrap (e.g., slider)
    UNKNOWN = "unknown"  # Will be inferred from behavior


@dataclass
class EncoderConfig:
    """Configuration for a known encoder device."""

    encoder_type: EncoderType
    positions: int | None = None  # None = use device-reported value


# Known encoder devices by (vendor_id, product_id)
# Community can PR additions to this table
# Pattern: similar to VENDOR_LABELING_LIST in entity.py for device-specific quirks
KNOWN_ENCODERS: dict[tuple[int, int], EncoderConfig] = {
    # IKEA BILRESA scroll wheel (E2490)
    # 18-position rotary encoder, wraps around
    (0x117C, 0x8000): EncoderConfig(EncoderType.ROTARY, 18),
    #
    # Add more devices here via PR:
    # (vendor_id, product_id): EncoderConfig(EncoderType.ROTARY_OR_LINEAR, positions),
    #
    # Examples of what might be added:
    # (0xNNNN, 0xNNNN): EncoderConfig(EncoderType.LINEAR, 100),  # Some slider
    # (0xNNNN, 0xNNNN): EncoderConfig(EncoderType.ROTARY, 24),   # 24-position dial
}


EVENT_TYPES_MAP = {
    # mapping from raw event id's to translation keys
    0: "switch_latched",  # clusters.Switch.Events.SwitchLatched
    1: "initial_press",  # clusters.Switch.Events.InitialPress
    2: "long_press",  # clusters.Switch.Events.LongPress
    3: "short_release",  # clusters.Switch.Events.ShortRelease
    4: "long_release",  # clusters.Switch.Events.LongRelease
    5: "multi_press_ongoing",  # clusters.Switch.Events.MultiPressOngoing
    6: "multi_press_complete",  # clusters.Switch.Events.MultiPressComplete
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MatterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter switches from Config Entry."""
    matter = config_entry.runtime_data.adapter
    matter.register_platform_handler(Platform.EVENT, async_add_entities)


@dataclass(frozen=True, kw_only=True)
class MatterEventEntityDescription(EventEntityDescription, MatterEntityDescription):
    """Describe Matter Event entities."""


class MatterEventEntity(MatterEntity, EventEntity):
    """Representation of a Matter Event entity.

    Handles both button-style switches and rotary/linear encoders. Encoders are
    detected by MultiPressMax > ENCODER_THRESHOLD and get proper rotation
    events with direction and magnitude.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the entity."""
        super().__init__(*args, **kwargs)

        feature_map = int(
            self.get_matter_attribute_value(clusters.Switch.Attributes.FeatureMap)
        )

        # Check if this is an encoder device
        self._is_encoder = False
        self._encoder_type = EncoderType.UNKNOWN
        self._last_position: int | None = None
        self._max_positions: int = 2

        # Get device identifiers from endpoint device_info (standard HA Matter pattern)
        vendor_id = self._get_vendor_id()
        product_id = self._get_product_id()

        # Check known devices table first
        known_config = KNOWN_ENCODERS.get((vendor_id, product_id))

        if feature_map & SwitchFeature.kLatchingSwitch:
            self._is_encoder = True
            self._encoder_type = EncoderType.ROTARY
            self._max_positions = self.get_matter_attribute_value(
                clusters.Switch.Attributes.NumberOfPositions
            ) or 18

        elif feature_map & SwitchFeature.kMomentarySwitchMultiPress:
            max_presses = self.get_matter_attribute_value(
                clusters.Switch.Attributes.MultiPressMax
            )
            if max_presses and max_presses > ENCODER_THRESHOLD:
                self._is_encoder = True
                self._max_positions = max_presses

        # Apply known device config if available
        if known_config:
            self._is_encoder = True
            self._encoder_type = known_config.encoder_type
            if known_config.positions:
                self._max_positions = known_config.positions

        # Set up event types based on device type
        event_types: list[str] = []

        if self._is_encoder:
            event_types = ["rotate_cw", "rotate_ccw"]
        elif feature_map & SwitchFeature.kLatchingSwitch:
            event_types.append("switch_latched")
        elif feature_map & SwitchFeature.kMomentarySwitchMultiPress:
            max_presses = self.get_matter_attribute_value(
                clusters.Switch.Attributes.MultiPressMax
            ) or 2
            for i in range(max_presses):
                event_types.append(f"multi_press_{i + 1}")
        elif feature_map & SwitchFeature.kMomentarySwitch:
            event_types.append("initial_press")
            if feature_map & SwitchFeature.kMomentarySwitchRelease:
                event_types.append("short_release")

        if feature_map & SwitchFeature.kMomentarySwitchLongPress:
            event_types.append("long_press")
            event_types.append("long_release")

        self._attr_event_types = event_types

    def _get_vendor_id(self) -> int:
        """Get the vendor ID for this device from endpoint device_info."""
        try:
            return int(self._endpoint.device_info.vendorID or 0)
        except (TypeError, ValueError, AttributeError):
            return 0

    def _get_product_id(self) -> int:
        """Get the product ID for this device from endpoint device_info."""
        try:
            return int(self._endpoint.device_info.productID or 0)
        except (TypeError, ValueError, AttributeError):
            return 0

    @override
    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await super().async_added_to_hass()

        # Initialize last_position from current device state for encoders
        if self._is_encoder:
            current_pos = self.get_matter_attribute_value(
                clusters.Switch.Attributes.CurrentPosition
            )
            if current_pos is not None:
                self._last_position = int(current_pos)

        self._unsubscribes.append(
            self.matter_client.subscribe_events(
                callback=self._on_matter_node_event,
                event_filter=EventType.NODE_EVENT,
                node_filter=self._endpoint.node.node_id,
            )
        )

    @override
    def _update_from_device(self) -> None:
        """Call when Node attribute(s) changed."""
        if self._is_encoder:
            current_pos = self.get_matter_attribute_value(
                clusters.Switch.Attributes.CurrentPosition
            )
            if current_pos is not None:
                self._last_position = int(current_pos)

    @callback
    def _on_matter_node_event(
        self,
        event: EventType,
        data: MatterNodeEvent,
    ) -> None:
        """Call on NodeEvent."""
        if data.endpoint_id != self._endpoint.endpoint_id:
            return

        if self._is_encoder:
            self._handle_encoder_event(data)
        else:
            self._handle_button_event(data)

    def _handle_encoder_event(self, data: MatterNodeEvent) -> None:
        """Handle rotary/linear encoder position events."""
        new_position: int | None = None

        if data.event_id == clusters.Switch.Events.MultiPressComplete.event_id:
            new_position = (data.data or {}).get("totalNumberOfPressesCounted")
        elif data.event_id == clusters.Switch.Events.SwitchLatched.event_id:
            new_position = (data.data or {}).get("newPosition")
        elif data.event_id == clusters.Switch.Events.InitialPress.event_id:
            new_position = (data.data or {}).get("newPosition")

        if new_position is None:
            return

        if self._last_position is None:
            # First event - fire initial position event so users get feedback
            self._trigger_event("rotate_cw", {
                "magnitude": 0,
                "position": new_position,
                "previous_position": None,
                "encoder_type": self._encoder_type.value,
                "initial": True,
            })
            self.async_write_ha_state()
        else:
            # Infer encoder type from delta if still unknown
            raw_delta = new_position - self._last_position
            self._infer_encoder_type_from_delta(raw_delta)

            delta = self._calculate_encoder_delta(self._last_position, new_position)

            if delta != 0:
                direction = "rotate_cw" if delta > 0 else "rotate_ccw"
                magnitude = abs(delta)

                self._trigger_event(direction, {
                    "magnitude": magnitude,
                    "position": new_position,
                    "previous_position": self._last_position,
                    "encoder_type": self._encoder_type.value,
                })
                self.async_write_ha_state()

        self._last_position = new_position

    def _infer_encoder_type_from_delta(self, raw_delta: int) -> None:
        """Infer encoder type from observed delta if type is unknown.

        Large jumps suggest linear encoder (user slid far).
        Small deltas are ambiguous but we don't change inference.
        """
        if self._encoder_type != EncoderType.UNKNOWN:
            return

        half_max = self._max_positions // 2
        if abs(raw_delta) > half_max:
            # Large jump suggests linear encoder (slider moved a lot)
            self._encoder_type = EncoderType.LINEAR

    def _calculate_encoder_delta(self, old_pos: int, new_pos: int) -> int:
        """Calculate position delta, handling wrap-around for rotary encoders.

        For rotary encoders, finds the shortest path (may wrap around).
        For linear encoders, uses direct delta (no wrap).
        For unknown type, assumes rotary behavior (handles wrap correctly).
        """
        raw_delta = new_pos - old_pos
        half_max = self._max_positions // 2

        if self._encoder_type == EncoderType.LINEAR:
            # Linear encoder: no wrap-around, use raw delta
            return raw_delta

        if self._encoder_type == EncoderType.ROTARY:
            # Rotary encoder: find shortest path, may wrap
            if raw_delta > half_max:
                return raw_delta - self._max_positions
            if raw_delta < -half_max:
                return raw_delta + self._max_positions
            return raw_delta

        # Unknown type: assume rotary for now (rotary is more common)
        return raw_delta

    def _handle_button_event(self, data: MatterNodeEvent) -> None:
        """Handle traditional button press events."""
        if data.event_id == clusters.Switch.Events.MultiPressComplete.event_id:
            presses = (data.data or {}).get("totalNumberOfPressesCounted", 1)
            event_type = f"multi_press_{presses}"
        else:
            event_type = EVENT_TYPES_MAP.get(data.event_id)
            if event_type is None:
                return

        if event_type not in self.event_types:
            return

        self._trigger_event(event_type, data.data)
        self.async_write_ha_state()


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.EVENT,
        entity_description=MatterEventEntityDescription(
            key="GenericSwitch",
            device_class=EventDeviceClass.BUTTON,
            translation_key="button",
        ),
        entity_class=MatterEventEntity,
        required_attributes=(
            clusters.Switch.Attributes.CurrentPosition,
            clusters.Switch.Attributes.FeatureMap,
        ),
        device_type=(
            device_types.Doorbell,
            device_types.GenericSwitch,
        ),
        optional_attributes=(
            clusters.Switch.Attributes.NumberOfPositions,
            clusters.Switch.Attributes.MultiPressMax,
            clusters.FixedLabel.Attributes.LabelList,
        ),
        allow_multi=True,
    ),
]
