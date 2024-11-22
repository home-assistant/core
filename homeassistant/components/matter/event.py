"""Matter event entities from Node events."""

from __future__ import annotations

from typing import Any

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types
from matter_server.common.models import EventType, MatterNodeEvent

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema

SwitchFeature = clusters.Switch.Bitmaps.Feature

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
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter switches from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.EVENT, async_add_entities)


class MatterEventEntity(MatterEntity, EventEntity):
    """Representation of a Matter Event entity."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the entity."""
        super().__init__(*args, **kwargs)
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
            max_presses_supported = min(max_presses_supported or 1, 8)
            for i in range(max_presses_supported):
                event_types.append(f"multi_press_{i + 1}")  # noqa: PERF401
        elif feature_map & SwitchFeature.kMomentarySwitch:
            # momentary switch without multi press support
            event_types.append("initial_press")
            if feature_map & SwitchFeature.kMomentarySwitchRelease:
                # momentary switch without multi press support can optionally support release
                event_types.append("short_release")

        # a momentary switch can optionally support long press
        if feature_map & SwitchFeature.kMomentarySwitchLongPress:
            event_types.append("long_press")
            event_types.append("long_release")

        self._attr_event_types = event_types

    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await super().async_added_to_hass()

        # subscribe to NodeEvent events
        self._unsubscribes.append(
            self.matter_client.subscribe_events(
                callback=self._on_matter_node_event,
                event_filter=EventType.NODE_EVENT,
                node_filter=self._endpoint.node.node_id,
            )
        )

    def _update_from_device(self) -> None:
        """Call when Node attribute(s) changed."""

    @callback
    def _on_matter_node_event(
        self,
        event: EventType,
        data: MatterNodeEvent,
    ) -> None:
        """Call on NodeEvent."""
        if data.endpoint_id != self._endpoint.endpoint_id:
            return
        if data.event_id == clusters.Switch.Events.MultiPressComplete.event_id:
            # multi press event
            presses = (data.data or {}).get("totalNumberOfPressesCounted", 1)
            event_type = f"multi_press_{presses}"
        else:
            event_type = EVENT_TYPES_MAP[data.event_id]

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
        entity_description=EventEntityDescription(
            key="GenericSwitch",
            device_class=EventDeviceClass.BUTTON,
            translation_key="button",
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
