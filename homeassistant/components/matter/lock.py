"""Matter lock."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from chip.clusters import Objects as clusters
from matter_server.common.errors import MatterError
from matter_server.common.models import EventType, MatterNodeEvent

from homeassistant.components.lock import (
    LockEntity,
    LockEntityDescription,
    LockEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CODE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
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
                source_text = DOOR_LOCK_OPERATION_SOURCE.get(
                    operation_source, "Unknown"
                )
                # include user index if available for attribution
                user_index: int | None = node_event_data.get("userIndex")
                if user_index is not None:
                    self._attr_changed_by = f"{source_text} (User {user_index})"
                else:
                    self._attr_changed_by = source_text
                self.async_write_ha_state()

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

    async def async_set_usercode(self, code_slot: int, usercode: str) -> None:
        """Set a usercode on the lock.

        Uses SetCredential which creates the user automatically if needed.
        code_slot maps to credential_index (1-based).
        Passing userIndex=0 tells the lock to auto-assign or create a user.
        """
        result = await self.matter_client.send_device_command(
            node_id=self._endpoint.node.node_id,
            endpoint_id=self._endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.SetCredential(
                operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd,
                credential=clusters.DoorLock.Structs.CredentialStruct(
                    credentialType=clusters.DoorLock.Enums.CredentialTypeEnum.kPin,
                    credentialIndex=code_slot,
                ),
                credentialData=usercode.encode(),
                userIndex=0,  # 0 = let the lock auto-assign a user
                userStatus=clusters.DoorLock.Enums.UserStatusEnum.kOccupiedEnabled,
                userType=clusters.DoorLock.Enums.UserTypeEnum.kUnrestrictedUser,
            ),
            timed_request_timeout_ms=1000,
        )
        if isinstance(result, dict):
            status = result.get("status", -1)
            if status != 0:
                raise HomeAssistantError(
                    f"SetCredential failed with status {status} for slot {code_slot}. "
                    "The lock may not support remote PIN management."
                )
            LOGGER.debug(
                "SetCredential succeeded for slot %s, userIndex=%s",
                code_slot,
                result.get("userIndex"),
            )

    async def async_clear_usercode(self, code_slot: int) -> None:
        """Clear a usercode on the lock."""
        try:
            await self.send_device_command(
                command=clusters.DoorLock.Commands.ClearCredential(
                    credential=clusters.DoorLock.Structs.CredentialStruct(
                        credentialType=clusters.DoorLock.Enums.CredentialTypeEnum.kPin,
                        credentialIndex=code_slot,
                    ),
                ),
                timed_request_timeout_ms=1000,
            )
        except (MatterError, HomeAssistantError) as err:
            LOGGER.warning("ClearCredential failed for slot %s: %s", code_slot, err)

    async def async_get_user(self, user_index: int) -> dict[str, Any]:
        """Get user information from the lock."""
        try:
            result = await self.matter_client.send_device_command(
                node_id=self._endpoint.node.node_id,
                endpoint_id=self._endpoint.endpoint_id,
                command=clusters.DoorLock.Commands.GetUser(
                    userIndex=user_index,
                ),
            )
        except (MatterError, HomeAssistantError) as err:
            LOGGER.warning("GetUser command failed for user %s: %s", user_index, err)
            return {
                "user_index": user_index,
                "exists": False,
                "error": str(err),
            }
        if result is None:
            return {"user_index": user_index, "exists": False}
        return {
            "user_index": user_index,
            "exists": True,
            "user_name": getattr(result, "userName", None),
            "user_unique_id": getattr(result, "userUniqueID", None),
            "user_status": getattr(result, "userStatus", None),
            "user_type": getattr(result, "userType", None),
            "credential_rule": getattr(result, "credentialRule", None),
            "next_user_index": getattr(result, "nextUserIndex", None),
        }

    async def async_get_credential_status(
        self, credential_type: int, credential_index: int
    ) -> dict[str, Any]:
        """Get credential status from the lock."""
        credential = clusters.DoorLock.Structs.CredentialStruct(
            credentialType=credential_type,
            credentialIndex=credential_index,
        )
        result = await self.matter_client.send_device_command(
            node_id=self._endpoint.node.node_id,
            endpoint_id=self._endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.GetCredentialStatus(
                credential=credential,
            ),
        )
        if result is None:
            return {
                "credential_type": credential_type,
                "credential_index": credential_index,
                "exists": False,
            }
        return {
            "credential_type": credential_type,
            "credential_index": credential_index,
            "exists": getattr(result, "credentialExists", False),
            "user_index": getattr(result, "userIndex", None),
            "creator_fabric_index": getattr(result, "creatorFabricIndex", None),
            "last_modified_fabric_index": getattr(
                result, "lastModifiedFabricIndex", None
            ),
            "next_credential_index": getattr(result, "nextCredentialIndex", None),
        }

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
            self._attr_is_jammed = False
        elif lock_state == clusters.DoorLock.Enums.DlLockState.kLocked:
            self._attr_is_locked = True
            self._attr_is_open = False
            self._attr_is_jammed = False
        elif lock_state == clusters.DoorLock.Enums.DlLockState.kUnlocked:
            self._attr_is_locked = False
            self._attr_is_open = False
            self._attr_is_jammed = False
        elif lock_state == clusters.DoorLock.Enums.DlLockState.kNotFullyLocked:
            self._attr_is_locked = False
            self._attr_is_open = False
            self._attr_is_jammed = True
        else:
            # Treat any other state as unknown.
            # NOTE: A null state can happen during device startup.
            self._attr_is_locked = None
            self._attr_is_open = None
            self._attr_is_jammed = None

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


DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.LOCK,
        entity_description=MatterLockEntityDescription(
            key="MatterLock",
            name=None,
        ),
        entity_class=MatterLock,
        required_attributes=(clusters.DoorLock.Attributes.LockState,),
        allow_multi=True,  # also used for door lock event entity
    ),
]
