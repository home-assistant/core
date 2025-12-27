"""Matter lock."""

from __future__ import annotations

import asyncio
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

DOOR_LOCK_OPERATION_TYPE = {
    # mapping from lock operation type id's to textual representation
    0: "lock",
    1: "unlock",
    2: "non_access_user_event",
    3: "forced_user_event",
    4: "unlatch",
}


def _get_attr(obj: Any, attr: str) -> Any:
    """Get attribute from object or dict."""
    if isinstance(obj, dict):
        return obj.get(attr)
    return getattr(obj, attr, None)


DoorLockFeature = clusters.DoorLock.Bitmaps.Feature


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter lock from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.LOCK, async_add_entities)


@dataclass(frozen=True, kw_only=True)
class MatterLockEntityDescription(LockEntityDescription, MatterEntityDescription):
    """Describe Matter Lock entities."""


class MatterLock(MatterEntity, LockEntity):
    """Representation of a Matter lock."""

    _feature_map: int | None = None
    _optimistic_timer: asyncio.TimerHandle | None = None
    _platform_translation_key = "lock"
    _attr_changed_by = "Unknown"

    async def async_added_to_hass(self) -> None:
        """Subscribe to events."""
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
        node_event: MatterNodeEvent,
    ) -> None:
        """Call on NodeEvent."""
        if (node_event.endpoint_id != self._endpoint.endpoint_id) or (
            node_event.cluster_id != clusters.DoorLock.id
        ):
            return

        LOGGER.debug(
            "Received node_event: event type %s, event id %s for %s with data %s",
            event,
            node_event.event_id,
            self.entity_id,
            node_event.data,
        )

        # handle the DoorLock events
        node_event_data: dict[str, int] = node_event.data or {}
        match node_event.event_id:
            case (
                clusters.DoorLock.Events.LockOperation.event_id
            ):  # Lock cluster event 2
                # update the changed_by attribute to indicate lock operation source
                operation_source: int = node_event_data.get("operationSource", -1)
                operation_type: int = node_event_data.get("lockOperationType", -1)
                user_index = node_event_data.get("userIndex")

                # Fire event and handle user lookup asynchronously
                self.hass.async_create_task(
                    self._handle_lock_operation(
                        operation_source, operation_type, user_index
                    )
                )

    async def _handle_lock_operation(
        self, operation_source: int, operation_type: int, user_index: int | None
    ) -> None:
        """Handle lock operation event - look up user and fire event."""
        source_name = DOOR_LOCK_OPERATION_SOURCE.get(operation_source, "Unknown")
        operation_name = DOOR_LOCK_OPERATION_TYPE.get(operation_type, "unknown")
        user_name: str | None = None

        # Look up user name if we have a user index
        if user_index is not None:
            try:
                get_user_response = await self.matter_client.send_device_command(
                    node_id=self._endpoint.node.node_id,
                    endpoint_id=self._endpoint.endpoint_id,
                    command=clusters.DoorLock.Commands.GetUser(userIndex=user_index),
                )
                user_name = _get_attr(get_user_response, "userName")
                user_type = _get_attr(get_user_response, "userType")
                user_status = _get_attr(get_user_response, "userStatus")

                # Clean up disposable users after use
                # UserType 6 = disposable_user, UserStatus 3 = occupied_disabled
                if user_type == 6 and user_status == 3:
                    await self._cleanup_disposable_user(user_index, user_name)
            except Exception:  # noqa: BLE001
                LOGGER.debug(
                    "Failed to get user info for index %s on %s",
                    user_index,
                    self.entity_id,
                    exc_info=True,
                )

        # Update changed_by with user name if available, otherwise source
        if user_name:
            self._attr_changed_by = f"{user_name} ({source_name})"
        else:
            self._attr_changed_by = source_name
        self.async_write_ha_state()

        # Fire event with all details
        event_data = {
            "entity_id": self.entity_id,
            "operation": operation_name,
            "source": source_name,
            "user_index": user_index,
            "user_name": user_name,
        }
        self.hass.bus.async_fire("matter_lock_operation", event_data)
        LOGGER.debug("Fired matter_lock_operation event: %s", event_data)

    async def _cleanup_disposable_user(
        self, user_index: int, user_name: str | None = None
    ) -> None:
        """Clean up a disposable user after use.

        Disposable users (one-time codes) should be deleted after use.
        Some locks disable them (status=3) instead of deleting them,
        so we clean them up automatically.
        """
        try:
            LOGGER.debug(
                "Cleaning up disabled disposable user '%s' at index %s for %s",
                user_name or "unknown",
                user_index,
                self.entity_id,
            )
            await self.matter_client.send_device_command(
                node_id=self._endpoint.node.node_id,
                endpoint_id=self._endpoint.endpoint_id,
                command=clusters.DoorLock.Commands.ClearUser(userIndex=user_index),
                timed_request_timeout_ms=1000,
            )
            LOGGER.info(
                "Deleted disposable user '%s' at index %s after one-time use for %s",
                user_name or "unknown",
                user_index,
                self.entity_id,
            )
            # Fire an event so automations can react to disposable user cleanup
            self.hass.bus.async_fire(
                "matter_lock_disposable_user_deleted",
                {
                    "entity_id": self.entity_id,
                    "user_index": user_index,
                    "user_name": user_name,
                },
            )
        except Exception:  # noqa: BLE001
            LOGGER.debug(
                "Failed to cleanup disposable user at index %s for %s",
                user_index,
                self.entity_id,
                exc_info=True,
            )

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
            # but bad things may happen, so guard against it with a timer.
            self._optimistic_timer = self.hass.loop.call_later(
                30, self._reset_optimistic_state
            )
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
            # but bad things may happen, so guard against it with a timer.
            self._optimistic_timer = self.hass.loop.call_later(
                30, self._reset_optimistic_state
            )
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
        self._attr_is_opening = True
        self.async_write_ha_state()
        # the lock should acknowledge the command with an attribute update
        # but bad things may happen, so guard against it with a timer.
        self._optimistic_timer = self.hass.loop.call_later(
            30 if self._attr_is_locked else 5, self._reset_optimistic_state
        )
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

        # always reset the optimisically (un)locking state on state update
        self._reset_optimistic_state(write_state=False)

        LOGGER.debug("Lock state: %s for %s", lock_state, self.entity_id)

        if lock_state == clusters.DoorLock.Enums.DlLockState.kUnlatched:
            self._attr_is_locked = False
            self._attr_is_open = True
        elif lock_state == clusters.DoorLock.Enums.DlLockState.kLocked:
            self._attr_is_locked = True
            self._attr_is_open = False
        elif lock_state in (
            clusters.DoorLock.Enums.DlLockState.kUnlocked,
            clusters.DoorLock.Enums.DlLockState.kNotFullyLocked,
        ):
            self._attr_is_locked = False
            self._attr_is_open = False
        else:
            # Treat any other state as unknown.
            # NOTE: A null state can happen during device startup.
            self._attr_is_locked = None
            self._attr_is_open = None

    @callback
    def _reset_optimistic_state(self, write_state: bool = True) -> None:
        if self._optimistic_timer and not self._optimistic_timer.cancelled():
            self._optimistic_timer.cancel()
        self._optimistic_timer = None
        self._attr_is_locking = False
        self._attr_is_unlocking = False
        self._attr_is_opening = False
        if write_state:
            self.async_write_ha_state()

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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes for lock capabilities."""
        supports_usr = bool((self._feature_map or 0) & DoorLockFeature.kUser)

        attrs: dict[str, Any] = {
            "supports_user_management": supports_usr,
        }

        # Only include capacity info if USR feature is supported
        if supports_usr:
            attrs["max_users"] = self.get_matter_attribute_value(
                clusters.DoorLock.Attributes.NumberOfTotalUsersSupported
            )
            attrs["max_pin_users"] = self.get_matter_attribute_value(
                clusters.DoorLock.Attributes.NumberOfPINUsersSupported
            )
            attrs["max_rfid_users"] = self.get_matter_attribute_value(
                clusters.DoorLock.Attributes.NumberOfRFIDUsersSupported
            )
            attrs["max_credentials_per_user"] = self.get_matter_attribute_value(
                clusters.DoorLock.Attributes.NumberOfCredentialsSupportedPerUser
            )

        return attrs


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
