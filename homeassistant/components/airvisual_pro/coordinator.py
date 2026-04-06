"""DataUpdateCoordinator for the AirVisual Pro integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pyairvisual.node import (
    InvalidAuthenticationError,
    NodeConnectionError,
    NodeProError,
    NodeSamba,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

UPDATE_INTERVAL = timedelta(minutes=1)


@dataclass
class AirVisualProData:
    """Define a data class."""

    coordinator: AirVisualProCoordinator
    node: NodeSamba


type AirVisualProConfigEntry = ConfigEntry[AirVisualProData]


class AirVisualProCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for AirVisual Pro data."""

    config_entry: AirVisualProConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AirVisualProConfigEntry,
        node: NodeSamba,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Node/Pro data",
            update_interval=UPDATE_INTERVAL,
        )
        self._node = node
        self.reload_task: asyncio.Task[bool] | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Get data from the device."""
        try:
            data = await self._node.async_get_latest_measurements()
            data["history"] = {}
            if data["settings"].get("follow_mode") == "device":
                history = await self._node.async_get_history(include_trends=False)
                data["history"] = history.get("measurements", [])[-1]
        except InvalidAuthenticationError as err:
            raise ConfigEntryAuthFailed("Invalid Samba password") from err
        except NodeConnectionError as err:
            if self.reload_task is None:
                self.reload_task = self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.config_entry.entry_id)
                )
            raise UpdateFailed(f"Connection to Pro unit lost: {err}") from err
        except NodeProError as err:
            raise UpdateFailed(f"Error while retrieving data: {err}") from err

        return data
