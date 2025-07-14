"""Matter lock."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from chip.clusters import Objects as clusters
from matter_server.common.models import EventType, MatterNodeEvent

from homeassistant.components.lock import (
    LockEntity,
    LockEntityDescription,
    LockEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CODE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .entity import MatterEntity, MatterEntityDescription
from .helpers import get_matter
from .models import MatterDiscoverySchema

ATTR_USER_INDEX = "user_index"

DOOR_LOCK_OPERATION_SOURCE = {
    # mapping from operation source id's to textual representation
    0: "Unspecified",
    1: "Manual",  # [Optional]
    2: "Proprietary Remote",  # [Optional]
    3: "Keypad",  # [Optional]
    4: "Auto",  # [Optional]
    5: "Button",  # [Optional]
    6: "Schedule",  # [HDSCH]
    7: "Remote",  # [M]
    8: "RFID",  # [RID]
    9: "Biometric",  # [USR]
    10: "Aliro",  # [Aliro]
}

DoorLockFeature = clusters.DoorLock.Bitmaps.Feature


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter lock from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.LOCK, async_add_entities)


@dataclass(frozen=True)
class MatterLockEntityDescription(LockEntityDescription, MatterEntityDescription):
    """Describe Matter Lock entities."""


class MatterLock(MatterEntity, LockEntity):
    """Representation of a Matter lock."""

    _feature_map: int | None = None
    _platform_translation_key = "lock"
    _attr_user_index: int | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to events to handle jammed and other event conditions"""
        await super().async_added_to_hass()
        # subscribe to NodeEvent events
        self._unsubscribes.append(
            self.matter_client.subscribe_events(
                callback=self._on_matter_node_event,
                event_filter=EventType.NODE_EVENT,
                node_filter=self._endpoint.node.node_id,
            )
        )

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

        LOGGER.debug(
            "Received _on_matter_node_event: event type %s, event id %s for %s with data %s",
            event,
            data.event_id,
            self.entity_id,
            data.data,
        )

        # handle the DoorLock events
        match data.event_id:
            case (
                clusters.DoorLock.Events.DoorLockAlarm.event_id
            ):  # Lock cluster event 0
                match data.data.get("alarmCode"):
                    case 0:  # lock is jammed
                        # set in an uncertain state if jammed
                        self._attr_is_locked = None
                        self._attr_is_open = None
                        self._attr_is_opening = None
                        self._attr_is_locking = None
                        self._attr_is_jammed = True
                        self.async_write_ha_state()
            case clusters.DoorLock.Events.LockOperation.event_id:  # Lock cluster vent 2
                # update the changed_by attribute to indicate lock operation source
                operation_source = data.data.get("operationSource")
                self._attr_changed_by = DOOR_LOCK_OPERATION_SOURCE.get(
                    operation_source, "Unknown"
                )
                # update the user index attribute to indicate which user performed the operation
                self._attr_user_index = data.data.get("userIndex")
                self.async_write_ha_state()
            case (
                clusters.DoorLock.Events.LockOperationError.event_id
            ):  # Lock cluster event 3
                # if an operation error occurs, clear the optimistic state
                self._attr_is_opening = False
                self._attr_is_locking = False
                self.async_write_ha_state()

    @property
    def user_index(self) -> int | None:
        """Return the user index for the lock."""
        return self._attr_user_index

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the additional user_index state attribute of the lock."""
        attrs = super().extra_state_attributes or {}
        attrs[ATTR_USER_INDEX] = self._attr_user_index
        return attrs

    @property
    def code_format(self) -> str | None:
        """Regex for code format or None if no code is required."""
        if self.get_matter_attribute_value(
            clusters.DoorLock.Attributes.RequirePINforRemoteOperation
        ):
            min_pincode_length = int(
                self.get_matter_attribute_value(
                    clusters.DoorLock.Attributes.MinPINCodeLength
                )
            )
            max_pincode_length = int(
                self.get_matter_attribute_value(
                    clusters.DoorLock.Attributes.MaxPINCodeLength
                )
            )
            return f"^\\d{{{min_pincode_length},{max_pincode_length}}}$"

        return None

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock with pin if needed."""
        if not self._attr_is_locked:
            # optimistically signal locking to state machine
            self._attr_is_locking = True
            self._attr_is_unlocking = False
            self._attr_is_opening = False
            self.async_write_ha_state()
        code: str | None = kwargs.get(ATTR_CODE)
        code_bytes = code.encode() if code else None
        result = await self.send_device_command(
            command=clusters.DoorLock.Commands.LockDoor(code_bytes),
            timed_request_timeout_ms=1000,
        )
        LOGGER.debug(
            "Received response from LockDoor command: %s for %s",
            result,
            self.entity_id,
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock. Do not unbolt, even if supported."""
        if self._attr_is_locked:
            # optimistically signal unlocking to state machine
            # the lock should acknowledge the command with an attribute update
            # if lock fails to do so, the jammed or lock operation error event
            # will be raised to clear the optimistic state.
            self._attr_is_locking = False
            self._attr_is_unlocking = True
            self._attr_is_opening = False
            self.async_write_ha_state()
        code: str | None = kwargs.get(ATTR_CODE)
        code_bytes = code.encode() if code else None
        await self.send_device_command(
            command=clusters.DoorLock.Commands.UnlockDoor(code_bytes),
            timed_request_timeout_ms=1000,
        )

    async def async_open(self, **kwargs: Any) -> None:
        """Unlock and pull the door latch."""
        # optimistically signal unlocking and pulling door latch to state machine
        # the lock should acknowledge the command with an attribute update
        # if lock fails to do so, the jammed or lock operation error event
        # will be raised to clear the optimistic state.
        if self._attr_is_locked:
            self._attr_is_locking = False
            self._attr_is_unlocking = True
        if not self._attr_is_open:
            self._attr_is_opening = True
        self.async_write_ha_state()
        code: str | None = kwargs.get(ATTR_CODE)
        code_bytes = code.encode() if code else None
        if self._attr_supported_features & LockEntityFeature.OPEN:
            # async_open should only be called if the lock reports it has unbolt support,
            # however, guard against a mistaken call to async_open and call UnLockDoor if it does not have unbolt support.
            await self.send_device_command(
                command=clusters.DoorLock.Commands.UnboltDoor(code_bytes),
                timed_request_timeout_ms=1000,
            )
        else:
            await self.send_device_command(
                command=clusters.DoorLock.Commands.UnlockDoor(code_bytes),
                timed_request_timeout_ms=1000,
            )

    @callback
    def _update_from_device(self) -> None:
        """Update the entity from the device."""
        # always calculate the features as they can dynamically change
        self._calculate_features()

        lock_state = self.get_matter_attribute_value(
            clusters.DoorLock.Attributes.LockState
        )

        LOGGER.debug(
            "Received _update_from_device with lock state: %s for %s",
            lock_state,
            self.entity_id,
        )
        # start by setting all the lock operation attributes as False, then change as needed
        self._attr_is_locked = False
        self._attr_is_locking = False
        self._attr_is_unlocking = False
        self._attr_is_open = False
        self._attr_is_opening = False
        self._attr_is_jammed = False
        if lock_state == clusters.DoorLock.Enums.DlLockState.kNotFullyLocked:
            # State 0 - lock is an uncertain lock state, treat as jammed
            self._attr_is_jammed = True
        elif lock_state == clusters.DoorLock.Enums.DlLockState.kLocked:
            # State 1 - fully locked, latch/bolt not pulled
            self._attr_is_locked = True
        elif lock_state == clusters.DoorLock.Enums.DlLockState.kUnlocked:  # state 2
            # State 2 - unlocked, latch/bolt is not pulled, False states are correct here
            pass
        elif lock_state == clusters.DoorLock.Enums.DlLockState.kUnlatched:
            # State 3 - lock is unlocked and latch/bolt is pulled
            self._attr_is_open = True
        else:
            # NOTE: A null state can happen during device startup. Treat as unknown.
            self._attr_is_locked = None
            self._attr_is_locking = None
            self._attr_is_unlocking = None
            self._attr_is_open = None
            self._attr_is_opening = None
            self._attr_is_jammed = None
            self._attr_changed_by = None
            self._attr_user_index = None

    @callback
    def _calculate_features(
        self,
    ) -> None:
        """Calculate features for HA Lock platform from Matter FeatureMap."""
        feature_map = int(
            self.get_matter_attribute_value(clusters.DoorLock.Attributes.FeatureMap)
        )
        # NOTE: the featuremap can dynamically change, so we need to update the
        # supported features if the featuremap changes.
        if self._feature_map == feature_map:
            return
        self._feature_map = feature_map
        supported_features = LockEntityFeature(0)
        # determine if lock supports optional open/unbolt feature
        if bool(feature_map & DoorLockFeature.kUnbolt):
            supported_features |= LockEntityFeature.OPEN
        self._attr_supported_features = supported_features


DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.LOCK,
        entity_description=MatterLockEntityDescription(
            key="MatterLock",
            name=None,
        ),
        entity_class=MatterLock,
        required_attributes=(clusters.DoorLock.Attributes.LockState,),
    ),
]
