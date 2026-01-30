"""Matter lock."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from chip.clusters import Objects as clusters
from matter_server.common.models import EventType, MatterNodeEvent
import voluptuous as vol

from homeassistant.components.lock import (
    LockEntity,
    LockEntityDescription,
    LockEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CODE, ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_CODE_SLOT,
    ATTR_CREDENTIAL_RULE,
    ATTR_MAX_CREDENTIALS_PER_USER,
    ATTR_MAX_PIN_USERS,
    ATTR_MAX_RFID_USERS,
    ATTR_MAX_USERS,
    ATTR_PIN_CODE,
    ATTR_SUPPORTS_USER_MGMT,
    ATTR_USER_INDEX,
    ATTR_USER_NAME,
    ATTR_USER_TYPE,
    ATTR_USERCODE,
    CLEAR_ALL_INDEX,
    CREDENTIAL_RULE_REVERSE_MAP,
    DOOR_LOCK_OPERATION_SOURCE,
    DOOR_LOCK_OPERATION_TYPE,
    EVENT_LOCK_DISPOSABLE_USER_DELETED,
    EVENT_LOCK_OPERATION,
    LOCK_TIMED_REQUEST_TIMEOUT_MS,
    LOGGER,
    SERVICE_CLEAR_LOCK_USER,
    SERVICE_CLEAR_LOCK_USERCODE,
    SERVICE_GET_LOCK_INFO,
    SERVICE_GET_LOCK_USERS,
    SERVICE_SET_LOCK_USER,
    SERVICE_SET_LOCK_USERCODE,
    USER_TYPE_REVERSE_MAP,
)
from .entity import MatterEntity, MatterEntityDescription
from .helpers import get_matter
from .helpers_lock import (
    DoorLockFeature,
    LockEndpointNotFoundError,
    UserSlotEmptyError,
    UsrFeatureNotSupportedError,
    clear_lock_user,
    clear_user_credentials,
    find_available_credential_slot,
    get_lock_endpoint_from_node,
    get_lock_info,
    get_lock_users,
    lock_supports_usr_feature,
    set_credential_for_user,
    set_lock_user,
    validate_pin_code,
)
from .models import MatterDiscoverySchema


def _get_attr(obj: Any, attr: str) -> Any:
    """Get attribute from object or dict."""
    if isinstance(obj, dict):
        return obj.get(attr)
    return getattr(obj, attr, None)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter lock from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.LOCK, async_add_entities)

    platform = entity_platform.async_get_current_platform()

    # Simple PIN operations (Z-Wave JS equivalents)
    platform.async_register_entity_service(
        SERVICE_SET_LOCK_USERCODE,
        {
            vol.Required(ATTR_CODE_SLOT): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Required(ATTR_USERCODE): cv.string,
        },
        "async_set_lock_usercode",
    )
    platform.async_register_entity_service(
        SERVICE_CLEAR_LOCK_USERCODE,
        {
            vol.Required(ATTR_CODE_SLOT): vol.All(vol.Coerce(int), vol.Range(min=1)),
        },
        "async_clear_lock_usercode",
    )

    # Full user CRUD
    platform.async_register_entity_service(
        SERVICE_SET_LOCK_USER,
        {
            vol.Optional(ATTR_USER_INDEX): vol.Any(
                vol.All(vol.Coerce(int), vol.Range(min=1)), None
            ),
            vol.Optional(ATTR_USER_NAME): vol.Any(str, None),
            vol.Optional(ATTR_USER_TYPE, default="unrestricted_user"): vol.In(
                USER_TYPE_REVERSE_MAP.keys()
            ),
            vol.Optional(ATTR_CREDENTIAL_RULE, default="single"): vol.In(
                CREDENTIAL_RULE_REVERSE_MAP.keys()
            ),
            vol.Optional(ATTR_PIN_CODE): vol.Any(str, None),
        },
        "async_set_lock_user",
    )
    platform.async_register_entity_service(
        SERVICE_CLEAR_LOCK_USER,
        {
            vol.Required(ATTR_USER_INDEX): vol.All(
                vol.Coerce(int),
                vol.Any(vol.Range(min=1), CLEAR_ALL_INDEX),
            ),
        },
        "async_clear_lock_user",
    )

    # Query operations (SupportsResponse)
    platform.async_register_entity_service(
        SERVICE_GET_LOCK_INFO,
        {},
        "async_get_lock_info",
        supports_response=SupportsResponse.ONLY,
    )
    platform.async_register_entity_service(
        SERVICE_GET_LOCK_USERS,
        {},
        "async_get_lock_users",
        supports_response=SupportsResponse.ONLY,
    )


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
            ATTR_ENTITY_ID: self.entity_id,
            "operation": operation_name,
            "source": source_name,
            ATTR_USER_INDEX: user_index,
            ATTR_USER_NAME: user_name,
        }
        self.hass.bus.async_fire(EVENT_LOCK_OPERATION, event_data)
        LOGGER.debug("Fired %s event: %s", EVENT_LOCK_OPERATION, event_data)

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
                timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
            )
            LOGGER.info(
                "Deleted disposable user '%s' at index %s after one-time use for %s",
                user_name or "unknown",
                user_index,
                self.entity_id,
            )
            self.hass.bus.async_fire(
                EVENT_LOCK_DISPOSABLE_USER_DELETED,
                {
                    ATTR_ENTITY_ID: self.entity_id,
                    ATTR_USER_INDEX: user_index,
                    ATTR_USER_NAME: user_name,
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
            timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
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
                timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
            )
        else:
            await self.send_device_command(
                command=clusters.DoorLock.Commands.UnlockDoor(code_bytes),
                timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
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
            timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
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
            ATTR_SUPPORTS_USER_MGMT: supports_usr,
        }

        # Only include capacity info if USR feature is supported
        if supports_usr:
            attrs[ATTR_MAX_USERS] = self.get_matter_attribute_value(
                clusters.DoorLock.Attributes.NumberOfTotalUsersSupported
            )
            attrs[ATTR_MAX_PIN_USERS] = self.get_matter_attribute_value(
                clusters.DoorLock.Attributes.NumberOfPINUsersSupported
            )
            attrs[ATTR_MAX_RFID_USERS] = self.get_matter_attribute_value(
                clusters.DoorLock.Attributes.NumberOfRFIDUsersSupported
            )
            attrs[ATTR_MAX_CREDENTIALS_PER_USER] = self.get_matter_attribute_value(
                clusters.DoorLock.Attributes.NumberOfCredentialsSupportedPerUser
            )

        return attrs

    # --- Entity service methods ---

    async def async_set_lock_usercode(self, code_slot: int, usercode: str) -> None:
        """Set a user code on the lock (simplified PIN interface).

        Creates user if needed, sets PIN in one call.
        """
        node = self._endpoint.node
        lock_endpoint = get_lock_endpoint_from_node(node)
        if lock_endpoint is None:
            raise LockEndpointNotFoundError("No lock endpoint found on this device")

        if not lock_supports_usr_feature(lock_endpoint):
            raise UsrFeatureNotSupportedError(
                "Lock does not support user/credential management"
            )

        # Validate PIN
        min_pin = (
            lock_endpoint.get_attribute_value(
                None, clusters.DoorLock.Attributes.MinPINCodeLength
            )
            or 0
        )
        max_pin = (
            lock_endpoint.get_attribute_value(
                None, clusters.DoorLock.Attributes.MaxPINCodeLength
            )
            or 0
        )
        pin_error = validate_pin_code(usercode, min_pin, max_pin)
        if pin_error is not None:
            raise HomeAssistantError(f"PIN code must be {min_pin}-{max_pin} digits")

        # Check if user exists at code_slot
        get_user_response = await self.matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.GetUser(userIndex=code_slot),
        )

        if _get_attr(get_user_response, "userStatus") is None:
            # Create user at this slot
            await self.matter_client.send_device_command(
                node_id=node.node_id,
                endpoint_id=lock_endpoint.endpoint_id,
                command=clusters.DoorLock.Commands.SetUser(
                    operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd,
                    userIndex=code_slot,
                    userName=None,
                    userUniqueID=None,
                    userStatus=clusters.DoorLock.Enums.UserStatusEnum.kOccupiedEnabled,
                    userType=0,  # unrestricted_user
                    credentialRule=0,  # single
                ),
                timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
            )

        # Set PIN credential
        pin_cred_type = clusters.DoorLock.Enums.CredentialTypeEnum.kPin

        # Check if user already has a PIN credential
        check_response = await self.matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.GetUser(userIndex=code_slot),
        )
        existing_cred_index = None
        creds = _get_attr(check_response, "credentials")
        if creds:
            for cred in creds:
                if _get_attr(cred, "credentialType") == pin_cred_type:
                    existing_cred_index = _get_attr(cred, "credentialIndex")
                    break

        if existing_cred_index is not None:
            await set_credential_for_user(
                self.matter_client,
                node.node_id,
                lock_endpoint.endpoint_id,
                code_slot,
                pin_cred_type,
                usercode.encode(),
                credential_index=existing_cred_index,
                operation=clusters.DoorLock.Enums.DataOperationTypeEnum.kModify,
            )
        else:
            max_pin_slots = (
                lock_endpoint.get_attribute_value(
                    None, clusters.DoorLock.Attributes.NumberOfPINUsersSupported
                )
                or 0
            )
            slot = await find_available_credential_slot(
                self.matter_client,
                node.node_id,
                lock_endpoint.endpoint_id,
                pin_cred_type,
                max_pin_slots,
            )
            if slot is None:
                raise HomeAssistantError("No available credential slots on the lock")

            result = await set_credential_for_user(
                self.matter_client,
                node.node_id,
                lock_endpoint.endpoint_id,
                code_slot,
                pin_cred_type,
                usercode.encode(),
                credential_index=slot,
                operation=clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd,
            )
            if result["status"] != "success":
                raise HomeAssistantError(
                    f"Failed to set credential: {result['status']}"
                )

    async def async_clear_lock_usercode(self, code_slot: int) -> None:
        """Clear user and all credentials at a slot."""
        node = self._endpoint.node
        lock_endpoint = get_lock_endpoint_from_node(node)
        if lock_endpoint is None:
            raise LockEndpointNotFoundError("No lock endpoint found on this device")

        if not lock_supports_usr_feature(lock_endpoint):
            raise UsrFeatureNotSupportedError(
                "Lock does not support user/credential management"
            )

        # Check if user exists
        get_user_response = await self.matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.GetUser(userIndex=code_slot),
        )

        if _get_attr(get_user_response, "userStatus") is None:
            raise UserSlotEmptyError(f"User slot {code_slot} is empty")

        # Clear all credentials for this user
        await clear_user_credentials(
            self.matter_client,
            node.node_id,
            lock_endpoint.endpoint_id,
            code_slot,
        )

        # Clear the user
        await self.matter_client.send_device_command(
            node_id=node.node_id,
            endpoint_id=lock_endpoint.endpoint_id,
            command=clusters.DoorLock.Commands.ClearUser(userIndex=code_slot),
            timed_request_timeout_ms=LOCK_TIMED_REQUEST_TIMEOUT_MS,
        )

    async def async_set_lock_user(self, **kwargs: Any) -> None:
        """Set a lock user (full CRUD)."""
        await set_lock_user(
            self.matter_client,
            self._endpoint.node,
            user_index=kwargs.get(ATTR_USER_INDEX),
            user_name=kwargs.get(ATTR_USER_NAME),
            user_type=kwargs.get(ATTR_USER_TYPE, "unrestricted_user"),
            credential_rule=kwargs.get(ATTR_CREDENTIAL_RULE, "single"),
            pin_code=kwargs.get(ATTR_PIN_CODE),
            pin_code_present=ATTR_PIN_CODE in kwargs,
        )

    async def async_clear_lock_user(self, **kwargs: Any) -> None:
        """Clear a lock user."""
        await clear_lock_user(
            self.matter_client,
            self._endpoint.node,
            kwargs[ATTR_USER_INDEX],
        )

    async def async_get_lock_info(self) -> dict[str, Any]:
        """Get lock capabilities and configuration info."""
        return await get_lock_info(
            self.matter_client,
            self._endpoint.node,
        )

    async def async_get_lock_users(self) -> dict[str, Any]:
        """Get all users from the lock."""
        return await get_lock_users(
            self.matter_client,
            self._endpoint.node,
        )


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
