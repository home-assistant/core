"""Data update coordinator for the Deluge integration."""

from __future__ import annotations

from datetime import timedelta
from ssl import SSLError
from typing import Any

from deluge_client.client import DelugeRPCClient, FailedToReconnectException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_KEYS, LOGGER


class DelugeDataUpdateCoordinator(
    DataUpdateCoordinator[dict[Platform, dict[str, Any]]]
):
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

    async def _async_update_data(self) -> dict[Platform, dict[str, Any]]:
        """Get the latest data from Deluge and updates the state."""
        data = {}
        try:
            _data = await self.hass.async_add_executor_job(
                self.api.call,
                "core.get_session_status",
                DATA_KEYS,
            )
            data[Platform.SENSOR] = {k.decode(): v for k, v in _data.items()}
            data[Platform.SWITCH] = await self.hass.async_add_executor_job(
                self.api.call, "core.get_torrents_status", {}, ["paused"]
            )
        except (
            ConnectionRefusedError,
            TimeoutError,
            SSLError,
            FailedToReconnectException,
        ) as ex:
            raise UpdateFailed(f"Connection to Deluge Daemon Lost: {ex}") from ex
        except Exception as ex:
            if type(ex).__name__ == "BadLoginError":
                raise ConfigEntryAuthFailed(
                    "Credentials for Deluge client are not valid"
                ) from ex
            LOGGER.error("Unknown error connecting to Deluge: %s", ex)
            raise
        return data
