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

    _attr_translation_key = "push"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the entity."""
        super().__init__(*args, **kwargs)
        # fill the event types based on the features the switch supports
        event_types: list[str] = []
        feature_map = int(
            self.get_matter_attribute_value(clusters.Switch.Attributes.FeatureMap)
        )
        if feature_map & SwitchFeature.kLatchingSwitch:
            event_types.append("switch_latched")
        if feature_map & SwitchFeature.kMomentarySwitch:
            event_types.append("initial_press")
        if feature_map & SwitchFeature.kMomentarySwitchRelease:
            event_types.append("short_release")
        if feature_map & SwitchFeature.kMomentarySwitchLongPress:
            event_types.append("long_press")
            event_types.append("long_release")
        if feature_map & SwitchFeature.kMomentarySwitchMultiPress:
            event_types.append("multi_press_ongoing")
            event_types.append("multi_press_complete")
        self._attr_event_types = event_types
        # the optional label attribute could be used to identify multiple buttons
        # e.g. in case of a dimmer switch with 4 buttons, each button
        # will have its own name, prefixed by the device name.
        if labels := self.get_matter_attribute_value(
            clusters.FixedLabel.Attributes.LabelList
        ):
            for label in labels:
                if label.label == "Label":
                    label_value: str = label.value
                    # in the case the label is only the label id, prettify it a bit
                    if label_value.isnumeric():
                        self._attr_name = f"Button {label_value}"
                    else:
                        self._attr_name = label_value
                    break

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
    def _on_matter_node_event(  # noqa: F821
        self,
        event: EventType,
        data: MatterNodeEvent,
    ) -> None:
        """Call on NodeEvent."""
        if data.endpoint_id != self._endpoint.endpoint_id:
            return
        self._trigger_event(EVENT_TYPES_MAP[data.event_id], data.data)
        self.async_write_ha_state()


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.EVENT,
        entity_description=EventEntityDescription(
            key="GenericSwitch", device_class=EventDeviceClass.BUTTON, name=None
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
    ),
]
