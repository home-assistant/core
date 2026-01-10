"""Data update coordinators for Unraid integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

import aiohttp
from unraid_api import UnraidClient
from unraid_api.exceptions import UnraidAPIError

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
    server_info: dict[str, Any]


# Type alias for config entries with runtime data
type UnraidConfigEntry = ConfigEntry[UnraidRuntimeData]


@dataclass
class UnraidSystemData:
    """Data class for system coordinator data - uses raw dict values."""

    # Raw data from API (no pydantic)
    info: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    containers: list[dict[str, Any]] = field(default_factory=list)
    vms: list[dict[str, Any]] = field(default_factory=list)
    ups_devices: list[dict[str, Any]] = field(default_factory=list)
    notifications_unread: int = 0


@dataclass
class UnraidStorageData:
    """Data class for storage coordinator data - uses raw dict values."""

    array_state: str | None = None
    capacity: dict[str, Any] | None = None
    parity_status: dict[str, Any] | None = None
    boot: dict[str, Any] | None = None
    disks: list[dict[str, Any]] = field(default_factory=list)
    parities: list[dict[str, Any]] = field(default_factory=list)
    caches: list[dict[str, Any]] = field(default_factory=list)
    shares: list[dict[str, Any]] = field(default_factory=list)


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

    async def _query_optional_docker(self) -> dict[str, Any]:
        """Query Docker data separately (fails gracefully if Docker not enabled)."""
        try:
            docker_query = """
                query {
                    docker {
                        containers {
                            id names state image
                            ports { privatePort publicPort type }
                        }
                    }
                }
            """
            result = await self.api_client.query(docker_query)
            return result.get("docker") or {"containers": []}
        except (UnraidAPIError, aiohttp.ClientError, RuntimeError, ValueError) as err:
            _LOGGER.debug("Docker data not available: %s", err)
            return {"containers": []}

    async def _query_optional_vms(self) -> dict[str, Any]:
        """Query VM data separately (fails gracefully if VMs not enabled)."""
        try:
            vms_query = """
                query {
                    vms { domain { id name state } }
                }
            """
            result = await self.api_client.query(vms_query)
            return result.get("vms") or {"domain": []}
        except (UnraidAPIError, aiohttp.ClientError, RuntimeError, ValueError) as err:
            _LOGGER.debug("VM data not available: %s", err)
            return {"domain": []}

    async def _query_optional_ups(self) -> list[dict[str, Any]]:
        """Query UPS data separately (fails gracefully if no UPS configured)."""
        try:
            ups_query = """
                query {
                    upsDevices {
                        id name status
                        battery { chargeLevel estimatedRuntime }
                        power { inputVoltage outputVoltage loadPercentage }
                    }
                }
            """
            result = await self.api_client.query(ups_query)
            return result.get("upsDevices") or []
        except (UnraidAPIError, aiohttp.ClientError, RuntimeError, ValueError) as err:
            _LOGGER.debug("UPS data not available: %s", err)
            return []

    async def _async_update_data(self) -> UnraidSystemData:
        """Fetch system data from Unraid server."""
        _LOGGER.debug("Starting system data update")
        try:
            # Query core system data (must succeed)
            query = """
                query {
                    info {
                        time
                        system { uuid manufacturer model serial }
                        cpu { brand threads cores packages { temp totalPower } }
                        os { hostname uptime kernel }
                        versions { core { unraid api kernel } }
                    }
                    metrics {
                        cpu { percentTotal }
                        memory {
                            total used free available percentTotal
                            swapTotal swapUsed swapFree percentSwapTotal
                        }
                    }
                    notifications {
                        overview { unread { total info warning alert } }
                    }
                }
            """
            raw_data = await self.api_client.query(query)

            # Query optional services separately (fail gracefully if not enabled)
            raw_data["docker"] = await self._query_optional_docker()
            raw_data["vms"] = await self._query_optional_vms()
            raw_data["upsDevices"] = await self._query_optional_ups()

            # Log recovery if previously unavailable
            if self._previously_unavailable:
                _LOGGER.info(
                    "Connection restored to Unraid server %s", self._server_name
                )
                self._previously_unavailable = False

            _LOGGER.debug("System data update completed successfully")

            # Parse raw data (simple dict extraction, no pydantic)
            return self._parse_system_data(raw_data)

        except aiohttp.ClientResponseError as err:
            self._previously_unavailable = True
            if err.status in (401, 403):
                msg = f"Authentication failed: {err.message}"
                raise UpdateFailed(msg) from err
            msg = f"HTTP error {err.status}: {err.message}"
            raise UpdateFailed(msg) from err
        except aiohttp.ClientError as err:
            self._previously_unavailable = True
            msg = f"Connection error: {err}"
            raise UpdateFailed(msg) from err
        except TimeoutError as err:
            self._previously_unavailable = True
            raise UpdateFailed("Request timeout") from err
        except Exception as err:
            self._previously_unavailable = True
            msg = f"Unexpected error: {err}"
            raise UpdateFailed(msg) from err

    def _parse_system_data(self, raw_data: dict[str, Any]) -> UnraidSystemData:
        """Parse raw API data into UnraidSystemData (no pydantic)."""
        # Parse Docker containers - normalize names field
        containers: list[dict[str, Any]] = []
        docker_data = raw_data.get("docker", {})
        for raw_container in docker_data.get("containers", []):
            container = dict(raw_container)
            names = container.get("names")
            if names and len(names) > 0:
                container["name"] = names[0].lstrip("/")
            containers.append(container)

        # Parse VMs
        vms_data = raw_data.get("vms") or {}
        vms = vms_data.get("domain", []) or []

        # Parse UPS devices
        ups_devices = raw_data.get("upsDevices", []) or []

        # Parse notifications
        notifications = raw_data.get("notifications", {})
        overview = notifications.get("overview", {})
        unread = overview.get("unread", {})
        notifications_unread = unread.get("total", 0) or 0

        return UnraidSystemData(
            info=raw_data.get("info", {}),
            metrics=raw_data.get("metrics", {}),
            containers=containers,
            vms=vms,
            ups_devices=ups_devices,
            notifications_unread=notifications_unread,
        )


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

    async def _query_optional_shares(self) -> list[dict[str, Any]]:
        """Query shares separately to handle servers with problematic shares."""
        try:
            shares_query = """
                query {
                    shares { id name size used free }
                }
            """
            result = await self.api_client.query(shares_query)
            return result.get("shares", []) or []
        except (UnraidAPIError, aiohttp.ClientError, RuntimeError, ValueError) as err:
            _LOGGER.debug(
                "Shares query failed (will continue without share data): %s", err
            )
            return []

    async def _async_update_data(self) -> UnraidStorageData:
        """Fetch storage data from Unraid server."""
        try:
            query = """
                query {
                    array {
                        state
                        capacity { kilobytes { total used free } }
                        parityCheckStatus { status progress errors }
                        boot {
                            id name device size status type
                            fsSize fsUsed fsFree fsType
                        }
                        disks {
                            id idx name device size status temp type
                            fsSize fsUsed fsFree fsType isSpinning
                        }
                        parities { id idx name device size status temp type isSpinning }
                        caches {
                            id idx name device size status temp type
                            fsSize fsUsed fsFree fsType isSpinning
                        }
                    }
                }
            """

            raw_data = await self.api_client.query(query)
            shares_data = await self._query_optional_shares()

            if self._previously_unavailable:
                _LOGGER.info(
                    "Connection restored to Unraid server %s (storage)",
                    self._server_name,
                )
                self._previously_unavailable = False

            return self._parse_storage_data(raw_data, shares_data)

        except aiohttp.ClientResponseError as err:
            self._previously_unavailable = True
            if err.status in (401, 403):
                raise UpdateFailed(f"Authentication failed: {err.message}") from err
            raise UpdateFailed(f"HTTP error {err.status}: {err.message}") from err
        except aiohttp.ClientError as err:
            self._previously_unavailable = True
            raise UpdateFailed(f"Connection error: {err}") from err
        except TimeoutError as err:
            self._previously_unavailable = True
            raise UpdateFailed("Request timeout") from err
        except Exception as err:
            self._previously_unavailable = True
            raise UpdateFailed(f"Unexpected error: {err}") from err

    def _parse_storage_data(
        self, raw_data: dict[str, Any], shares_data: list[dict[str, Any]]
    ) -> UnraidStorageData:
        """Parse raw API data into UnraidStorageData (no pydantic)."""
        array_data = raw_data.get("array", {})

        # Set default type for disks if not present
        disks = []
        for disk in array_data.get("disks", []):
            d = dict(disk)
            d.setdefault("type", "DATA")
            disks.append(d)

        parities = []
        for disk in array_data.get("parities", []):
            d = dict(disk)
            d.setdefault("type", "PARITY")
            parities.append(d)

        caches = []
        for disk in array_data.get("caches", []):
            d = dict(disk)
            d.setdefault("type", "CACHE")
            caches.append(d)

        boot = array_data.get("boot")
        if boot:
            boot = dict(boot)
            boot.setdefault("type", "FLASH")

        return UnraidStorageData(
            array_state=array_data.get("state"),
            capacity=array_data.get("capacity"),
            parity_status=array_data.get("parityCheckStatus"),
            boot=boot,
            disks=disks,
            parities=parities,
            caches=caches,
            shares=shares_data,
        )
