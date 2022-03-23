"""Data update coordinator for the Deluge integration."""
from __future__ import annotations

from datetime import timedelta
import socket
from ssl import SSLError

from deluge_client.client import DelugeRPCClient, FailedToReconnectException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER


class DelugeDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the Deluge integration."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, api: DelugeRPCClient, entry: ConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=entry.title,
            update_interval=timedelta(seconds=30),
        )
        self.api = api
        self.config_entry = entry

    async def _async_update_data(self) -> dict[Platform, dict[str, int | str]]:
        """Get the latest data from Deluge and updates the state."""
        data = {}
        try:
            data[Platform.SENSOR] = await self.hass.async_add_executor_job(
                self.api.call,
                "core.get_session_status",
                [
                    "upload_rate",
                    "download_rate",
                    "dht_upload_rate",
                    "dht_download_rate",
                ],
            )
            data[Platform.SWITCH] = await self.hass.async_add_executor_job(
                self.api.call, "core.get_torrents_status", {}, ["paused"]
            )
        except (
            ConnectionRefusedError,
            socket.timeout,  # pylint:disable=no-member
            SSLError,
            FailedToReconnectException,
        ) as ex:
            raise UpdateFailed(f"Connection to Deluge Daemon Lost: {ex}") from ex
        except Exception as ex:  # pylint:disable=broad-except
            if type(ex).__name__ == "BadLoginError":
                raise ConfigEntryAuthFailed(
                    "Credentials for Deluge client are not valid"
                ) from ex
            LOGGER.error("Unknown error connecting to Deluge: %s", ex)
            raise ex
        return data
