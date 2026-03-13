"""Data update coordinator for the UniFi Access integration."""

from __future__ import annotations

import asyncio
import logging
from typing import cast

from unifi_access_api import (
    ApiAuthError,
    ApiConnectionError,
    ApiError,
    Door,
    UnifiAccessApiClient,
    WsMessageHandler,
)
from unifi_access_api.models.websocket import (
    LocationUpdateState,
    LocationUpdateV2,
    V2LocationState,
    V2LocationUpdate,
    WebsocketMessage,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type UnifiAccessConfigEntry = ConfigEntry[UnifiAccessCoordinator]


class UnifiAccessCoordinator(DataUpdateCoordinator[dict[str, Door]]):
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

    async def _async_setup(self) -> None:
        """Set up the WebSocket connection for push updates."""
        handlers: dict[str, WsMessageHandler] = {
            "access.data.device.location_update_v2": self._handle_location_update,
            "access.data.v2.location.update": self._handle_v2_location_update,
        }
        self.client.start_websocket(
            handlers,
            on_connect=self._on_ws_connect,
            on_disconnect=self._on_ws_disconnect,
        )

    async def _async_update_data(self) -> dict[str, Door]:
        """Fetch all doors from the API."""
        try:
            async with asyncio.timeout(10):
                doors = await self.client.get_doors()
        except ApiAuthError as err:
            raise ConfigEntryAuthFailed from err
        except ApiConnectionError as err:
            raise UpdateFailed(f"Error connecting to API: {err}") from err
        except ApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        return {door.id: door for door in doors}

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
        _LOGGER.debug("WebSocket disconnected from UniFi Access")
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
        if self.data is None or door_id not in self.data:
            return

        if ws_state is None:
            return

        current_door = self.data[door_id]
        updates: dict[str, object] = {"door_position_status": ws_state.dps}
        if ws_state.lock == "locked":
            updates["door_lock_relay_status"] = "lock"
        elif ws_state.lock == "unlocked":
            updates["door_lock_relay_status"] = "unlock"
        updated_door = current_door.with_updates(**updates)
        self.async_set_updated_data({**self.data, door_id: updated_door})
