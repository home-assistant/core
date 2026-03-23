"""Data update coordinator for the UniFi Access integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, cast

from unifi_access_api import (
    ApiAuthError,
    ApiConnectionError,
    ApiError,
    ApiNotFoundError,
    Door,
    DoorLockRuleStatus,
    EmergencyStatus,
    UnifiAccessApiClient,
    WsMessageHandler,
)
from unifi_access_api.models.websocket import (
    HwDoorbell,
    InsightsAdd,
    LocationUpdateState,
    LocationUpdateV2,
    SettingUpdate,
    V2LocationState,
    V2LocationUpdate,
    WebsocketMessage,
    WsDoorLockRuleStatus,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

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
    supports_lock_rules: bool
    lock_rule_support_complete: bool


def _ws_rule_status_to_lock_rule_status(
    ws_rule_status: WsDoorLockRuleStatus,
) -> DoorLockRuleStatus:
    """Convert websocket lock rule data to the API status model."""
    return DoorLockRuleStatus(
        type=ws_rule_status.type,
        ended_time=ws_rule_status.until,
    )


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

    async def _async_setup(self) -> None:
        """Set up the WebSocket connection for push updates."""
        handlers: dict[str, WsMessageHandler] = {
            "access.data.device.location_update_v2": self._handle_location_update,
            "access.data.v2.location.update": self._handle_v2_location_update,
            "access.hw.door_bell": self._handle_doorbell,
            "access.logs.insights.add": self._handle_insights_add,
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

        supports_lock_rules = bool(door_lock_rules) or not lock_rule_support_complete

        return UnifiAccessData(
            doors={door.id: door for door in doors},
            emergency=emergency,
            door_lock_rules=door_lock_rules,
            supports_lock_rules=supports_lock_rules,
            lock_rule_support_complete=lock_rule_support_complete,
        )

    async def _async_get_door_lock_rule(
        self, door_id: str
    ) -> DoorLockRuleStatus | None:
        """Fetch the lock rule for a single door if supported."""
        try:
            return await self.client.get_door_lock_rule(door_id)
        except ApiNotFoundError:
            return None

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
        _LOGGER.warning("WebSocket disconnected from UniFi Access")
        self.async_set_update_error(
            UpdateFailed("WebSocket disconnected from UniFi Access")
        )

    async def _handle_location_update(self, msg: WebsocketMessage) -> None:
        """Handle location_update_v2 messages."""
        update = cast(LocationUpdateV2, msg)
        self._process_door_update(update.data.id, update.data.state)

    async def _handle_v2_location_update(self, msg: WebsocketMessage) -> None:
        """Handle V2 location update messages."""
        update = cast(V2LocationUpdate, msg)
        self._process_door_update(update.data.id, update.data.state)

    def _process_door_update(
        self, door_id: str, ws_state: LocationUpdateState | V2LocationState | None
    ) -> None:
        """Process a door state update from WebSocket."""
        if self.data is None or door_id not in self.data.doors:
            return

        if ws_state is None:
            return

        current_door = self.data.doors[door_id]
        updates: dict[str, object] = {}
        door_lock_rules = self.data.door_lock_rules
        current_lock_rule = door_lock_rules.get(door_id)
        updated_lock_rule = current_lock_rule
        if ws_state.dps is not None:
            updates["door_position_status"] = ws_state.dps
        if ws_state.lock == "locked":
            updates["door_lock_relay_status"] = "lock"
        elif ws_state.lock == "unlocked":
            updates["door_lock_relay_status"] = "unlock"

        lock_rule_updated = False
        if "remain_lock" in ws_state.model_fields_set:
            lock_rule_updated = True
            updated_lock_rule = (
                _ws_rule_status_to_lock_rule_status(ws_state.remain_lock)
                if ws_state.remain_lock is not None
                else DoorLockRuleStatus()
            )
        elif "remain_unlock" in ws_state.model_fields_set:
            lock_rule_updated = True
            updated_lock_rule = (
                _ws_rule_status_to_lock_rule_status(ws_state.remain_unlock)
                if ws_state.remain_unlock is not None
                else DoorLockRuleStatus()
            )

        if not updates and (
            not lock_rule_updated or updated_lock_rule == current_lock_rule
        ):
            return

        updated_door = current_door.with_updates(**updates) if updates else current_door
        supports_lock_rules = self.data.supports_lock_rules
        if lock_rule_updated and updated_lock_rule != current_lock_rule:
            door_lock_rules = {
                **door_lock_rules,
                door_id: updated_lock_rule or DoorLockRuleStatus(),
            }
            supports_lock_rules = True

        self.async_set_updated_data(
            UnifiAccessData(
                doors={**self.data.doors, door_id: updated_door},
                emergency=self.data.emergency,
                door_lock_rules=door_lock_rules,
                supports_lock_rules=supports_lock_rules,
                lock_rule_support_complete=self.data.lock_rule_support_complete,
            )
        )

    async def _handle_setting_update(self, msg: WebsocketMessage) -> None:
        """Handle settings update messages (evacuation/lockdown)."""
        if self.data is None:
            return
        update = cast(SettingUpdate, msg)
        self.async_set_updated_data(
            UnifiAccessData(
                doors=self.data.doors,
                emergency=EmergencyStatus(
                    evacuation=update.data.evacuation,
                    lockdown=update.data.lockdown,
                ),
                door_lock_rules=self.data.door_lock_rules,
                supports_lock_rules=self.data.supports_lock_rules,
                lock_rule_support_complete=self.data.lock_rule_support_complete,
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
        if not isinstance(door_entries, list):
            door_entries = [door_entries]
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

    def get_lock_rule_status(self, door_id: str) -> DoorLockRuleStatus | None:
        """Return the current lock rule status for a door."""
        return self.data.door_lock_rules.get(door_id)

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
