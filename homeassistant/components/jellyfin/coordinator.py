"""Data update coordinator for the Jellyfin integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from jellyfin_apiclient_python import JellyfinClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_CLIENT_DEVICE_ID, DOMAIN, LOGGER, USER_APP_NAME

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
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=10),
        )
        self.api_client = api_client
        self.server_id: str = system_info["Id"]
        self.server_name: str = system_info["Name"]
        self.server_version: str | None = system_info.get("Version")
        self.client_device_id: str = config_entry.data[CONF_CLIENT_DEVICE_ID]
        self.user_id: str = user_id

        self.session_ids: set[str] = set()
        self.remote_session_ids: set[str] = set()
        self.device_ids: set[str] = set()

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from Jellyfin API and handle errors gracefully."""
        try:
            sessions = await self.hass.async_add_executor_job(
                self.api_client.jellyfin.sessions
            )
            return sessions

        except requests.exceptions.ConnectionError as err:
            _LOGGER.error("Jellyfin server unreachable: %s", err)

        except KeyError as err:
            _LOGGER.error("Missing key in Jellyfin API response: %s", err)

        except Exception as err:
            _LOGGER.error("Unexpected error fetching Jellyfin data: %s", err)

        return None  # Mark the device as unavailable
