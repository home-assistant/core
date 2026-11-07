"""Data update coordinator for the Jellyfin integration."""

from datetime import timedelta
from functools import partial
from typing import Any, override

from jellyfin_apiclient_python import JellyfinClient
from jellyfin_apiclient_python.exceptions import HTTPException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CLIENT_DEVICE_ID, DOMAIN, LOGGER, USER_APP_NAME

# Fail fast when the server is offline instead of blocking an executor
# thread with the library's default retries; the next poll retries anyway.
SESSIONS_TIMEOUT = 10

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

    @override
    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Get the latest data from Jellyfin."""
        try:
            sessions = await self.hass.async_add_executor_job(
                partial(
                    self.api_client.jellyfin.sessions,
                    timeout=SESSIONS_TIMEOUT,
                    retry=0,
                )
            )
        except HTTPException as err:
            if err.status == "Unauthorized":
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="invalid_auth",
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err.status)},
            ) from err

        if sessions is None:
            return {}

        sessions_by_id: dict[str, dict[str, Any]] = {
            session["Id"]: session
            for session in sessions
            if session["DeviceId"] != self.client_device_id
            and session["Client"] != USER_APP_NAME
            # Tools like Jellystat report sessions as the server itself
            and session["DeviceId"] != self.server_id
        }

        self.device_ids = {session["DeviceId"] for session in sessions_by_id.values()}

        return sessions_by_id
