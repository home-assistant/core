"""Matter event entities from Node events."""

from dataclasses import dataclass
from typing import Any, override

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types
from matter_server.common.models import EventType, MatterNodeEvent

from homeassistant.components.event import (
    ATTR_PRESS_COUNT,
    ButtonEventType,
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .entity import MatterEntity, MatterEntityDescription
from .helpers import MatterConfigEntry
from .models import MatterDiscoverySchema, SemanticTag

SwitchFeature = clusters.Switch.Bitmaps.Feature

EVENT_TYPES_MAP = {
    # mapping from raw event IDs to translation keys
    0: "switch_latched",  # clusters.Switch.Events.SwitchLatched
    1: "initial_press",  # clusters.Switch.Events.InitialPress
    2: "long_press",  # clusters.Switch.Events.LongPress
    3: "short_release",  # clusters.Switch.Events.ShortRelease
    4: "long_release",  # clusters.Switch.Events.LongRelease
    5: "multi_press_ongoing",  # clusters.Switch.Events.MultiPressOngoing
    6: "multi_press_complete",  # clusters.Switch.Events.MultiPressComplete
}

SemanticTagNamespace = clusters.Globals.Enums.namespace

# IKEA uses a Switches.Custom semantic tag labeled "rotary" for the Generic
# Switch endpoints that report the rotation of a scroll wheel (one endpoint
# per direction) as multi-press counts. These are no buttons, so they don't get
# the standard button event entity and keep the legacy event entity until
# a dedicated rotary event entity replaces it.
ROTARY_SWITCH_TAG = SemanticTag(
    namespace_id=SemanticTagNamespace.kSwitches,
    tag=0x08,  # Custom
    label="rotary",
)

# Matter-specific event types of the standard button event entity
EVENT_TYPE_INITIAL_PRESS = "initial_press"
EVENT_TYPE_SWITCH_LATCHED = "switch_latched"


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


class MatterEventEntityBase(MatterEntity, EventEntity):
    """Base class for Matter Event entities."""

    @override
    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await super().async_added_to_hass()

        # subscribe to NodeEvent events
        self.async_on_remove(
            self.matter_client.subscribe_events(
                callback=self._on_matter_node_event,
                event_filter=EventType.NODE_EVENT,
                node_filter=self._endpoint.node.node_id,
            )
        )

    @callback
    @override
    def _update_from_device(self) -> None:
        """Call when Node attribute(s) changed."""

    @callback
    def _on_matter_node_event(
        self,
        event: EventType,
        data: MatterNodeEvent,
    ) -> None:
        """Call on NodeEvent."""
        if (
            data.endpoint_id != self._endpoint.endpoint_id
            or data.cluster_id != clusters.Switch.id
        ):
            return
        self._handle_switch_event(data)

    @callback
    def _handle_switch_event(self, data: MatterNodeEvent) -> None:
        """Handle a Switch cluster event."""
        raise NotImplementedError


class MatterButtonEventEntity(MatterEventEntityBase):
    """Matter Event entity using the standard button event types."""

    @override
    @callback
    def _update_from_device(self) -> None:
        """Call when Node attribute(s) changed."""
        # (re)fill the event types based on the features the switch supports,
        # as the feature map can change during the lifetime of the entity
        event_types: list[str] = []
        feature_map = int(
            self.get_matter_attribute_value(clusters.Switch.Attributes.FeatureMap)
        )
        if feature_map & SwitchFeature.kLatchingSwitch:
            # a latching switch only supports the switch_latched event
            event_types.append(EVENT_TYPE_SWITCH_LATCHED)
        elif feature_map & SwitchFeature.kMomentarySwitch:
            action_switch = bool(feature_map & SwitchFeature.kActionSwitch)
            if not action_switch:
                # InitialPress is sent when the button goes down
                event_types.append(ButtonEventType.PRESS_START)
            if feature_map & SwitchFeature.kMomentarySwitchRelease:
                event_types.append(ButtonEventType.PRESS_END)
            if feature_map & SwitchFeature.kMomentarySwitchLongPress:
                event_types.append(ButtonEventType.LONG_PRESS_START)
                event_types.append(ButtonEventType.LONG_PRESS_END)
            if feature_map & SwitchFeature.kMomentarySwitchMultiPress:
                event_types.append(ButtonEventType.SINGLE_PRESS)
                event_types.append(ButtonEventType.MULTI_PRESS)
            if action_switch:
                # an action switch sends InitialPress only once per
                # multi-press sequence, so it is not a press_start
                # and is passed on as a Matter-specific event type
                event_types.append(EVENT_TYPE_INITIAL_PRESS)

        self._attr_event_types = event_types

    @override
    @callback
    def _handle_switch_event(self, data: MatterNodeEvent) -> None:
        """Handle a Switch cluster event."""
        # pass the event data as-is (such as the advanced Position data)
        event_data = dict(data.data or {})
        event_type: str | None
        match data.event_id:
            case clusters.Switch.Events.SwitchLatched.event_id:
                event_type = EVENT_TYPE_SWITCH_LATCHED
            case clusters.Switch.Events.InitialPress.event_id:
                event_type = ButtonEventType.PRESS_START
                if ButtonEventType.PRESS_START not in self.event_types:
                    event_type = EVENT_TYPE_INITIAL_PRESS
            case clusters.Switch.Events.ShortRelease.event_id:
                event_type = ButtonEventType.PRESS_END
            case clusters.Switch.Events.LongPress.event_id:
                event_type = ButtonEventType.LONG_PRESS_START
            case clusters.Switch.Events.LongRelease.event_id:
                event_type = ButtonEventType.LONG_PRESS_END
            case clusters.Switch.Events.MultiPressComplete.event_id:
                presses = event_data.get("totalNumberOfPressesCounted")
                if not isinstance(presses, int) or presses < 1:
                    # a count of 0 means the multi-press sequence was aborted,
                    # e.g. because the number of presses exceeded MultiPressMax;
                    # an event without a count can't be classified
                    return
                if presses == 1:
                    event_type = ButtonEventType.SINGLE_PRESS
                else:
                    event_type = ButtonEventType.MULTI_PRESS
                    event_data[ATTR_PRESS_COUNT] = presses
            case _:
                # MultiPressOngoing is not mapped, the result of
                # a multi-press sequence is reported by MultiPressComplete
                event_type = None

        if event_type is None or event_type not in self.event_types:
            # this should not happen, but guard for bad things
            # some remotes send events that they do not report as supported (sigh...)
            return

        self._trigger_event(event_type, event_data)
        self.async_write_ha_state()


class MatterEventEntity(MatterEventEntityBase):
    """Legacy Matter Event entity, replaced by MatterButtonEventEntity.

    Deprecated and disabled by default in HA 2026.12, remove in 2027.6.
    Rotary endpoints don't get the replacement, so it stays enabled
    there until a dedicated rotary event entity replaces it.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the entity."""
        super().__init__(*args, **kwargs)
        if ROTARY_SWITCH_TAG.on_endpoint(self._endpoint):
            self._attr_translation_key = "button"
            self._attr_entity_registry_enabled_default = True
        # fill the event types based on the features the switch supports
        event_types: list[str] = []
        feature_map = int(
            self.get_matter_attribute_value(clusters.Switch.Attributes.FeatureMap)
        )
        if feature_map & SwitchFeature.kLatchingSwitch:
            # a latching switch only supports switch_latched event
            event_types.append("switch_latched")
        elif feature_map & SwitchFeature.kMomentarySwitchMultiPress:
            # Momentary switch with multi press support
            # NOTE: We ignore 'multi press ongoing' as it doesn't make a lot
            # of sense and many devices do not support it.
            # Instead we report on the 'multi press complete' event with the number
            # of presses.
            max_presses_supported = self.get_matter_attribute_value(
                clusters.Switch.Attributes.MultiPressMax
            )
            max_presses_supported = min(max_presses_supported or 2, 8)
            for i in range(max_presses_supported):
                event_types.append(f"multi_press_{i + 1}")  # noqa: PERF401
        elif feature_map & SwitchFeature.kMomentarySwitch:
            # momentary switch without multi press support
            event_types.append("initial_press")
            if feature_map & SwitchFeature.kMomentarySwitchRelease:
                # momentary switch without multi press support
                # can optionally support release
                event_types.append("short_release")

        # a momentary switch can optionally support long press
        if feature_map & SwitchFeature.kMomentarySwitchLongPress:
            event_types.append("long_press")
            event_types.append("long_release")

        self._attr_event_types = event_types

    @override
    @callback
    def _handle_switch_event(self, data: MatterNodeEvent) -> None:
        """Handle a Switch cluster event."""
        event_type: str | None = EVENT_TYPES_MAP.get(data.event_id)
        if data.event_id == clusters.Switch.Events.MultiPressComplete.event_id:
            # multi press event
            presses = (data.data or {}).get("totalNumberOfPressesCounted", 1)
            event_type = f"multi_press_{presses}"

        if event_type is None:
            LOGGER.debug(
                "Ignoring unknown switch event id %s for %s",
                data.event_id,
                self.entity_id,
            )
            return

        if event_type not in self.event_types:
            # this should not happen, but guard for bad things
            # some remotes send events that they do not report as supported (sigh...)
            return

        # pass the rest of the data as-is (such as the advanced Position data)
        self._trigger_event(event_type, data.data)
        self.async_write_ha_state()


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.EVENT,
        entity_description=MatterEventEntityDescription(
            key="GenericSwitchButton",
            device_class=EventDeviceClass.BUTTON,
            translation_key="button",
        ),
        entity_class=MatterButtonEventEntity,
        required_attributes=(
            clusters.Switch.Attributes.CurrentPosition,
            clusters.Switch.Attributes.FeatureMap,
        ),
        device_type=(device_types.GenericSwitch,),
        absent_semantic_tags=(ROTARY_SWITCH_TAG,),
        optional_attributes=(
            clusters.Switch.Attributes.NumberOfPositions,
            clusters.FixedLabel.Attributes.LabelList,
        ),
        allow_multi=True,  # also used for the legacy event and sensor entity
    ),
    MatterDiscoverySchema(
        platform=Platform.EVENT,
        entity_description=MatterEventEntityDescription(
            key="GenericSwitch",
            device_class=EventDeviceClass.BUTTON,
            translation_key="button_deprecated",
            # Deprecated and disabled by default in HA 2026.12, remove in 2027.6,
            # except on rotary endpoints (see MatterEventEntity)
            entity_registry_enabled_default=False,
        ),
        entity_class=MatterEventEntity,
        required_attributes=(
            clusters.Switch.Attributes.CurrentPosition,
            clusters.Switch.Attributes.FeatureMap,
        ),
        device_type=(device_types.GenericSwitch,),
        optional_attributes=(
            clusters.Switch.Attributes.NumberOfPositions,
            clusters.FixedLabel.Attributes.LabelList,
        ),
        allow_multi=True,  # also used for sensor (current position) entity
    ),
]
