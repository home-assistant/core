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
    Door,
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
        return UnifiAccessData(
            doors={door.id: door for door in doors},
            emergency=emergency,
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
        if ws_state.dps is not None:
            updates["door_position_status"] = ws_state.dps
        if ws_state.lock == "locked":
            updates["door_lock_relay_status"] = "lock"
        elif ws_state.lock == "unlocked":
            updates["door_lock_relay_status"] = "unlock"
        if not updates:
            return
        updated_door = current_door.with_updates(**updates)
        self.async_set_updated_data(
            UnifiAccessData(
                doors={**self.data.doors, door_id: updated_door},
                emergency=self.data.emergency,
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
        door = insights.data.metadata.door
        if not door.id:
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
        self._dispatch_door_event(door.id, "access", event_type, attrs)

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
