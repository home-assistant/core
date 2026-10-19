"""Coordinator for Powerfox integration."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import override

from powerfox import (
    Device,
    DeviceReport,
    Powerfox,
    PowerfoxAuthenticationError,
    PowerfoxConnectionError,
    PowerfoxNoDataError,
    PowerfoxPrivacyError,
    Poweropti,
)

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER, SCAN_INTERVAL


@dataclass
class PowerfoxAuthState:
    """Track authentication failures shared by all account coordinators."""

    failure_since: datetime | None = None
    last_verification: datetime | None = None
    verification_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def record_failure(self, now: datetime) -> bool:
        """Record a failure and return whether the grace period has expired."""
        if self.failure_since is None:
            self.failure_since = now
            return False

        return now - self.failure_since >= timedelta(minutes=5)

    def has_persistent_failure(self, now: datetime) -> bool:
        """Return whether authentication has failed for at least 30 minutes."""
        return self.failure_since is not None and now - self.failure_since >= timedelta(
            minutes=30
        )

    def record_success(self) -> None:
        """Reset the investigation after successful data retrieval."""
        self.failure_since = None
        self.last_verification = None


type PowerfoxCoordinator = (
    PowerfoxDataUpdateCoordinator | PowerfoxReportDataUpdateCoordinator
)
type PowerfoxConfigEntry = ConfigEntry[list[PowerfoxCoordinator]]


class PowerfoxBaseCoordinator[T](DataUpdateCoordinator[T]):
    """Base coordinator handling shared Powerfox logic."""

    config_entry: PowerfoxConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PowerfoxConfigEntry,
        client: Powerfox,
        device: Device,
        auth_state: PowerfoxAuthState,
    ) -> None:
        """Initialize shared Powerfox coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.device = device
        self.auth_state = auth_state

    @override
    async def _async_update_data(self) -> T:
        """Fetch data and normalize Powerfox errors."""
        try:
            data = await self._async_fetch_data()
        except PowerfoxAuthenticationError as err:
            now = dt_util.utcnow()

            if self.auth_state.record_failure(now):
                async with self.auth_state.verification_lock:
                    failure_since = self.auth_state.failure_since
                    last_verification = self.auth_state.last_verification

                    if (
                        failure_since is not None
                        and now - failure_since >= timedelta(minutes=5)
                        and (
                            last_verification is None
                            or now - last_verification >= timedelta(minutes=1)
                        )
                    ):
                        self.auth_state.last_verification = now

                        try:
                            await self.client.all_devices()
                        except PowerfoxAuthenticationError:
                            # Another 401 does not reliably distinguish invalid
                            # credentials from a temporary Powerfox API issue.
                            # Keep retrying instead of forcing reauthentication.
                            pass
                        except PowerfoxConnectionError:
                            pass

            if self.auth_state.has_persistent_failure(now):
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id=f"persistent_auth_failure_{self.config_entry.entry_id}",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="persistent_auth_failure",
                )

            if self.config_entry.state is not ConfigEntryState.LOADED:
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="auth_retry",
                ) from err

            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="auth_retry",
            ) from err
        except PowerfoxConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from err
        except PowerfoxNoDataError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_data_error",
                translation_placeholders={"device_name": self.device.name},
            ) from err
        except PowerfoxPrivacyError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="privacy_error",
                translation_placeholders={"device_name": self.device.name},
            ) from err
        else:
            self.auth_state.record_success()
            ir.async_delete_issue(
                self.hass,
                DOMAIN,
                f"persistent_auth_failure_{self.config_entry.entry_id}",
            )
            return data

    async def _async_fetch_data(self) -> T:
        """Fetch data from the Powerfox API."""
        raise NotImplementedError


class PowerfoxDataUpdateCoordinator(PowerfoxBaseCoordinator[Poweropti]):
    """Class to manage fetching Powerfox data from the API."""

    @override
    async def _async_fetch_data(self) -> Poweropti:
        """Fetch live device data from the Powerfox API."""
        return await self.client.device(device_id=self.device.id)


class PowerfoxReportDataUpdateCoordinator(PowerfoxBaseCoordinator[DeviceReport]):
    """Coordinator handling report data from the API."""

    @override
    async def _async_fetch_data(self) -> DeviceReport:
        """Fetch report data from the Powerfox API."""
        local_now = dt_util.now()
        return await self.client.report(
            device_id=self.device.id,
            year=local_now.year,
            month=local_now.month,
            day=local_now.day,
        )
