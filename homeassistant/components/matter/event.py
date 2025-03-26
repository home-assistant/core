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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter switches from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.EVENT, async_add_entities)


SwitchFeature = clusters.Switch.Bitmaps.Feature

GENERIC_SWITCH_EVENT_TYPES_MAP = {
    # mapping from raw event id's to translation keys
    0: "switch_latched",  # clusters.Switch.Events.SwitchLatched
    1: "initial_press",  # clusters.Switch.Events.InitialPress
    2: "long_press",  # clusters.Switch.Events.LongPress
    3: "short_release",  # clusters.Switch.Events.ShortRelease
    4: "long_release",  # clusters.Switch.Events.LongRelease
    5: "multi_press_ongoing",  # clusters.Switch.Events.MultiPressOngoing
    6: "multi_press_complete",  # clusters.Switch.Events.MultiPressComplete
}


class MatterGenericSwitchEventEntity(MatterEntity, EventEntity):
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
            event_type = GENERIC_SWITCH_EVENT_TYPES_MAP[data.event_id]

        if event_type not in self.event_types:
            # this should not happen, but guard for bad things
            # some remotes send events that they do not report as supported (sigh...)
            return

        # pass the rest of the data as-is (such as the advanced Position data)
        self._trigger_event(event_type, data.data)
        self.async_write_ha_state()


DoorLockFeature = clusters.DoorLock.Bitmaps.Feature
DOOR_LOCK_EVENT_TYPES = {
    # mapping from raw event id's to translation keys
    0: "Alarm: (Any)",  # [M]
    1: "Door State Change: (Any)",  # [DPS]
    2: "Lock Operation: (Any)",  # [M]
    3: "Lock Operation Error: (Any)",  # [M]
    4: "Lock User Change: (Any)",  # [USR]
}

DOOR_LOCK_EVENT_TYPES_EXTENDED_MAP = {
    # mapping from raw event id's to translation keys
    0: {  # DoorLockAlarm (M)
        0: "Alarm: Lock Jammed",  # M
        1: "Alarm: Lock Factory Reset",  # O
        3: "Alarm: Lock Radio Power Cycled",  # O
        4: "Alarm: Wrong Code Entry Limit",  # [USR]
        5: "Alarm: Front Esceutcheon Removed",  # O
        6: "Alarm: Door Forced Open",  # [DPS]
        7: "Alarm: Door Ajar",  # [DPS]
        8: "Alarm: Forced User",  # [USR]
    },
    1: {  # DoorStateChange (DPS)
        0: "Door State: Door Open",  # DPS
        1: "Door State: Door Closed",  # DPS
        2: "Door State: Door Jammed",  # [DPS]
        3: "Door State: Door Forced Open",  # [DPS]
        4: "Door State: Door Unspecified Error",  # [DPS]
        5: "Door State: Door Ajar",  # [DPS]
    },
    2: {  # Lock Operation (M)
        0: "Lock Operation: Lock",  # [M]
        1: "Lock Operation: Unlock",  # [M]
        2: "Lock Operation: Non Access User Event",  # [O]
        3: "Lock Operation: Forced User Event",  # [O]
        4: "Lock Operation: Unlatch",  # [M]
    },
    3: {  # Lock Operation Error (M)
        0: "Lock Operation Error: Lock",  # [M]
        1: "Lock Operation Error: Unlock",  # [M]
        2: "Lock Operation Error: Non Access User Event",  # [O]
        3: "Lock Operation Error: Forced User Event",  # [O]
        4: "Lock Operation Error: Unlatch",  # [M]
    },
    4: {  # Lock User Change (USR)
        0: "Lock User Change: Unspecified",  # [O]
        1: "Lock User Change: Programming Code",  # [O]
        2: "Lock User Change: User Index",  # [M]
        3: "Lock User Change: Week Day Schedule",  # [WDSCH]
        4: "Lock User Change: Year Day Schedule",  # [YDSCH]
        5: "Lock User Change: Holiday Schedule",  # [HDSCH]
        6: "Lock User Change: PIN",  # [PIN]
        7: "Lock User Change: RFID",  # [RID]
        8: "Lock User Change: Fingerprint",  # [FGP]
        9: "Lock User Change: Finger Vein",  # [FGP]
        10: "Lock User Change: Face",  # [FACE]
        11: "Lock User Change: Aliero Crednetial Issuer Key",  # [Aliro]
        12: "Lock User Change: Aliro Evictable Endpoint Key",  # [Aliro]
        13: "Lock User Change: Aliro Non Evictable Endpoint Key",  # [Aliro]
    },
}

