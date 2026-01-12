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

    api_client: UnraidClient
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

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_client: UnraidClient,
        server_name: str,
    ) -> None:
        """Initialize the system coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{server_name} System",
            update_interval=timedelta(seconds=DEFAULT_SYSTEM_POLL_INTERVAL),
            config_entry=config_entry,
        )
        self.api_client = api_client
        self._server_name = server_name
        self._previously_unavailable = False

    async def _async_update_data(self) -> UnraidSystemData:
        """Fetch system data from Unraid server using library methods."""
        try:
            metrics = await self.api_client.get_system_metrics()

            # Log recovery if previously unavailable
            if self._previously_unavailable:
                _LOGGER.info(
                    "Connection restored to Unraid server %s", self._server_name
                )
                self._previously_unavailable = False

            return UnraidSystemData(metrics=metrics)

        except UnraidAuthenticationError as err:
            self._previously_unavailable = True
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except UnraidConnectionError as err:
            self._previously_unavailable = True
            raise UpdateFailed(f"Connection error: {err}") from err
        except UnraidAPIError as err:
            self._previously_unavailable = True
            raise UpdateFailed(f"API error: {err}") from err
