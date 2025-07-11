"""Matter lock."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from propcache.api import cached_property

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
            "Received _on_matter_node_event: event %s for %s with data %s",
            data.event_id,
            self.entity_id,
            data.data,
        )

        match data.event_id:
            case clusters.DoorLock.Events.DoorLockAlarm.event_id:  # Event 0
                match data.data.get("alarmCode"):
                    case 0:  # lock is jammed
                        # don't reset the optimisically (un)locking state on state update
                        self._attr_is_jammed = True
                        self.async_write_ha_state()
            case clusters.DoorLock.Events.LockOperation.event_id:  # Event 2
                # update the changed_by attribute with the translated value
                operation_source = data.data.get("operationSource")
                self._attr_changed_by = DOOR_LOCK_OPERATION_SOURCE.get(
                    operation_source, "Unknown"
                )
                self._attr_user_index = data.data.get("userIndex")
                self.async_write_ha_state()
            case clusters.DoorLock.Events.LockOperationError.event_id:  # Event 3
                match data.data.get("lockOperationError"):
                    case 0 | 1:  # Lock or Unlock Error
                        self._attr_is_jammed = True
                        self.async_write_ha_state()

    @property
    def user_index(self) -> int | None:
        """Return the user index for the lock."""
        return self._attr_user_index

    @property
    def extra_state_attributes(self):
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
            self.async_write_ha_state()
            # the lock should acknowledge the command with an attribute update
            # if lock fails to do so, the jammed event will be raised.
        code: str | None = kwargs.get(ATTR_CODE)
        code_bytes = code.encode() if code else None
        await self.send_device_command(
            command=clusters.DoorLock.Commands.LockDoor(code_bytes),
            timed_request_timeout_ms=1000,
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock with pin if needed."""
        if self._attr_is_locked:
            # optimistically signal unlocking to state machine
            self._attr_is_unlocking = True
            self.async_write_ha_state()
            # the lock should acknowledge the command with an attribute update
            # if lock fails to do so, the jammed event will be raised
        code: str | None = kwargs.get(ATTR_CODE)
        code_bytes = code.encode() if code else None
        if self._attr_supported_features & LockEntityFeature.OPEN:
            # if the lock reports it has separate unbolt support,
            # the unlock command should unbolt only on the unlock command
            # and unlatch on the HA 'open' command.
            await self.send_device_command(
                command=clusters.DoorLock.Commands.UnboltDoor(code_bytes),
                timed_request_timeout_ms=1000,
            )
        else:
            await self.send_device_command(
                command=clusters.DoorLock.Commands.UnlockDoor(code_bytes),
                timed_request_timeout_ms=1000,
            )

    async def async_open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        # optimistically signal opening to state machine
        # if lock fails to do so, the jammed event will be raised
        self._attr_is_opening = True
        self.async_write_ha_state()
        code: str | None = kwargs.get(ATTR_CODE)
        code_bytes = code.encode() if code else None
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

        LOGGER.debug("Lock state: %s for %s", lock_state, self.entity_id)

        if lock_state == clusters.DoorLock.Enums.DlLockState.kUnlatched:
            # unlocked and unlatched
            self._attr_is_locked = False
            self._attr_is_open = True
            self._attr_is_jammed = False
        elif lock_state == clusters.DoorLock.Enums.DlLockState.kLocked:
            # locked and latched.
            self._attr_is_locked = True  # lock is open, but latch is closed
            self._attr_is_open = False
            self._attr_is_jammed = False
        elif lock_state == clusters.DoorLock.Enums.DlLockState.kUnlocked:
            # unlocked but latched
            self._attr_is_locked = False
            self._attr_is_open = False
            self._attr_is_jammed = False
        elif lock_state == clusters.DoorLock.Enums.DlLockState.kNotFullyLocked:
            # uncertain lock state, treat as jammed
            self._attr_is_locked = False
            self._attr_is_open = False
            self._attr_is_jammed = True
        else:
            # Treat any other state as unknown.
            # NOTE: A null state can happen during device startup.
            self._attr_is_locked = None
            self._attr_is_open = None
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