DOOR_LOCK_OPERATION_SOURCE = {
    # mapping from raw event id's to translation keys
    0: "Unspecified",  # [O]
    1: "Manual",  # [O]
    2: "Proprietary Remote",  # [O]
    3: "Keypad",  # [O]
    4: "Auto",  # [O]
    5: "Button",  # [O]
    6: "Schedule",  # [HDSCH]
    7: "Remote",  # [M]
    8: "RFID",  # [RID]
    9: "Biometric",  # [USR]
    10: "Aliro",  # [Aliro]
}

DOOR_LOCK_DATA_OPERATION_TYPE = {
    0: "Add",
    1: "Clear",
    2: "Modify",
}


class MatterDoorLockEventEntity(MatterEntity, EventEntity):
    """Representation of a Matter Event entity."""

    DoorLockFeatureFeature = clusters.DoorLock.Bitmaps.Feature

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the entity."""
        super().__init__(*args, **kwargs)
        # fill the event types based on the features the DoorLock supports
        event_types: list[str] = []
        feature_map = int(
            self.get_matter_attribute_value(clusters.DoorLock.Attributes.FeatureMap)
        )
        # DoorLockAlarm
        event_types.append(DOOR_LOCK_EVENT_TYPES[0])
        # Start with the Mandatory and Optional features
        alarm_codes: list[int] = [0, 1, 3, 5]
        # Add others based on feature_map
        if feature_map & DoorLockFeature.kDoorPositionSensor:
            alarm_codes.extend([6, 7])
        if feature_map & DoorLockFeature.kUser:
            alarm_codes.extend([4, 8])
        alarm_codes.sort()
        for alarm_type_key in alarm_codes:
            event_types.append(DOOR_LOCK_EVENT_TYPES_EXTENDED_MAP[0][alarm_type_key])  # noqa: PERF401

        # DoorStateChange
        if feature_map & DoorLockFeature.kDoorPositionSensor:
            event_types.append(DOOR_LOCK_EVENT_TYPES[1])
            event_types.extend(DOOR_LOCK_EVENT_TYPES_EXTENDED_MAP[1].values())

        # LockOperation and LockOperationError
        for door_lock_event_id in (
            2,
            3,
        ):  # LockOperation is ID = 2, LockOperationError is ID = 3
            event_types.append(DOOR_LOCK_EVENT_TYPES[door_lock_event_id])
            for operation_value in DOOR_LOCK_EVENT_TYPES_EXTENDED_MAP[
                door_lock_event_id
            ].values():
                event_types.append(
                    operation_value + ": (Any)"
                )  # Use this event in triggers operation source subtype doesn't matter (Any subtype)

                # Add a third level of events for the particular operation source type from Matter Cluster Spec. 5.2.6.16
                # Start with Mandatory + Optional operation source type from Matter Cluster Spec. 5.2.6.16
                operation_source: list[int] = [0, 1, 2, 3, 4, 5, 7]

                if feature_map & DoorLockFeature.kHolidaySchedules:
                    operation_source.extend([6])
                if feature_map & DoorLockFeature.kRfidCredential:
                    operation_source.extend([8])
                if feature_map & DoorLockFeature.kUser:
                    operation_source.extend([9])
                if feature_map & DoorLockFeature.kAliroProvisioning:
                    operation_source.extend([10])

                operation_source.sort()
                for source_type in operation_source:
                    event_types.append(  # noqa: PERF401
                        f"{operation_value}: {DOOR_LOCK_OPERATION_SOURCE[source_type]}"
                    )

        # LockUserChange
        if feature_map & DoorLockFeature.kUser:
            event_types.append(DOOR_LOCK_EVENT_TYPES[4])
            user_change_types: list[int] = [0, 1, 2]
            if feature_map & DoorLockFeature.kWeekDayAccessSchedules:
                user_change_types.extend([3])
            if feature_map & DoorLockFeature.kYearDayAccessSchedules:
                user_change_types.extend([4])
            if feature_map & DoorLockFeature.kHolidaySchedules:
                user_change_types.extend([5])
            if feature_map & DoorLockFeature.kPinCredential:
                user_change_types.extend([6])
            if feature_map & DoorLockFeature.kRfidCredential:
                user_change_types.extend([7])
            if feature_map & DoorLockFeature.kFingerCredentials:
                user_change_types.extend([8, 9])
            if feature_map & DoorLockFeature.kFaceCredentials:
                user_change_types.extend([10])
            if feature_map & DoorLockFeature.kAliroProvisioning:
                user_change_types.extend([11])

            user_change_types.sort()

            for change_type_key in user_change_types:
                event_types.append(
                    f"{DOOR_LOCK_EVENT_TYPES_EXTENDED_MAP[4][change_type_key]}: (Any)"
                )
                event_types.append(
                    f"{DOOR_LOCK_EVENT_TYPES_EXTENDED_MAP[4][change_type_key]}: Add"
                )
                event_types.append(
                    f"{DOOR_LOCK_EVENT_TYPES_EXTENDED_MAP[4][change_type_key]}: Clear"
                )
                event_types.append(
                    f"{DOOR_LOCK_EVENT_TYPES_EXTENDED_MAP[4][change_type_key]}: Modify"
                )

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
        if (data.endpoint_id != self._endpoint.endpoint_id) or (
            data.cluster_id != clusters.DoorLock.id
        ):
            return

        # Up to 3 HomeAssistant events may be created for each DoorLock Event specified in Section 5.2.11 of the Matter Application Cluster standard.
        # This allows automation triggers with different degrees of specificity

        # Event 1 conveys that a one of the high-level events in the Events table of Section 5.2.11 has occurred.
        # Event 1 is designated as "(Any)" event since triggering on Event 1 will include all further subcategories of the event.
        self._trigger_event(DOOR_LOCK_EVENT_TYPES[data.event_id], data.data)
        self.async_write_ha_state()

        # Additional events (up to 3 total) may be generated as set out below
        match data.event_id:
            case clusters.DoorLock.Events.DoorLockAlarm.event_id:
                # Event 2 is an event that further conveys the Alarm Code information from Matter App. Cluster Spec. 5.2.6.7.
                event_type = DOOR_LOCK_EVENT_TYPES_EXTENDED_MAP[data.event_id][
                    data.data["alarmCode"]
                ]
                self._trigger_event(event_type, data.data)
                self.async_write_ha_state()

            case clusters.DoorLock.Events.DoorStateChange.event_id:
                # Event 2 is an event that further conveys the Alarm Code information from Matter App. Cluster Spec. 5.2.6.11.
                event_type = DOOR_LOCK_EVENT_TYPES_EXTENDED_MAP[data.event_id][
                    data.data["doorState"]
                ]
                self._trigger_event(event_type, data.data)
                self.async_write_ha_state()

            case (
                clusters.DoorLock.Events.LockOperation.event_id
                | clusters.DoorLock.Events.LockOperationError.event_id
            ):  # This case applies to both LockOperation or LockOperationError event types
                event_type = DOOR_LOCK_EVENT_TYPES_EXTENDED_MAP[data.event_id][
                    data.data["lockOperationType"]
                ]

                # Event 2 is an event that conveys the LockOperationType information from Matter App. Cluster Spec. 5.2.6.13.
                # This is designated as "(Any)" event since triggering on this will include all further subcategories
                self._trigger_event(f"{event_type}: (Any)", data.data)
                self.async_write_ha_state()

                # Event 3 is an event that further conveys the operationSource information from Matter App. Cluster Spec. Section 5.2.6.16
                event_type = f"{event_type}: {DOOR_LOCK_OPERATION_SOURCE[data.data['operationSource']]}"
                self._trigger_event(event_type, data.data)
                self.async_write_ha_state()

            case clusters.DoorLock.Events.LockUserChange.event_id:
                event_type = DOOR_LOCK_EVENT_TYPES_EXTENDED_MAP[data.event_id][
                    data.data["lockDataType"]
                ]
                # Event 2 is an event that further conveys the LockDataType information from Matter App. Cluster Spec. 5.2.6.12.
                # This is designated as "(Any)" event since triggering on this will include all further subcategories
                self._trigger_event(f"{event_type}: (Any)", data.data)
                self.async_write_ha_state()

                # Event 3 is an event that further conveys the DataOperationType information from Matter App. Cluster Spec. Section 5.2.6.10
                event_type = f"{event_type}: {DOOR_LOCK_DATA_OPERATION_TYPE[data.data['dataOperationType']]}"
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
        entity_class=MatterGenericSwitchEventEntity,
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
    MatterDiscoverySchema(
        platform=Platform.EVENT,
        entity_description=EventEntityDescription(
            key="DoorLockEvents",
            device_class=EventDeviceClass.BUTTON,
            translation_key="button",
        ),
        entity_class=MatterDoorLockEventEntity,
        required_attributes=(clusters.DoorLock.Attributes.LockState,),
        device_type=(device_types.DoorLock,),
        allow_multi=True,  # also used for sensor (current position) entity
    ),
]
