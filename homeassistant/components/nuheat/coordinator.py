"""Data coordinator for NuHeat."""

from collections.abc import Callable
from datetime import datetime
import logging
from typing import TYPE_CHECKING, override

from chemelex_nuheat import (
    NuHeatApiError,
    NuHeatAuthError,
    NuHeatClient,
    NuHeatDataError,
    NuHeatPermissionError,
    NuHeatRateLimitError,
    Thermostat,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL, SETPOINT_RECONCILE_DELAY

if TYPE_CHECKING:
    from . import NuHeatConfigEntry

_LOGGER = logging.getLogger(__name__)


class NuHeatCoordinator(DataUpdateCoordinator[dict[str, Thermostat]]):
    """Poll the account and retain unavailable thermostats without optimism."""

    def __init__(
        self, hass: HomeAssistant, entry: NuHeatConfigEntry, api: NuHeatClient
    ) -> None:
        """Initialize account polling and delayed refresh cancellation."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api
        self._present_serials: set[str] = set()
        self._cancel_refresh: Callable[[], None] | None = None

    @property
    def shutdown_requested(self) -> bool:
        """Return whether new controls must stop during unload."""
        return self._shutdown_requested

    @property
    def cooldown_remaining(self) -> float:
        """Return the SDK's shared account request cooldown."""
        return self.api.cooldown_remaining

    @callback
    def async_schedule_reconciliation(self) -> None:
        """Request one delayed read, without retrying the command."""
        if self._shutdown_requested:
            return
        if self._cancel_refresh:
            self._cancel_refresh()
        self._cancel_refresh = async_call_later(
            self.hass,
            max(SETPOINT_RECONCILE_DELAY, self.cooldown_remaining),
            self._async_refresh_after_command,
        )

    async def _async_refresh_after_command(self, _now: datetime) -> None:
        self._cancel_refresh = None
        if not self._shutdown_requested:
            await self.async_refresh()

    @override
    async def async_shutdown(self) -> None:
        if self._cancel_refresh:
            self._cancel_refresh()
            self._cancel_refresh = None
        await super().async_shutdown()

    @override
    async def _async_update_data(self) -> dict[str, Thermostat]:
        if self.cooldown_remaining:
            raise UpdateFailed("NuHeat requests are throttled; retry after cooldown")
        try:
            thermostats = await self.api.list_thermostats()
        except NuHeatAuthError as err:
            raise ConfigEntryAuthFailed("NuHeat authorization expired") from err
        except NuHeatRateLimitError as err:
            raise UpdateFailed(
                "NuHeat requests are throttled; retry after cooldown"
            ) from err
        except NuHeatPermissionError as err:
            raise UpdateFailed(
                "NuHeat application permission denied; verify application access"
            ) from err
        except (NuHeatApiError, NuHeatDataError) as err:
            raise UpdateFailed("Unable to update NuHeat thermostats") from err
        fresh = {item.serial_number: item for item in thermostats}
        self._present_serials = set(fresh)
        # Missing devices retain their identities but are unavailable.
        return {**(self.data or {}), **fresh}

    def is_thermostat_available(self, serial_number: str) -> bool:
        """Retain omitted devices but report them as unavailable."""
        thermostat = (self.data or {}).get(serial_number)
        return (
            self.last_update_success
            and serial_number in self._present_serials
            and thermostat is not None
            and thermostat.online
        )
