"""Data update coordinator for the Deluge integration."""

from collections import Counter
from datetime import timedelta
from ssl import SSLError
from typing import Any

from deluge_client.client import DelugeRPCClient, FailedToReconnectException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    LOGGER,
    DelugeGetConfigValueKeys,
    DelugeGetSessionStatusKeys,
    DelugeSensorType,
    DelugeSetConfigKeys,
)

type DelugeConfigEntry = ConfigEntry[DelugeDataUpdateCoordinator]


def count_states(data: dict[str, Any]) -> dict[str, int]:
    """Count the states of the provided torrents."""

    counts = Counter(torrent[b"state"].decode() for torrent in data.values())

    return {
        DelugeSensorType.DOWNLOADING_COUNT_SENSOR.value: counts.get("Downloading", 0),
        DelugeSensorType.SEEDING_COUNT_SENSOR.value: counts.get("Seeding", 0),
    }


class DelugeDataUpdateCoordinator(
    DataUpdateCoordinator[dict[Platform, dict[str, Any]]]
):
    """Data update coordinator for the Deluge integration."""

    config_entry: DelugeConfigEntry

    def __init__(
        self, hass: HomeAssistant, api: DelugeRPCClient, entry: DelugeConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=60),
        )
        self.api = api

    def set_listen_port(self, port: int) -> None:
        """Set Deluge to use one fixed listen port.

        Deluge stores the incoming ports as a [start_port, end_port] list.
        Setting both values to the same port creates a single fixed port.
        random_port must be disabled, otherwise Deluge may ignore listen_ports.
        """
        if not 1 <= port <= 65535:
            raise ValueError(f"Invalid Deluge listen port: {port}")

        self.api.call(
            "core.set_config",
            {
                DelugeSetConfigKeys.LISTEN_PORTS.value: [port, port],
                DelugeSetConfigKeys.RANDOM_PORT.value: False,
            },
        )

    def _get_deluge_data(self):
        """Get the latest data from Deluge."""

        data = {}
        try:
            data["session_status"] = self.api.call(
                "core.get_session_status",
                [iter_member.value for iter_member in list(DelugeGetSessionStatusKeys)],
            )
            data["torrents_status_state"] = self.api.call(
                "core.get_torrents_status", {}, ["state"]
            )
            data["torrents_status_paused"] = self.api.call(
                "core.get_torrents_status", {}, ["paused"]
            )
            data["listen_ports"] = self.api.call(
                "core.get_config_value", DelugeGetConfigValueKeys.LISTEN_PORTS.value
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

    async def _async_update_data(self) -> dict[Platform, dict[str, Any]]:
        """Get the latest data from Deluge and updates the state."""

        deluge_data = await self.hass.async_add_executor_job(self._get_deluge_data)

        data = {}
        data[Platform.SENSOR] = {
            (k.decode() if isinstance(k, bytes) else k): v
            for k, v in deluge_data["session_status"].items()
        }
        data[Platform.SENSOR].update(count_states(deluge_data["torrents_status_state"]))
        # Normalize keys to strings for the SWITCH platform
        data[Platform.SWITCH] = {
            k.decode(): v for k, v in deluge_data["torrents_status_paused"].items()
        }
        data[Platform.SENSOR][DelugeSensorType.LISTEN_PORTS_SENSOR.value] = deluge_data[
            "listen_ports"
        ]
        return data
