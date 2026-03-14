"""Data update coordinator for the Jellyfin integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from jellyfin_apiclient_python import JellyfinClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client_wrapper import CannotConnect, InvalidAuth, _connect
from .const import (
    CONF_CLIENT_DEVICE_ID,
    DOMAIN,
    LOGGER,
    SERVER_KEY_ID,
    SERVER_KEY_NAME,
    SERVER_KEY_VERSION,
    UPDATE_INTERVAL_CONNECTED,
    UPDATE_INTERVAL_DISCONNECTED,
    USER_APP_NAME,
)

type JellyfinConfigEntry = ConfigEntry[JellyfinDataUpdateCoordinator]


class JellyfinDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Data update coordinator for the Jellyfin integration."""

    config_entry: JellyfinConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: JellyfinConfigEntry,
        api_client: JellyfinClient,
        system_info: dict[str, Any],
        user_id: str,
        connected: bool = True,
    ) -> None:
        """Initialize the coordinator."""
        interval = (
            UPDATE_INTERVAL_CONNECTED if connected else UPDATE_INTERVAL_DISCONNECTED
        )
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.api_client = api_client
        self.server_id: str = system_info.get(SERVER_KEY_ID, config_entry.entry_id)
        self.server_name: str = system_info.get(SERVER_KEY_NAME, "Jellyfin")
        self.server_version: str | None = system_info.get(SERVER_KEY_VERSION)
        self.client_device_id: str = config_entry.data[CONF_CLIENT_DEVICE_ID]
        self.user_id: str = user_id
        self.connected: bool = connected

        self.session_ids: set[str] = set()
        self.remote_session_ids: set[str] = set()
        self.device_ids: set[str] = set()

    def _reconnect(self) -> tuple[str, dict[str, Any]]:
        """Attempt to reconnect to the Jellyfin server."""
        return _connect(
            self.api_client,
            self.config_entry.data[CONF_URL],
            self.config_entry.data[CONF_USERNAME],
            self.config_entry.data[CONF_PASSWORD],
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Get the latest data from Jellyfin."""
        if not self.connected:
            try:
                user_id, connect_result = await self.hass.async_add_executor_job(
                    self._reconnect
                )
                self.connected = True
                # Keep server_id as entry_id for consistent device identification
                api_server = connect_result["Servers"][0]
                self.server_name = api_server.get("Name", "Jellyfin")
                self.server_version = api_server.get("Version")
                self.user_id = user_id
                self.update_interval = timedelta(seconds=UPDATE_INTERVAL_CONNECTED)
            except (CannotConnect, InvalidAuth, Exception) as err:
                raise UpdateFailed(f"Server unreachable: {err}") from err

        try:
            sessions = await self.hass.async_add_executor_job(
                self.api_client.jellyfin.sessions
            )
        except (KeyError, CannotConnect, InvalidAuth, Exception) as err:
            self.connected = False
            self.update_interval = timedelta(seconds=UPDATE_INTERVAL_DISCONNECTED)
            raise UpdateFailed(f"Error fetching Jellyfin sessions: {err}") from err

        if sessions is None:
            return {}

        sessions_by_id: dict[str, dict[str, Any]] = {
            session["Id"]: session
            for session in sessions
            if session["DeviceId"] != self.client_device_id
            and session["Client"] != USER_APP_NAME
        }

        self.device_ids = {session["DeviceId"] for session in sessions_by_id.values()}

        return sessions_by_id
