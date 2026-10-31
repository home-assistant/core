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
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DISCOVERY_INTERVAL, DOMAIN, FAST_POLLING_INTERVAL, UPDATE_INTERVAL

if TYPE_CHECKING:
    from . import GkpRuntimeData

    type GkpConfigEntry = ConfigEntry[GkpRuntimeData]

_LOGGER = logging.getLogger(__name__)


def _rate_limited_error(err: GkpRateLimitError) -> UpdateFailed:
    """Return an update failure retrying after the delay requested by the API."""
    return UpdateFailed(
        translation_domain=DOMAIN,
        translation_key="rate_limited",
        translation_placeholders={"retry_after": str(err.retry_after)},
        retry_after=err.retry_after,
    )


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
        self.last_discovery = 0.0
        self.first_wake_up: datetime | None = None
        self.last_wake_up: float | None = None

    @override
    async def _async_setup(self) -> None:
        """Discover the installations of the user before the first refresh."""
        try:
            await self._async_discover()
        except GkpError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="failed_to_discover_devices",
            ) from err

    @override
    async def _async_update_data(self) -> dict[str, Thermostat]:
        """Discover installations, wake up devices and fetch their state."""
        now = time.time()

        if now - self.last_discovery >= DISCOVERY_INTERVAL.total_seconds():
            try:
                await self._async_discover()
            except GkpError as err:
                _LOGGER.warning("Periodic discovery failed: %s", err)

        if (
            self.last_wake_up is None
            or now - self.last_wake_up >= USER_CONNECTED_INTERVAL.total_seconds()
        ):
            await self._async_wake_up_devices(now)
            # Read the state the devices report in answer to the wake up
            self.update_interval = USER_CONNECTED_REPORT_DELAY
        else:
            self.update_interval = UPDATE_INTERVAL

        return await self._async_fetch_thermostats()

    async def _async_discover(self) -> None:
        """Refresh the installations of the user."""
        try:
            installations = await self.client.get_installations()
        except GkpAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except GkpRateLimitError as err:
            raise _rate_limited_error(err) from err

        self.installations = {
            installation.installation_id: installation for installation in installations
        }
        self.last_discovery = time.time()
        self._remove_stale_devices()

    async def _async_wake_up_devices(self, now: float) -> None:
        """Ask the devices to report their current state."""
        for installation_id in self.installations:
            try:
                await self.client.notify_user_connected(installation_id)
            except GkpAuthError as err:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="authentication_failed",
                ) from err
            except GkpRateLimitError as err:
                raise _rate_limited_error(err) from err
            except GkpError as err:
                _LOGGER.debug(
                    "Failed to wake up devices of installation %s: %s",
                    installation_id,
                    err,
                )

        if self.first_wake_up is None:
            self.first_wake_up = dt_util.utcnow()
        self.last_wake_up = now

    async def _async_fetch_thermostats(self) -> dict[str, Thermostat]:
        """Fetch all thermostats, keeping the last state of failing ones."""
        try:
            result = await self.client.get_thermostats(self.installations.values())
        except GkpAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except GkpRateLimitError as err:
            raise _rate_limited_error(err) from err

        if result.errors and not result.thermostats:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="failed_to_update_devices",
            )

        thermostats = result.thermostats
        previous = self.data or {}
        for device_id, error in result.errors.items():
            _LOGGER.debug("Failed to update device %s: %s", device_id, error)
            if device_id in previous:
                thermostats[device_id] = previous[device_id]

        _LOGGER.debug("Updated %d devices", len(thermostats))
        return thermostats

    def _remove_stale_devices(self) -> None:
        """Remove devices that are no longer in the user installations."""
        assert self.config_entry is not None
        device_registry = dr.async_get(self.hass)
        identifiers = {(DOMAIN, device_id) for device_id in self.device_installations}
        for device in dr.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        ):
            if not device.identifiers & identifiers:
                _LOGGER.info("Removing stale device: %s", device.name)
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

        config_entry.async_on_unload(
            hub_coordinator.async_add_listener(self._handle_hub_update)
        )

    def _handle_hub_update(self) -> None:
        """Handle updates from hub coordinator.

        Update data and notify listeners without rescheduling the refresh
        interval, so an in-flight fast-polling cycle is not interrupted.
        """
        if not self.hub_coordinator.last_update_success:
            self.last_update_success = False
            self.async_update_listeners()
        elif self.hub_coordinator.data and self.device_id in self.hub_coordinator.data:
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
        except GkpAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except GkpRateLimitError as err:
            raise _rate_limited_error(err) from err
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
