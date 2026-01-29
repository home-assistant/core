"""Matter lock event entities from Node events."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from chip.clusters import Objects as clusters
from matter_server.common.models import EventType, MatterNodeEvent

from homeassistant.components.event import EventEntity
from homeassistant.core import callback

from .entity import MatterEntity

# DoorLock alarm codes (DoorLockAlarm event)
DOOR_LOCK_ALARM_MAP = {
    0: "lock_jammed",
    1: "lock_factory_reset",
    2: "lock_radio_power_cycled",
    3: "wrong_code_entry_limit",
    4: "front_escutcheon_removed",
    5: "door_forced_open",
    6: "door_ajar",
    7: "forced_user",
}

# DoorLock door state (DoorStateChange event)
DOOR_STATE_MAP = {
    0: "door_open",
    1: "door_closed",
    2: "door_jammed",
    3: "door_forced_open",
    4: "door_unspecified_error",
    5: "door_ajar",
}

# DoorLock operation types (LockOperation/LockOperationError events)
LOCK_OPERATION_TYPE_MAP = {
    0: "lock",
    1: "unlock",
    2: "non_access_user_event",
    3: "forced_user_event",
    4: "unlatch",
}

# DoorLock operation source
LOCK_OPERATION_SOURCE_MAP = {
    0: "unspecified",
    1: "manual",
    2: "proprietary_remote",
    3: "keypad",
    4: "auto",
    5: "button",
    6: "schedule",
    7: "remote",
    8: "rfid",
    9: "biometric",
    10: "aliro",
}

# DoorLock operation error codes (LockOperationError event)
LOCK_OPERATION_ERROR_MAP = {
    0: "unspecified",
    1: "invalid_credential",
    2: "disabled_user_denied",
    3: "restricted",
    4: "insufficient_battery",
}

# DoorLock data type for user change (LockUserChange event)
LOCK_DATA_TYPE_MAP = {
    0: "unspecified",
    1: "programming_pin",
    2: "user_index",
    3: "week_day_schedule",
    4: "year_day_schedule",
    5: "holiday_schedule",
    6: "pin",
    7: "rfid",
    8: "fingerprint",
    9: "finger_vein",
    10: "face",
    11: "aliro_credential_issuer_key",
    12: "aliro_evictable_endpoint_key",
    13: "aliro_non_evictable_endpoint_key",
}

# DoorLock data operation type for user change
LOCK_DATA_OPERATION_MAP = {
    0: "add",
    1: "clear",
    2: "modify",
}


class MatterLockEventEntityBase(MatterEntity, EventEntity):
    """Base class for Matter Lock Event entities.

    This base class reduces code duplication by handling common
    event subscription and filtering logic.
    """

    # Subclasses must define which event IDs they handle
    _handled_event_ids: set[int] = set()

    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await super().async_added_to_hass()

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
        if data.cluster_id != clusters.DoorLock.id:
            return
        if data.event_id not in self._handled_event_ids:
            return

        self._handle_lock_event(data)

    @abstractmethod
    def _handle_lock_event(self, data: MatterNodeEvent) -> None:
        """Handle a lock-specific event. Must be implemented by subclasses."""


class MatterLockAlarmEventEntity(MatterLockEventEntityBase):
    """Representation of a Matter Lock Alarm Event entity."""

    _attr_event_types = list(DOOR_LOCK_ALARM_MAP.values())
    _handled_event_ids = {clusters.DoorLock.Events.DoorLockAlarm.event_id}

    def _handle_lock_event(self, data: MatterNodeEvent) -> None:
        """Handle a DoorLockAlarm event."""
        event_data = data.data or {}
        alarm_code = event_data.get("alarmCode", 0)
        event_type = DOOR_LOCK_ALARM_MAP.get(alarm_code, "unknown")

        self._trigger_event(event_type, event_data)
        self.async_write_ha_state()


class MatterLockOperationEventEntity(MatterLockEventEntityBase):
    """Representation of a Matter Lock Operation Event entity."""

    # Event types for lock operations and errors
    _attr_event_types = [
        "locked",
        "unlocked",
        "unlatched",
        "lock_failed",
        "unlock_failed",
        "unlatch_failed",
    ]
    _handled_event_ids = {
        clusters.DoorLock.Events.LockOperation.event_id,
        clusters.DoorLock.Events.LockOperationError.event_id,
    }

    def _handle_lock_event(self, data: MatterNodeEvent) -> None:
        """Handle a LockOperation or LockOperationError event."""
        event_data = data.data or {}

        if data.event_id == clusters.DoorLock.Events.LockOperation.event_id:
            self._handle_lock_operation(event_data)
        elif data.event_id == clusters.DoorLock.Events.LockOperationError.event_id:
            self._handle_lock_operation_error(event_data)

    def _handle_lock_operation(self, event_data: dict[str, Any]) -> None:
        """Handle a successful lock operation event."""
        lock_op_type = event_data.get("lockOperationType", 0)
        if lock_op_type == 0:  # Lock
            event_type = "locked"
        elif lock_op_type == 1:  # Unlock
            event_type = "unlocked"
        elif lock_op_type == 4:  # Unlatch
            event_type = "unlatched"
        else:
            return  # Ignore other operation types

        # Add human-readable fields to event data
        enriched_data = {
            "operation_type": LOCK_OPERATION_TYPE_MAP.get(lock_op_type, "unknown"),
            "source": LOCK_OPERATION_SOURCE_MAP.get(
                event_data.get("operationSource", 0), "unknown"
            ),
            "user_index": event_data.get("userIndex"),
        }
        self._trigger_event(event_type, enriched_data)
        self.async_write_ha_state()

    def _handle_lock_operation_error(self, event_data: dict[str, Any]) -> None:
        """Handle a failed lock operation event."""
        lock_op_type = event_data.get("lockOperationType", 0)
        if lock_op_type == 0:  # Lock
            event_type = "lock_failed"
        elif lock_op_type == 1:  # Unlock
            event_type = "unlock_failed"
        elif lock_op_type == 4:  # Unlatch
            event_type = "unlatch_failed"
        else:
            return  # Ignore other operation types

        # Add human-readable fields to event data
        enriched_data = {
            "operation_type": LOCK_OPERATION_TYPE_MAP.get(lock_op_type, "unknown"),
            "source": LOCK_OPERATION_SOURCE_MAP.get(
                event_data.get("operationSource", 0), "unknown"
            ),
            "error": LOCK_OPERATION_ERROR_MAP.get(
                event_data.get("operationError", 0), "unknown"
            ),
            "user_index": event_data.get("userIndex"),
        }
        self._trigger_event(event_type, enriched_data)
        self.async_write_ha_state()


class MatterDoorStateEventEntity(MatterLockEventEntityBase):
    """Representation of a Matter Door State Change Event entity."""

    _attr_event_types = list(DOOR_STATE_MAP.values())
    _handled_event_ids = {clusters.DoorLock.Events.DoorStateChange.event_id}

    def _handle_lock_event(self, data: MatterNodeEvent) -> None:
        """Handle a DoorStateChange event."""
        event_data = data.data or {}
        door_state = event_data.get("doorState", 0)
        event_type = DOOR_STATE_MAP.get(door_state, "unknown")

        self._trigger_event(event_type, event_data)
        self.async_write_ha_state()


class MatterLockUserChangeEventEntity(MatterLockEventEntityBase):
    """Representation of a Matter Lock User Change Event entity."""

    _attr_event_types = [
        "user_added",
        "user_cleared",
        "user_modified",
        "credential_added",
        "credential_cleared",
        "credential_modified",
    ]
    _handled_event_ids = {clusters.DoorLock.Events.LockUserChange.event_id}

    def _handle_lock_event(self, data: MatterNodeEvent) -> None:
        """Handle a LockUserChange event."""
        event_data = data.data or {}
        lock_data_type = event_data.get("lockDataType", 0)
        data_operation = event_data.get("dataOperationType", 0)

        # Determine if this is a user or credential change
        is_user_change = lock_data_type == 2  # UserIndex type

        # Map operation to event type
        if is_user_change:
            if data_operation == 0:
                event_type = "user_added"
            elif data_operation == 1:
                event_type = "user_cleared"
            else:
                event_type = "user_modified"
        elif data_operation == 0:
            event_type = "credential_added"
        elif data_operation == 1:
            event_type = "credential_cleared"
        else:
            event_type = "credential_modified"

        # Add human-readable fields to event data
        enriched_data = {
            "data_type": LOCK_DATA_TYPE_MAP.get(lock_data_type, "unknown"),
            "operation": LOCK_DATA_OPERATION_MAP.get(data_operation, "unknown"),
            "source": LOCK_OPERATION_SOURCE_MAP.get(
                event_data.get("operationSource", 0), "unknown"
            ),
            "user_index": event_data.get("userIndex"),
            "data_index": event_data.get("dataIndex"),
        }
        self._trigger_event(event_type, enriched_data)
        self.async_write_ha_state()
