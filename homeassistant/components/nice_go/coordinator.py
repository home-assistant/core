"""DataUpdateCoordinator for Nice G.O."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import json
import logging
from typing import TYPE_CHECKING, Any

from nice_go import (
    BARRIER_STATUS,
    ApiError,
    AuthFailedError,
    BarrierState,
    ConnectionState,
    NiceGOApi,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_CREATION_TIME,
    DOMAIN,
    REFRESH_TOKEN_EXPIRY_TIME,
)

_LOGGER = logging.getLogger(__name__)

RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY = 5


@dataclass
class NiceGODevice:
    """Nice G.O. device dataclass."""

    type: str
    id: str
    name: str
    barrier_status: str
    light_status: bool | None
    fw_version: str
    connected: bool
    vacation_mode: bool | None


type NiceGOConfigEntry = ConfigEntry[NiceGOUpdateCoordinator]


class NiceGOUpdateCoordinator(DataUpdateCoordinator[dict[str, NiceGODevice]]):
    """DataUpdateCoordinator for Nice G.O."""

    config_entry: NiceGOConfigEntry
    organization_id: str

    def __init__(self, hass: HomeAssistant, config_entry: NiceGOConfigEntry) -> None:
        """Initialize DataUpdateCoordinator for Nice G.O."""
        super().__init__(hass, _LOGGER, config_entry=config_entry, name="Nice G.O.")

        self.refresh_token = self.config_entry.data[CONF_REFRESH_TOKEN]
        self.refresh_token_creation_time = self.config_entry.data[
            CONF_REFRESH_TOKEN_CREATION_TIME
        ]
        self.email = self.config_entry.data[CONF_EMAIL]
        self.password = self.config_entry.data[CONF_PASSWORD]
        self.api = NiceGOApi()
        self._unsub_connected: Callable[[], None] | None = None
        self._unsub_data: Callable[[], None] | None = None
        self._unsub_connection_lost: Callable[[], None] | None = None
        self.connected = False
        self._hass_stopping: bool = hass.is_stopping

    @callback
    def async_ha_stop(self, event: Event) -> None:
        """Stop reconnecting if hass is stopping."""
        self._hass_stopping = True

    async def _parse_barrier(
        self, device_type: str, barrier_state: BarrierState
    ) -> NiceGODevice | None:
        """Parse barrier data."""

        device_id = barrier_state.deviceId
        name = barrier_state.reported["displayName"]
        if barrier_state.reported["migrationStatus"] == "NOT_STARTED":
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"firmware_update_required_{device_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="firmware_update_required",
                translation_placeholders={"device_name": name},
            )
            return None
        ir.async_delete_issue(
            self.hass, DOMAIN, f"firmware_update_required_{device_id}"
        )
        barrier_status_raw = [
            int(x) for x in barrier_state.reported["barrierStatus"].split(",")
        ]

        if BARRIER_STATUS[int(barrier_status_raw[2])] == "STATIONARY":
            barrier_status = "open" if barrier_status_raw[0] == 1 else "closed"
        else:
            barrier_status = BARRIER_STATUS[int(barrier_status_raw[2])].lower()

        light_status = (
            barrier_state.reported["lightStatus"].split(",")[0] == "1"
            if barrier_state.reported.get("lightStatus")
            else None
        )
        fw_version = barrier_state.reported["deviceFwVersion"]
        if barrier_state.connectionState:
            connected = barrier_state.connectionState.connected
        elif device_type == "Mms100":
            connected = barrier_state.reported.get("radioConnected", 0) == 1
        else:
            # Assume connected
            connected = True
        vacation_mode = barrier_state.reported.get("vcnMode", None)

        return NiceGODevice(
            type=device_type,
            id=device_id,
            name=name,
            barrier_status=barrier_status,
            light_status=light_status,
            fw_version=fw_version,
            connected=connected,
            vacation_mode=vacation_mode,
        )

    async def _async_update_data(self) -> dict[str, NiceGODevice]:
        return self.data

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        async with asyncio.timeout(10):
            expiry_time = (
                self.refresh_token_creation_time
                + REFRESH_TOKEN_EXPIRY_TIME.total_seconds()
            )
            try:
                if datetime.now().timestamp() >= expiry_time:
                    await self.update_refresh_token()
                else:
                    await self.api.authenticate_refresh(
                        self.refresh_token, async_get_clientsession(self.hass)
                    )
                _LOGGER.debug("Authenticated with Nice G.O. API")

                barriers = await self.api.get_all_barriers()
                parsed_barriers = [
                    await self._parse_barrier(barrier.type, barrier.state)
                    for barrier in barriers
                ]

                # Parse the barriers and save them in a dictionary
                devices = {
                    barrier.id: barrier for barrier in parsed_barriers if barrier
                }
                self.organization_id = await barriers[0].get_attr("organization")
            except AuthFailedError as e:
                raise ConfigEntryAuthFailed from e
            except ApiError as e:
                raise UpdateFailed from e
            else:
                self.async_set_updated_data(devices)

    async def update_refresh_token(self) -> None:
        """Update the refresh token with Nice G.O. API."""
        _LOGGER.debug("Updating the refresh token with Nice G.O. API")
        try:
            refresh_token = await self.api.authenticate(
                self.email, self.password, async_get_clientsession(self.hass)
            )
        except AuthFailedError as e:
            _LOGGER.exception("Authentication failed")
            raise ConfigEntryAuthFailed from e
        except ApiError as e:
            _LOGGER.exception("API error")
            raise UpdateFailed from e

        self.refresh_token = refresh_token
        data = {
            **self.config_entry.data,
            CONF_REFRESH_TOKEN: refresh_token,
            CONF_REFRESH_TOKEN_CREATION_TIME: datetime.now().timestamp(),
        }
        self.hass.config_entries.async_update_entry(self.config_entry, data=data)

    async def client_listen(self) -> None:
        """Listen to the websocket for updates."""
        self._unsub_connected = self.api.listen("on_connected", self.on_connected)
        self._unsub_data = self.api.listen("on_data", self.on_data)
        self._unsub_connection_lost = self.api.listen(
            "on_connection_lost", self.on_connection_lost
        )

        for _ in range(RECONNECT_ATTEMPTS):
            if self._hass_stopping:
                return

            try:
                await self.api.connect(reconnect=True)
            except ApiError:
                _LOGGER.exception("API error")
            else:
                return

            await asyncio.sleep(RECONNECT_DELAY)

        self.async_set_update_error(
            TimeoutError(
                "Failed to connect to the websocket, reconnect attempts exhausted"
            )
        )

    async def on_data(self, data: dict[str, Any]) -> None:
        """Handle incoming data from the websocket."""
        _LOGGER.debug("Received data from the websocket")
        _LOGGER.debug(data)
        raw_data = data["data"]["devicesStatesUpdateFeed"]["item"]
        parsed_data = await self._parse_barrier(
            self.data[
                raw_data["deviceId"]
            ].type,  # Device type is not sent in device state update, and it can't change, so we just reuse the existing one
            BarrierState(
                deviceId=raw_data["deviceId"],
                reported=json.loads(raw_data["reported"]),
                connectionState=ConnectionState(
                    connected=raw_data["connectionState"]["connected"],
                    updatedTimestamp=raw_data["connectionState"]["updatedTimestamp"],
                )
                if raw_data["connectionState"]
                else None,
                version=raw_data["version"],
                timestamp=raw_data["timestamp"],
            ),
        )
        if parsed_data is None:
            return

        data_copy = self.data.copy()
        data_copy[parsed_data.id] = parsed_data

        self.async_set_updated_data(data_copy)

    async def on_connected(self) -> None:
        """Handle the websocket connection."""
        _LOGGER.debug("Connected to the websocket")
        self.connected = True

        await self.api.subscribe(self.organization_id)

        if not self.last_update_success:
            self.async_set_updated_data(self.data)

    async def on_connection_lost(self, data: dict[str, Exception]) -> None:
        """Handle the websocket connection loss. Don't need to do much since the library will automatically reconnect."""
        _LOGGER.debug("Connection lost to the websocket")
        self.connected = False

        # Give some time for reconnection
        await asyncio.sleep(RECONNECT_DELAY)
        if self.connected:
            _LOGGER.debug("Reconnected, not setting error")
            return

        # There's likely a problem with the connection, and not the server being flaky
        self.async_set_update_error(data["exception"])

    def unsubscribe(self) -> None:
        """Unsubscribe from the websocket."""
        if TYPE_CHECKING:
            assert self._unsub_connected is not None
            assert self._unsub_data is not None
            assert self._unsub_connection_lost is not None

        self._unsub_connection_lost()
        self._unsub_connected()
        self._unsub_data()
        self._unsub_connected = None
        self._unsub_data = None
        self._unsub_connection_lost = None
        _LOGGER.debug("Unsubscribed from the websocket")
