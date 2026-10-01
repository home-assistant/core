"""Data coordinators for GKP integration."""

from dataclasses import dataclass
from datetime import datetime
import logging
import time
from typing import TYPE_CHECKING, override

from gkphomepython import (
    USER_CONNECTED_INTERVAL,
    USER_CONNECTED_REPORT_DELAY,
    GkpAuthError,
    GkpClient,
    GkpError,
    GkpRateLimitError,
    Installation,
    Thermostat,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DISCOVERY_INTERVAL, DOMAIN, FAST_POLLING_INTERVAL, UPDATE_INTERVAL

if TYPE_CHECKING:
    from . import GkpRuntimeData

    type GkpConfigEntry = ConfigEntry[GkpRuntimeData]

_LOGGER = logging.getLogger(__name__)


@dataclass
class GkpDeviceData:
    """Data class for device coordinator."""

    thermostat: Thermostat


class GkpHubCoordinator(DataUpdateCoordinator[dict[str, Thermostat]]):
    """Hub coordinator discovering installations and polling all thermostats."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: GkpClient,
        config_entry: GkpConfigEntry,
    ) -> None:
        """Initialize the hub coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client
        self.installations: dict[str, Installation] = {}
        self.last_discovery: float | None = None
        self.first_user_connected: datetime | None = None
        self.last_user_connected: float | None = None

    @override
    async def _async_update_data(self) -> dict[str, Thermostat]:
        """Discover installations, wake up devices and fetch their state."""
        now = time.time()

        if (
            self.last_discovery is None
            or now - self.last_discovery >= DISCOVERY_INTERVAL.total_seconds()
        ):
            await self._async_discover(now)

        if (
            self.last_user_connected is None
            or now - self.last_user_connected >= USER_CONNECTED_INTERVAL.total_seconds()
        ):
            await self._async_notify_user_connected()
            if self.first_user_connected is None:
                self.first_user_connected = dt_util.utcnow()
            self.last_user_connected = now
            self.update_interval = USER_CONNECTED_REPORT_DELAY
        else:
            self.update_interval = UPDATE_INTERVAL

        return await self._async_fetch_thermostats()

    async def _async_discover(self, now: float) -> None:
        """Refresh the installations of the user."""
        is_first_refresh = self.last_discovery is None
        try:
            installations = await self.client.get_installations()
        except GkpAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except GkpError as err:
            if is_first_refresh:
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="failed_to_discover_devices",
                ) from err
            _LOGGER.warning("Periodic discovery failed: %s", err)
            return

        previous_devices = set(self.device_installations)
        self.installations = {
            installation.installation_id: installation for installation in installations
        }
        self.last_discovery = now

        if stale_devices := previous_devices - set(self.device_installations):
            self._remove_stale_devices(stale_devices)

    async def _async_notify_user_connected(self) -> None:
        """Ask the devices to report their current state."""
        for installation_id in self.installations:
            try:
                await self.client.notify_user_connected(installation_id)
            except GkpAuthError as err:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="authentication_failed",
                ) from err
            except GkpError as err:
                _LOGGER.warning(
                    "Failed to wake up devices of installation %s: %s",
                    installation_id,
                    err,
                )

    async def _async_fetch_thermostats(self) -> dict[str, Thermostat]:
        """Fetch all thermostats, keeping the last state of failing ones."""
        results = await self.client.get_thermostats(self.installations.values())
        if not results:
            return {}

        previous = self.data or {}
        thermostats: dict[str, Thermostat] = {}
        failures = 0
        rate_limit_error: GkpRateLimitError | None = None
        for device_id, result in results.items():
            if isinstance(result, Thermostat):
                thermostats[device_id] = result
                continue
            if isinstance(result, GkpAuthError):
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="authentication_failed",
                ) from result
            if isinstance(result, GkpRateLimitError):
                rate_limit_error = result
            failures += 1
            _LOGGER.debug("Failed to update device %s: %s", device_id, result)
            if device_id in previous:
                thermostats[device_id] = previous[device_id]

        if failures == len(results):
            if rate_limit_error is not None:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="rate_limited",
                    translation_placeholders={
                        "retry_after": str(rate_limit_error.retry_after)
                    },
                    retry_after=rate_limit_error.retry_after,
                )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="failed_to_update_devices",
            )

        _LOGGER.debug("Updated %d devices", len(thermostats))
        return thermostats

    def _remove_stale_devices(self, stale_device_ids: set[str]) -> None:
        """Remove devices that are no longer in the user installations."""
        assert self.config_entry is not None
        device_registry = dr.async_get(self.hass)

        for device_id in stale_device_ids:
            _LOGGER.info("Removing stale device: %s", device_id)

            device = device_registry.async_get_device_by_identifier(
                (DOMAIN, device_id), self.config_entry.entry_id
            )
            if device:
                device_registry.async_remove_device(device.id)

    @property
    def device_installations(self) -> dict[str, Installation]:
        """Return the installation of each known device."""
        return {
            device_id: installation
            for installation in self.installations.values()
            for device_id in installation.device_ids
        }


class GkpDeviceCoordinator(DataUpdateCoordinator[GkpDeviceData]):
    """Device coordinator for refreshes after a command."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: GkpClient,
        config_entry: GkpConfigEntry,
        hub_coordinator: GkpHubCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the device coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_id}",
            update_interval=None,  # Manual refresh only
            config_entry=config_entry,
        )
        self.client = client
        self.device_id = device_id
        self.installation = hub_coordinator.device_installations[device_id]
        self.hub_coordinator = hub_coordinator
        self.fast_polling_until: float | None = None

        self.unsubscribe_hub_listener = hub_coordinator.async_add_listener(
            self._handle_hub_update
        )

    def _handle_hub_update(self) -> None:
        """Handle updates from hub coordinator.

        Update data and notify listeners without rescheduling the refresh
        interval, so an in-flight fast-polling cycle is not interrupted.
        """
        if (
            self.hub_coordinator.last_update_success
            and self.hub_coordinator.data
            and self.device_id in self.hub_coordinator.data
        ):
            self.data = GkpDeviceData(
                thermostat=self.hub_coordinator.data[self.device_id]
            )
            self.last_update_success = True
            self.async_update_listeners()

    @override
    async def _async_update_data(self) -> GkpDeviceData:
        """Refresh the thermostat."""
        if self.fast_polling_until and time.time() > self.fast_polling_until:
            self.fast_polling_until = None
            self.update_interval = None
            _LOGGER.debug(
                "Device %s: Fast polling period ended, returning to manual refresh",
                self.device_id,
            )

        try:
            thermostat = await self.client.get_thermostat(
                self.device_id, self.installation
            )
        except GkpError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="failed_to_refresh_device",
                translation_placeholders={"device_id": self.device_id},
            ) from err

        _LOGGER.debug("Refreshed device %s", self.device_id)
        return GkpDeviceData(thermostat=thermostat)

    def trigger_fast_polling(self, duration_seconds: int = 60) -> None:
        """Activate fast polling for a specified duration after a command."""
        self.fast_polling_until = time.time() + duration_seconds
        self.update_interval = FAST_POLLING_INTERVAL
        _LOGGER.debug(
            "Device %s: Activated fast polling for %d seconds",
            self.device_id,
            duration_seconds,
        )
