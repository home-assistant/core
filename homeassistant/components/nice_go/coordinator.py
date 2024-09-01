"""DataUpdateCoordinator for Nice G.O."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import json
import logging
from typing import Any

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
from homeassistant.core import HomeAssistant
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


@dataclass
class NiceGODevice:
    """Nice G.O. device dataclass."""

    id: str
    name: str
    barrier_status: str
    light_status: bool
    fw_version: str
    connected: bool
    vacation_mode: bool


class NiceGOUpdateCoordinator(DataUpdateCoordinator[dict[str, NiceGODevice]]):
    """DataUpdateCoordinator for Nice G.O."""

    config_entry: ConfigEntry
    organization_id: str

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize DataUpdateCoordinator for Nice G.O."""
        super().__init__(
            hass,
            _LOGGER,
            name="Nice G.O.",
        )

        self.refresh_token = self.config_entry.data[CONF_REFRESH_TOKEN]
        self.refresh_token_creation_time = self.config_entry.data[
            CONF_REFRESH_TOKEN_CREATION_TIME
        ]
        self.email = self.config_entry.data[CONF_EMAIL]
        self.password = self.config_entry.data[CONF_PASSWORD]
        self.api = NiceGOApi()
        self.ws_connected = False

    async def _parse_barrier(self, barrier_state: BarrierState) -> NiceGODevice | None:
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

        light_status = barrier_state.reported["lightStatus"].split(",")[0] == "1"
        fw_version = barrier_state.reported["deviceFwVersion"]
        if barrier_state.connectionState:
            connected = barrier_state.connectionState.connected
        else:
            connected = False
        vacation_mode = barrier_state.reported["vcnMode"]

        return NiceGODevice(
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
                    await self._update_refresh_token()
                else:
                    await self.api.authenticate_refresh(
                        self.refresh_token, async_get_clientsession(self.hass)
                    )
                _LOGGER.debug("Authenticated with Nice G.O. API")

                barriers = await self.api.get_all_barriers()
                parsed_barriers = [
                    await self._parse_barrier(barrier.state) for barrier in barriers
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

    async def _update_refresh_token(self) -> None:
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
        self.api.event(self.on_connected)
        self.api.event(self.on_data)
        try:
            await self.api.connect(reconnect=True)
        except ApiError:
            _LOGGER.exception("API error")

        if not self.hass.is_stopping:
            await asyncio.sleep(5)
            await self.client_listen()

    async def on_data(self, data: dict[str, Any]) -> None:
        """Handle incoming data from the websocket."""
        _LOGGER.debug("Received data from the websocket")
        _LOGGER.debug(data)
        raw_data = data["data"]["devicesStatesUpdateFeed"]["item"]
        parsed_data = await self._parse_barrier(
            BarrierState(
                deviceId=raw_data["deviceId"],
                desired=json.loads(raw_data["desired"]),
                reported=json.loads(raw_data["reported"]),
                connectionState=ConnectionState(
                    connected=raw_data["connectionState"]["connected"],
                    updatedTimestamp=raw_data["connectionState"]["updatedTimestamp"],
                )
                if raw_data["connectionState"]
                else None,
                version=raw_data["version"],
                timestamp=raw_data["timestamp"],
            )
        )
        if parsed_data is None:
            return

        data_copy = self.data.copy()
        data_copy[parsed_data.id] = parsed_data

        self.async_set_updated_data(data_copy)

    async def on_connected(self) -> None:
        """Handle the websocket connection."""
        _LOGGER.debug("Connected to the websocket")
        await self.api.subscribe(self.organization_id)
