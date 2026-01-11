"""Data update coordinators for Unraid integration."""

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
from unraid_api.models import (
    DockerContainer,
    NotificationOverview,
    ServerInfo,
    Share,
    SystemMetrics,
    UnraidArray,
    UPSDevice,
    VmDomain,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_STORAGE_POLL_INTERVAL, DEFAULT_SYSTEM_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class UnraidRuntimeData:
    """Runtime data for Unraid integration (stored in entry.runtime_data)."""

    api_client: UnraidClient
    system_coordinator: UnraidSystemCoordinator
    storage_coordinator: UnraidStorageCoordinator
    server_info: ServerInfo


# Type alias for config entries with runtime data
type UnraidConfigEntry = ConfigEntry[UnraidRuntimeData]


@dataclass
class UnraidSystemData:
    """Data class for system coordinator data - uses library models."""

    metrics: SystemMetrics
    containers: list[DockerContainer]
    vms: list[VmDomain]
    ups_devices: list[UPSDevice]
    notifications: NotificationOverview


@dataclass
class UnraidStorageData:
    """Data class for storage coordinator data - uses library models."""

    array: UnraidArray
    shares: list[Share]


class UnraidSystemCoordinator(DataUpdateCoordinator[UnraidSystemData]):
    """Coordinator for Unraid system data (30s polling)."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_client: UnraidClient,
        server_name: str,
        update_interval: int = DEFAULT_SYSTEM_POLL_INTERVAL,
    ) -> None:
        """Initialize the system coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{server_name} System",
            update_interval=timedelta(seconds=update_interval),
            config_entry=config_entry,
        )
        self.api_client = api_client
        self._server_name = server_name
        self._previously_unavailable = False

    async def _async_update_data(self) -> UnraidSystemData:
        """Fetch system data from Unraid server using library methods."""
        try:
            # Use typed library methods - no GraphQL in HA code
            metrics = await self.api_client.get_system_metrics()
            notifications = await self.api_client.get_notification_overview()

            # Query optional services (fail gracefully if not enabled)
            containers = await self._get_optional_containers()
            vms = await self._get_optional_vms()
            ups_devices = await self._get_optional_ups()

            # Log recovery if previously unavailable
            if self._previously_unavailable:
                _LOGGER.info(
                    "Connection restored to Unraid server %s", self._server_name
                )
                self._previously_unavailable = False

            return UnraidSystemData(
                metrics=metrics,
                containers=containers,
                vms=vms,
                ups_devices=ups_devices,
                notifications=notifications,
            )

        except UnraidAuthenticationError as err:
            self._previously_unavailable = True
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except UnraidConnectionError as err:
            self._previously_unavailable = True
            raise UpdateFailed(f"Connection error: {err}") from err
        except UnraidAPIError as err:
            self._previously_unavailable = True
            raise UpdateFailed(f"API error: {err}") from err

    async def _get_optional_containers(self) -> list[DockerContainer]:
        """Get Docker containers (fails gracefully if Docker not enabled)."""
        try:
            return await self.api_client.typed_get_containers()
        except (UnraidAPIError, UnraidConnectionError) as err:
            _LOGGER.debug("Docker data not available: %s", err)
            return []

    async def _get_optional_vms(self) -> list[VmDomain]:
        """Get VMs (fails gracefully if VMs not enabled)."""
        try:
            return await self.api_client.typed_get_vms()
        except (UnraidAPIError, UnraidConnectionError) as err:
            _LOGGER.debug("VM data not available: %s", err)
            return []

    async def _get_optional_ups(self) -> list[UPSDevice]:
        """Get UPS devices (fails gracefully if no UPS configured)."""
        try:
            return await self.api_client.typed_get_ups_devices()
        except (UnraidAPIError, UnraidConnectionError) as err:
            _LOGGER.debug("UPS data not available: %s", err)
            return []


class UnraidStorageCoordinator(DataUpdateCoordinator[UnraidStorageData]):
    """Coordinator for Unraid storage data (5min polling)."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_client: UnraidClient,
        server_name: str,
        update_interval: int = DEFAULT_STORAGE_POLL_INTERVAL,
    ) -> None:
        """Initialize the storage coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{server_name} Storage",
            update_interval=timedelta(seconds=update_interval),
            config_entry=config_entry,
        )
        self.api_client = api_client
        self._server_name = server_name
        self._previously_unavailable = False

    async def _async_update_data(self) -> UnraidStorageData:
        """Fetch storage data from Unraid server using library methods."""
        try:
            # Use typed library methods - no GraphQL in HA code
            array = await self.api_client.typed_get_array()
            shares = await self._get_optional_shares()

            if self._previously_unavailable:
                _LOGGER.info(
                    "Connection restored to Unraid server %s (storage)",
                    self._server_name,
                )
                self._previously_unavailable = False

            return UnraidStorageData(
                array=array,
                shares=shares,
            )

        except UnraidAuthenticationError as err:
            self._previously_unavailable = True
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except UnraidConnectionError as err:
            self._previously_unavailable = True
            raise UpdateFailed(f"Connection error: {err}") from err
        except UnraidAPIError as err:
            self._previously_unavailable = True
            raise UpdateFailed(f"API error: {err}") from err

    async def _get_optional_shares(self) -> list[Share]:
        """Get shares (fails gracefully if shares query fails)."""
        try:
            return await self.api_client.typed_get_shares()
        except (UnraidAPIError, UnraidConnectionError) as err:
            _LOGGER.debug(
                "Shares query failed (will continue without share data): %s", err
            )
            return []
