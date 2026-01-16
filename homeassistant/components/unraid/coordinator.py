"""Data update coordinator for Unraid integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from unraid_api import UnraidClient
from unraid_api.exceptions import (
    UnraidAPIError,
    UnraidAuthenticationError,
    UnraidConnectionError,
)
from unraid_api.models import ServerInfo, SystemMetrics

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SYSTEM_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class UnraidRuntimeData:
    """Runtime data for Unraid integration (stored in entry.runtime_data)."""

    system_coordinator: UnraidSystemCoordinator
    server_info: ServerInfo


# Type alias for config entries with runtime data
type UnraidConfigEntry = ConfigEntry[UnraidRuntimeData]


@dataclass
class UnraidSystemData:
    """Data class for system coordinator data - uses library models."""

    metrics: SystemMetrics


class UnraidSystemCoordinator(DataUpdateCoordinator[UnraidSystemData]):
    """Coordinator for Unraid system data."""

    config_entry: UnraidConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: UnraidConfigEntry,
        api_client: UnraidClient,
        server_info: ServerInfo,
    ) -> None:
        """Initialize the system coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{server_info.hostname or 'Unraid'} System",
            update_interval=timedelta(seconds=DEFAULT_SYSTEM_POLL_INTERVAL),
            config_entry=config_entry,
        )
        self.api_client = api_client
        self.server_info = server_info

    async def _async_update_data(self) -> UnraidSystemData:
        """Fetch system data from Unraid server using library methods."""
        try:
            metrics = await self.api_client.get_system_metrics()
        except UnraidAuthenticationError as err:
            raise ConfigEntryError(f"Authentication failed: {err}") from err
        except UnraidConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err
        except UnraidAPIError as err:
            raise UpdateFailed(f"API error: {err}") from err

        return UnraidSystemData(metrics=metrics)
