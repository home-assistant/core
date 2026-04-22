"""Matter event entities from Node events."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, cast

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types
from matter_server.common.models import EventType, MatterNodeEvent

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.components.script import scripts_with_entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN
from .entity import MatterEntity, MatterEntityDescription
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

MULTI_PRESS_COUNT_TO_NAME: dict[int, str] = {
    1: "single",
    2: "double",
    3: "triple",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter event entities from Config Entry."""
    matter = get_matter(hass)

    def async_add_entities_filtered(
        entities: Iterable[Entity],
        update_before_add: bool = False,
    ) -> None:
        async_add_entities(
            (
                entity
                for entity in entities
                if async_check_create_deprecated(
                    hass,
                    Platform.EVENT,
                    entity.unique_id or "",
                    cast(MatterEventEntityDescription, entity.entity_description),
                )
            ),
            update_before_add,
        )

    matter.register_platform_handler(
        Platform.EVENT,
        async_add_entities_filtered,  # type: ignore[arg-type]
    )


@dataclass(slots=True)
class DeprecatedInfo:
    """Class to define deprecation info for deprecated entities."""

    new_platform: Platform
    breaks_in_ha_version: str


@dataclass(frozen=True, kw_only=True)
class MatterEventEntityDescription(EventEntityDescription, MatterEntityDescription):
    """Describe Matter Event entities."""

    deprecated_info: DeprecatedInfo | None = None


def async_check_create_deprecated(
    hass: HomeAssistant,
    platform: Platform,
    unique_id: str,
    entity_description: MatterEventEntityDescription,
) -> bool:
    """Return true if the entity should be created based on the deprecated_info.

    If deprecated_info is not defined will return true.
    If entity not yet created will return false.
    If entity disabled will delete it and return false.
    Otherwise will return true and create issues for scripts or automations.
    """
    if not entity_description.deprecated_info:
        return True

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(
        platform,
        DOMAIN,
        unique_id,
    )
    if not entity_id:
        return False

    entity_entry = ent_reg.async_get(entity_id)
    assert entity_entry
    if entity_entry.disabled:
        ent_reg.async_remove(entity_id)
        return False

    entity_automations = automations_with_entity(hass, entity_id)
    entity_scripts = scripts_with_entity(hass, entity_id)
    deprecated_info = entity_description.deprecated_info
    for item in entity_automations + entity_scripts:
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_entity_{entity_id}_{item}",
            breaks_in_ha_version=deprecated_info.breaks_in_ha_version,
            is_fixable=False,
            is_persistent=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_entity",
            translation_placeholders={
                "entity": entity_id,
                "info": item,
                "platform": str(platform),
                "new_platform": str(deprecated_info.new_platform),
            },
        )
    return True


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
            max_presses_supported = min(max_presses_supported or 2, 8)
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


class MatterMultiPressEventEntity(MatterEventEntity):
    """Representation of a Matter Multi-Press Event entity with press count data."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the entity."""
        super().__init__(*args, **kwargs)
        self._previous_press_count: int = 0
        # Override event types with flat if-chain per Matter spec
        event_types: list[str] = []
        feature_map = int(
            self.get_matter_attribute_value(clusters.Switch.Attributes.FeatureMap)
        )
        # Either momentary xor latching is required
        if feature_map & SwitchFeature.kLatchingSwitch:
            event_types.append("switch_latched")

        if feature_map & SwitchFeature.kMomentarySwitch:
            event_types.append("initial_press")

        # The specs are more strict about what features a device must support
        # We just trust the device. No harm in expecting more events.

        # release is optional, but requires momentary support
        if feature_map & SwitchFeature.kMomentarySwitchRelease:
            event_types.append("short_release")

        # multi press is optional, but requires release support
        if feature_map & SwitchFeature.kMomentarySwitchMultiPress:
            event_types.append("multi_press_ongoing")
            event_types.append("multi_press_complete")

        # long press is optional, but requires release support
        if feature_map & SwitchFeature.kMomentarySwitchLongPress:
            event_types.append("long_press")
            event_types.append("long_release")

        self._attr_event_types = event_types

    @callback
    def _on_matter_node_event(
        self,
        event: EventType,
        data: MatterNodeEvent,
    ) -> None:
        """Call on NodeEvent."""
        if data.endpoint_id != self._endpoint.endpoint_id:
            return
        event_type = EVENT_TYPES_MAP.get(data.event_id)
        if event_type is None:
            return

        if event_type == "initial_press":
            self._previous_press_count = 0

        if event_type == "multi_press_ongoing" and data.data:
            press_count = data.data.get("currentNumberOfPressesCounted", 1)
            data.data["press_count"] = press_count
            data.data["press_step"] = press_count - self._previous_press_count
            self._previous_press_count = press_count

        if event_type == "multi_press_complete" and data.data:
            press_count = data.data.get("totalNumberOfPressesCounted", 1)
            data.data["press_count"] = press_count
            if press_count in MULTI_PRESS_COUNT_TO_NAME:
                data.data["event_type_extra"] = MULTI_PRESS_COUNT_TO_NAME[press_count]
            self._previous_press_count = 0

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
            key="GenericSwitch",
            device_class=EventDeviceClass.BUTTON,
            translation_key="button",
            deprecated_info=DeprecatedInfo(
                new_platform=Platform.EVENT,
                breaks_in_ha_version="2026.11.0",
            ),
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
        allow_multi=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.EVENT,
        entity_description=MatterEventEntityDescription(
            key="MatterMultiPressSwitch",
            device_class=EventDeviceClass.BUTTON,
            translation_key="button",
        ),
        entity_class=MatterMultiPressEventEntity,
        required_attributes=(
            clusters.Switch.Attributes.CurrentPosition,
            clusters.Switch.Attributes.FeatureMap,
        ),
        device_type=(device_types.GenericSwitch,),
        optional_attributes=(
            clusters.Switch.Attributes.NumberOfPositions,
            clusters.FixedLabel.Attributes.LabelList,
        ),
        allow_multi=True,
    ),
]
