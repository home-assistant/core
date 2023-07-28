"""Data update coordinator for the Jellyfin integration."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any, TypeVar

from jellyfin_apiclient_python import JellyfinClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER, USER_APP_NAME

JellyfinDataT = TypeVar(
    "JellyfinDataT",
    bound=dict[str, dict[str, Any]] | dict[str, Any],
)


class JellyfinDataUpdateCoordinator(DataUpdateCoordinator[JellyfinDataT], ABC):
    """Data update coordinator for the Jellyfin integration."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: JellyfinClient,
        system_info: dict[str, Any],
        client_device_id: str,
        user_id: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=10),
        )
        self.api_client: JellyfinClient = api_client
        self.server_id: str = system_info["Id"]
        self.server_name: str = system_info["Name"]
        self.server_version: str | None = system_info.get("Version")
        self.client_device_id: str = client_device_id
        self.user_id: str = user_id

        self.session_ids: set[str] = set()

    async def _async_update_data(self) -> JellyfinDataT:
        """Get the latest data from Jellyfin."""
        return await self._fetch_data()

    @abstractmethod
    async def _fetch_data(self) -> JellyfinDataT:
        """Fetch the actual data."""


class SessionsDataUpdateCoordinator(
    JellyfinDataUpdateCoordinator[dict[str, dict[str, Any]]]
):
    """Sessions update coordinator for Jellyfin."""

    async def _fetch_data(self) -> dict[str, dict[str, Any]]:
        """Fetch the data."""
        sessions = await self.hass.async_add_executor_job(
            self.api_client.jellyfin.sessions
        )

        sessions_by_id: dict[str, dict[str, Any]] = {
            session["Id"]: session
            for session in sessions
            if session["DeviceId"] != self.client_device_id
            and session["Client"] != USER_APP_NAME
        }

        return sessions_by_id
