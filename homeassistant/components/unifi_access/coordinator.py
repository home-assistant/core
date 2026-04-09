"""Data update coordinator for the UniFi Access integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, replace
import logging
from typing import Any, cast

from unifi_access_api import (
    ApiAuthError,
    ApiConnectionError,
    ApiError,
    ApiNotFoundError,
    Door,
    DoorLockRelayStatus,
    DoorLockRule,
    DoorLockRuleStatus,
    DoorLockRuleType,
    EmergencyStatus,
    UnifiAccessApiClient,
    WsMessageHandler,
)
from unifi_access_api.models.websocket import (
    HwDoorbell,
    InsightsAdd,
    LocationUpdateState,
    LocationUpdateV2,
    LogAdd,
    SettingUpdate,
    ThumbnailInfo,
    V2LocationState,
    V2LocationUpdate,
    WebsocketMessage,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DEFAULT_LOCK_RULE_INTERVAL = 10

type UnifiAccessConfigEntry = ConfigEntry[UnifiAccessCoordinator]


@dataclass(frozen=True)
class DoorEvent:
    """Represent a door event from WebSocket."""

    door_id: str
    category: str
    event_type: str
    event_data: dict[str, Any]


@dataclass(frozen=True)
class UnifiAccessData:
    """Data provided by the UniFi Access coordinator."""

    doors: dict[str, Door]
    emergency: EmergencyStatus
    door_lock_rules: dict[str, DoorLockRuleStatus]
    unconfirmed_lock_rule_doors: set[str]
    supports_lock_rules: bool
    lock_rule_support_complete: bool
    door_thumbnails: dict[str, ThumbnailInfo]


class UnifiAccessCoordinator(DataUpdateCoordinator[UnifiAccessData]):
    """Coordinator for fetching UniFi Access door data."""

    config_entry: UnifiAccessConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: UnifiAccessConfigEntry,
        client: UnifiAccessApiClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,
        )
        self.client = client
        self._event_listeners: list[Callable[[DoorEvent], None]] = []
        self._device_to_door: dict[str, str] = {}

    @callback
    def async_subscribe_door_events(
        self,
        event_callback: Callable[[DoorEvent], None],
    ) -> CALLBACK_TYPE:
        """Subscribe to door events (doorbell, access)."""

        def _unsubscribe() -> None:
            self._event_listeners.remove(event_callback)

        self._event_listeners.append(event_callback)
        return _unsubscribe

    async def async_set_lock_rule(self, door_id: str, rule_type: str) -> None:
        """Set a temporary lock rule for a door."""
        if not rule_type:
            return
        lock_rule_type = DoorLockRuleType(rule_type)
        rule = DoorLockRule(type=lock_rule_type, interval=DEFAULT_LOCK_RULE_INTERVAL)
        await self.client.set_door_lock_rule(door_id, rule)
        if self.data is None or door_id not in self.data.doors:
            return
        new_status = DoorLockRuleStatus(
            type=DoorLockRuleType.NONE
            if lock_rule_type == DoorLockRuleType.RESET
            else lock_rule_type
        )
        updated_data = replace(
            self.data,
            door_lock_rules={
                **self.data.door_lock_rules,
                door_id: new_status,
            },
        )
        if self.last_update_success:
            self.async_set_updated_data(updated_data)
        else:
            # Preserve coordinator error state while updating cached data
            self.data = updated_data
            self.async_update_listeners()

    async def _async_setup(self) -> None:
        """Set up the WebSocket connection for push updates."""
        handlers: dict[str, WsMessageHandler] = {
            "access.data.device.location_update_v2": self._handle_location_update,
            "access.data.v2.location.update": self._handle_v2_location_update,
            "access.hw.door_bell": self._handle_doorbell,
            "access.logs.insights.add": self._handle_insights_add,
            "access.logs.add": self._handle_logs_add,
            "access.data.setting.update": self._handle_setting_update,
        }
        self.client.start_websocket(
            handlers,
            on_connect=self._on_ws_connect,
            on_disconnect=self._on_ws_disconnect,
        )

    async def _async_update_data(self) -> UnifiAccessData:
        """Fetch all doors and emergency status from the API."""
        try:
            async with asyncio.timeout(10):
                doors, emergency = await asyncio.gather(
                    self.client.get_doors(),
                    self.client.get_emergency_status(),
                )
        except ApiAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except ApiConnectionError as err:
            raise UpdateFailed(f"Error connecting to API: {err}") from err
        except ApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except TimeoutError as err:
            raise UpdateFailed("Timeout communicating with UniFi Access API") from err

        previous_lock_rules = self.data.door_lock_rules.copy() if self.data else {}
        door_lock_rules: dict[str, DoorLockRuleStatus] = {}
        unconfirmed_lock_rule_doors: set[str] = set()
        lock_rule_support_complete = True
        try:
            async with asyncio.timeout(10):
                lock_rule_results = await asyncio.gather(
                    *(self._async_get_door_lock_rule(door.id) for door in doors),
                    return_exceptions=True,
                )
        except TimeoutError as err:
            lock_rule_results = [err] * len(doors)
        for door, result in zip(doors, lock_rule_results, strict=True):
            if isinstance(result, DoorLockRuleStatus):
                door_lock_rules[door.id] = result
                continue

            if result is None:
                continue

            lock_rule_support_complete = False
            _LOGGER.debug("Could not fetch door lock rule for %s: %s", door.id, result)
            if door.id in previous_lock_rules:
                door_lock_rules[door.id] = previous_lock_rules[door.id]
            else:
                unconfirmed_lock_rule_doors.add(door.id)

        supports_lock_rules = bool(door_lock_rules) or bool(unconfirmed_lock_rule_doors)

        current_ids = {door.id for door in doors} | {self.config_entry.entry_id}
        self._remove_stale_devices(current_ids)

        current_door_ids = {door.id for door in doors}
        self._device_to_door = {
            dev_id: door_id
            for dev_id, door_id in self._device_to_door.items()
            if door_id in current_door_ids
        }

        return UnifiAccessData(
            doors={door.id: door for door in doors},
            emergency=emergency,
            door_lock_rules=door_lock_rules,
            unconfirmed_lock_rule_doors=unconfirmed_lock_rule_doors,
            supports_lock_rules=supports_lock_rules,
            lock_rule_support_complete=lock_rule_support_complete,
            door_thumbnails={
                door.id: ThumbnailInfo(
                    url=door.door_thumbnail,
                    door_thumbnail_last_update=door.door_thumbnail_last_update,
                )
                for door in doors
                if door.door_thumbnail is not None
                and door.door_thumbnail_last_update is not None
            },
        )

    async def _async_get_door_lock_rule(
        self, door_id: str
    ) -> DoorLockRuleStatus | None:
        """Fetch the lock rule for a single door if supported."""
        try:
            return await self.client.get_door_lock_rule(door_id)
        except ApiNotFoundError:
            return None

    @callback
    def _remove_stale_devices(self, current_ids: set[str]) -> None:
        """Remove devices for doors that no longer exist on the hub."""
        device_registry = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        ):
            if any(
                identifier[0] == DOMAIN and identifier[1] in current_ids
                for identifier in device.identifiers
            ):
                continue
            device_registry.async_update_device(
                device_id=device.id,
                remove_config_entry_id=self.config_entry.entry_id,
            )

    def _on_ws_connect(self) -> None:
        """Handle WebSocket connection established."""
        _LOGGER.debug("WebSocket connected to UniFi Access")
        if not self.last_update_success:
            self.config_entry.async_create_background_task(
                self.hass,
                self.async_request_refresh(),
                "unifi_access_reconnect_refresh",
            )

    def _on_ws_disconnect(self) -> None:
        """Handle WebSocket disconnection."""
        self.async_set_update_error(
            UpdateFailed("WebSocket disconnected from UniFi Access")
        )

    async def _handle_location_update(self, msg: WebsocketMessage) -> None:
        """Handle location_update_v2 messages."""
        update = cast(LocationUpdateV2, msg)
        self._process_door_update(
            update.data.id, update.data.state, update.data.thumbnail
        )

    async def _handle_v2_location_update(self, msg: WebsocketMessage) -> None:
        """Handle V2 location update messages."""
        update = cast(V2LocationUpdate, msg)
        door_id = update.data.id

        stale_device_ids = [
            device_id
            for device_id, mapped_door_id in self._device_to_door.items()
            if mapped_door_id == door_id
        ]
        for device_id in stale_device_ids:
            del self._device_to_door[device_id]

        for device_id in update.data.device_ids:
            self._device_to_door[device_id] = door_id

        self._process_door_update(door_id, update.data.state, update.data.thumbnail)

    def _process_door_update(
        self,
        door_id: str,
        ws_state: LocationUpdateState | V2LocationState | None,
        thumbnail: ThumbnailInfo | None = None,
    ) -> None:
        """Process a door state update from WebSocket."""
        if self.data is None or door_id not in self.data.doors:
            return

        if ws_state is None and thumbnail is None:
            return

        current_door = self.data.doors[door_id]
        updates: dict[str, object] = {}
        door_lock_rules = self.data.door_lock_rules
        unconfirmed_lock_rule_doors = self.data.unconfirmed_lock_rule_doors.copy()
        current_lock_rule = door_lock_rules.get(door_id)
        updated_lock_rule = current_lock_rule
        lock_rule_updated = False
        if ws_state is not None:
            if ws_state.dps is not None:
                updates["door_position_status"] = ws_state.dps
            if ws_state.lock == "locked":
                updates["door_lock_relay_status"] = DoorLockRelayStatus.LOCK
            elif ws_state.lock == "unlocked":
                updates["door_lock_relay_status"] = DoorLockRelayStatus.UNLOCK

            if "remain_lock" in ws_state.model_fields_set:
                lock_rule_updated = True
                updated_lock_rule = (
                    ws_state.remain_lock.to_door_lock_rule_status()
                    if ws_state.remain_lock is not None
                    else DoorLockRuleStatus()
                )
            elif "remain_unlock" in ws_state.model_fields_set:
                lock_rule_updated = True
                updated_lock_rule = (
                    ws_state.remain_unlock.to_door_lock_rule_status()
                    if ws_state.remain_unlock is not None
                    else DoorLockRuleStatus()
                )

        if (
            not updates
            and thumbnail is None
            and (not lock_rule_updated or updated_lock_rule == current_lock_rule)
        ):
            return

        updated_door = current_door.with_updates(**updates) if updates else current_door
        new_thumbnails = (
            {**self.data.door_thumbnails, door_id: thumbnail}
            if thumbnail is not None
            else self.data.door_thumbnails
        )
        supports_lock_rules = self.data.supports_lock_rules
        if lock_rule_updated and (
            updated_lock_rule != current_lock_rule
            or door_id in unconfirmed_lock_rule_doors
        ):
            door_lock_rules = {
                **door_lock_rules,
                door_id: updated_lock_rule or DoorLockRuleStatus(),
            }
            unconfirmed_lock_rule_doors.discard(door_id)
            supports_lock_rules = True

        self.async_set_updated_data(
            replace(
                self.data,
                doors={**self.data.doors, door_id: updated_door},
                door_lock_rules=door_lock_rules,
                unconfirmed_lock_rule_doors=unconfirmed_lock_rule_doors,
                supports_lock_rules=supports_lock_rules,
                door_thumbnails=new_thumbnails,
            )
        )

    async def _handle_setting_update(self, msg: WebsocketMessage) -> None:
        """Handle settings update messages (evacuation/lockdown)."""
        if self.data is None:
            return  # type: ignore[unreachable]
        update = cast(SettingUpdate, msg)
        self.async_set_updated_data(
            replace(
                self.data,
                emergency=EmergencyStatus(
                    evacuation=update.data.evacuation,
                    lockdown=update.data.lockdown,
                ),
            )
        )

    async def _handle_doorbell(self, msg: WebsocketMessage) -> None:
        """Handle doorbell press events."""
        doorbell = cast(HwDoorbell, msg)
        self._dispatch_door_event(
            doorbell.data.door_id,
            "doorbell",
            "ring",
            {},
        )

    async def _handle_insights_add(self, msg: WebsocketMessage) -> None:
        """Handle access insights events (entry/exit)."""
        insights = cast(InsightsAdd, msg)
        door_entries = insights.data.metadata.door
        if not door_entries:
            return
        event_type = (
            "access_granted" if insights.data.result == "ACCESS" else "access_denied"
        )
        attrs: dict[str, Any] = {}
        if insights.data.metadata.actor.display_name:
            attrs["actor"] = insights.data.metadata.actor.display_name
        if insights.data.metadata.authentication.display_name:
            attrs["authentication"] = insights.data.metadata.authentication.display_name
        if insights.data.result:
            attrs["result"] = insights.data.result
        for door in door_entries:
            if door.id:
                self._dispatch_door_event(door.id, "access", event_type, attrs)

    async def _handle_logs_add(self, msg: WebsocketMessage) -> None:
        """Handle access log events (entry/exit via access.logs.add)."""
        log = cast(LogAdd, msg)
        source = log.data.source
        device_target = source.device_config
        if device_target is None or device_target.id not in self._device_to_door:
            return
        door_id = self._device_to_door[device_target.id]
        event_type = (
            "access_granted" if source.event.result == "ACCESS" else "access_denied"
        )
        attrs: dict[str, Any] = {}
        if source.actor.display_name:
            attrs["actor"] = source.actor.display_name
        if source.authentication.credential_provider:
            attrs["authentication"] = source.authentication.credential_provider
        if source.event.result:
            attrs["result"] = source.event.result
        self._dispatch_door_event(door_id, "access", event_type, attrs)

    def get_lock_rule_status(self, door_id: str) -> DoorLockRuleStatus | None:
        """Return the current lock rule status for a door."""
        return self.data.door_lock_rules.get(door_id)

    def get_lock_rule_sensor_door_ids(self) -> set[str]:
        """Return doors that should expose lock-rule sensor entities."""
        return self.data.door_lock_rules.keys() | self.data.unconfirmed_lock_rule_doors

    @callback
    def _dispatch_door_event(
        self,
        door_id: str,
        category: str,
        event_type: str,
        event_data: dict[str, Any],
    ) -> None:
        """Dispatch a door event to all subscribed listeners."""
        event = DoorEvent(door_id, category, event_type, event_data)
        for listener in self._event_listeners:
            listener(event)
