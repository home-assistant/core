"""Data coordinator for NuHeat."""

from asyncio import Lock
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from math import isclose
from typing import TYPE_CHECKING, override

from chemelex_nuheat import (
    NuHeatApiError,
    NuHeatAuthError,
    NuHeatClient,
    NuHeatDataError,
    NuHeatPermissionError,
    NuHeatRateLimitError,
    ScheduleMode,
    Thermostat,
    ThermostatState,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    SCAN_INTERVAL,
    SETPOINT_RECONCILE_DELAY,
    SETPOINT_RECONCILE_RETRY,
    SETPOINT_RECONCILE_TIMEOUT,
)

if TYPE_CHECKING:
    from . import NuHeatConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class PendingSetpoint:
    """A requested Celsius target awaiting cloud confirmation."""

    temperature: float
    cancel_timeout: Callable[[], None]
    hold_until: datetime | None = None


@dataclass
class PendingMode:
    """An accepted mode intent; object identity guards read generations."""

    state: ThermostatState
    cancel_timeout: Callable[[], None]


MODE_TO_STATE = {
    ScheduleMode.AUTO: ThermostatState.SCHEDULED,
    ScheduleMode.MANUAL: ThermostatState.MANUAL,
    ScheduleMode.PERMANENT_HOLD: ThermostatState.PERMANENT_HOLD,
    ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE: ThermostatState.TIMED_HOLD,
}


class NuHeatCoordinator(DataUpdateCoordinator[dict[str, Thermostat]]):
    """Poll and retain all thermostats belonging to the linked account."""

    def __init__(
        self, hass: HomeAssistant, entry: NuHeatConfigEntry, api: NuHeatClient
    ) -> None:
        """Initialize the NuHeat coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api
        self._present_serials: set[str] = set()
        self._pending_setpoints: dict[str, PendingSetpoint] = {}
        self._pending_modes: dict[str, PendingMode] = {}
        self._cancel_reconcile: Callable[[], None] | None = None
        self._reconcile_is_initial = False
        self._cooldown_read_due = False
        self._read_lock = Lock()
        self._read_generation = 0

    @property
    def shutdown_requested(self) -> bool:
        """Return whether the coordinator is shutting down."""
        return self._shutdown_requested

    @property
    def confirmation_status(self) -> dict[str, int]:
        """Return only allowlisted confirmation counts for local diagnostics."""
        return {
            "pending_targets": len(self._pending_setpoints),
            "pending_modes": len(self._pending_modes),
            "pending_expiries": sum(
                pending.hold_until is not None
                for pending in self._pending_setpoints.values()
            ),
        }

    @property
    def cooldown_remaining(self) -> float:
        """Return SDK-owned cooldown shared across every account endpoint."""
        return self.api.cooldown_remaining

    async def _async_coalesced_refresh(self, *, scheduled: bool = False) -> None:
        """Share a completed sample when poll and reconciliation overlap."""
        generation = self._read_generation
        async with self._debounced_refresh.async_lock():
            if generation == self._read_generation:
                await self._async_refresh(log_failures=True, scheduled=scheduled)

    @override
    async def async_refresh(self) -> None:
        await self._async_coalesced_refresh()

    @override
    async def _handle_refresh_interval(self, _now: datetime | None = None) -> None:
        self._unsub_refresh = None
        await self._async_coalesced_refresh(scheduled=True)

    def pending_mode(self, serial_number: str) -> ThermostatState | None:
        """Return the accepted mode while its confirmation is bounded."""
        if pending := self._pending_modes.get(serial_number):
            return pending.state
        return None

    @callback
    def async_set_pending_mode(
        self, serial_number: str, mode: ScheduleMode | None
    ) -> None:
        """Track complete readback; None represents frost-protected Standby."""
        self.async_clear_pending_mode(serial_number)

        @callback
        def expire(_now: datetime) -> None:
            if self._pending_modes.get(serial_number) is not pending:
                return
            self.async_clear_pending_mode(serial_number)
            _LOGGER.warning("NuHeat mode was not confirmed before the timeout")
            self.async_update_listeners()

        pending = PendingMode(
            ThermostatState.STANDBY if mode is None else MODE_TO_STATE[mode],
            async_call_later(self.hass, SETPOINT_RECONCILE_TIMEOUT, expire),
        )
        self._pending_modes[serial_number] = pending
        self.async_schedule_reconciliation()
        self.async_update_listeners()

    @callback
    def async_clear_pending_mode(
        self, serial_number: str, *, confirmed: bool = False
    ) -> None:
        """Cancel a superseded, confirmed, or expired mode generation."""
        if pending := self._pending_modes.pop(serial_number, None):
            pending.cancel_timeout()
        if not (confirmed and self._reconcile_is_initial):
            self._cancel_idle_reconciliation()

    @callback
    def _cancel_idle_reconciliation(self) -> None:
        if (
            not self._pending_setpoints
            and not self._pending_modes
            and not self._cooldown_read_due
            and self._cancel_reconcile
        ):
            self._cancel_reconcile()
            self._cancel_reconcile = None

    def pending_setpoint(self, serial_number: str) -> float | None:
        """Return a temporary requested target, without changing cloud data."""
        if pending := self._pending_setpoints.get(serial_number):
            return pending.temperature
        return None

    def pending_hold_until(self, serial_number: str) -> datetime | None:
        """Retain a newly accepted timed expiry until cloud confirmation/deadline."""
        if pending := self._pending_setpoints.get(serial_number):
            return pending.hold_until
        return None

    @callback
    def async_set_pending_setpoint(
        self,
        serial_number: str,
        temperature: float,
        *,
        hold_until: datetime | None = None,
    ) -> None:
        """Publish an accepted command until confirmed or its deadline expires."""
        self.async_clear_pending_setpoint(serial_number)

        @callback
        def expire(_now: datetime) -> None:
            if self._pending_setpoints.get(serial_number) is not pending:
                return
            self.async_clear_pending_setpoint(serial_number)
            _LOGGER.warning("NuHeat setpoint was not confirmed before the timeout")
            self.async_update_listeners()

        pending = PendingSetpoint(
            temperature,
            async_call_later(self.hass, SETPOINT_RECONCILE_TIMEOUT, expire),
            hold_until,
        )
        self._pending_setpoints[serial_number] = pending
        self.async_schedule_reconciliation()
        self.async_update_listeners()

    @callback
    def async_clear_pending_setpoint(self, serial_number: str) -> None:
        """Discard a confirmed or superseded request."""
        if pending := self._pending_setpoints.pop(serial_number, None):
            pending.cancel_timeout()
        self._cancel_idle_reconciliation()

    @callback
    def async_schedule_reconciliation(self) -> None:
        """Coalesce writes into a delayed account refresh, including uncertain writes."""
        if self._shutdown_requested:
            return
        if self.cooldown_remaining:
            self._cooldown_read_due = True
        if self._cancel_reconcile:
            self._cancel_reconcile()
        self._reconcile_is_initial = True
        self._cancel_reconcile = async_call_later(
            self.hass,
            min(86400, max(SETPOINT_RECONCILE_DELAY, self.cooldown_remaining)),
            self._async_reconcile,
        )

    @callback
    def _schedule_cooldown_read(self) -> None:
        """Keep one deferred read even if optimism expires before the quota."""
        remaining = self.cooldown_remaining
        self._cooldown_read_due = remaining > 0
        if not self._cooldown_read_due or self._shutdown_requested:
            return
        if self._cancel_reconcile:
            self._cancel_reconcile()
        self._reconcile_is_initial = False
        self._cancel_reconcile = async_call_later(
            self.hass,
            min(86400, max(SETPOINT_RECONCILE_RETRY, remaining)),
            self._async_reconcile,
        )

    async def _async_reconcile(self, _now: datetime) -> None:
        self._cancel_reconcile = None
        self._reconcile_is_initial = False
        if self._shutdown_requested:
            return
        if self.cooldown_remaining:
            self._schedule_cooldown_read()
            return
        self._cooldown_read_due = False
        # async_refresh serializes reads but bypasses the request debouncer's
        # ten-second cooldown, which would otherwise defer the two-second read.
        await self.async_refresh()
        if (
            (self._pending_setpoints or self._pending_modes or self._cooldown_read_due)
            and not self._shutdown_requested
            and (
                self.last_update_success
                or not isinstance(self.last_exception, ConfigEntryAuthFailed)
            )
            and self._cancel_reconcile is None
        ):
            self._cancel_reconcile = async_call_later(
                self.hass,
                min(86400, max(SETPOINT_RECONCILE_RETRY, self.cooldown_remaining)),
                self._async_reconcile,
            )

    @override
    async def async_shutdown(self) -> None:
        """Cancel reconciliation and independent optimism deadlines on unload."""
        if self._cancel_reconcile:
            self._cancel_reconcile()
            self._cancel_reconcile = None
        for pending in self._pending_setpoints.values():
            pending.cancel_timeout()
        self._pending_setpoints.clear()
        for pending_mode in self._pending_modes.values():
            pending_mode.cancel_timeout()
        self._pending_modes.clear()
        self._cooldown_read_due = False
        await super().async_shutdown()

    @override
    async def _async_update_data(self) -> dict[str, Thermostat]:
        generation = self._read_generation
        async with self._read_lock:
            if generation != self._read_generation:
                return self.data or {}
            result = await self._async_read_data()
            self._read_generation += 1
            return result

    async def _async_read_data(self) -> dict[str, Thermostat]:
        pending_at_start = self._pending_setpoints.copy()
        modes_at_start = self._pending_modes.copy()
        if self.cooldown_remaining:
            self._schedule_cooldown_read()
            raise UpdateFailed("NuHeat requests are throttled; retry after cooldown")
        try:
            thermostats = await self.api.list_thermostats()
        except NuHeatAuthError as err:
            raise ConfigEntryAuthFailed("NuHeat authorization expired") from err
        except NuHeatRateLimitError as err:
            self._schedule_cooldown_read()
            raise UpdateFailed(
                "NuHeat requests are throttled; retry after cooldown"
            ) from err
        except NuHeatPermissionError as err:
            raise UpdateFailed(
                "NuHeat application permission denied; verify application access"
            ) from err
        except (NuHeatApiError, NuHeatDataError) as err:
            raise UpdateFailed("Unable to update NuHeat thermostats") from err

        if self.cooldown_remaining:
            self._schedule_cooldown_read()
        elif self._cooldown_read_due:
            self._cooldown_read_due = False
            self._cancel_idle_reconciliation()

        fresh = {item.serial_number: item for item in thermostats}
        for serial_number, pending in pending_at_start.items():
            if (
                self._pending_setpoints.get(serial_number) is pending
                and (thermostat := fresh.get(serial_number)) is not None
                and thermostat.online
                and (
                    pending.hold_until is None
                    or (
                        thermostat.state is ThermostatState.TIMED_HOLD
                        and thermostat.hold_until == pending.hold_until
                    )
                )
                and thermostat.target_temperature is not None
                and isclose(
                    thermostat.target_temperature, pending.temperature, abs_tol=0.01
                )
            ):
                self.async_clear_pending_setpoint(serial_number)
        for serial_number, pending_mode in modes_at_start.items():
            if (
                self._pending_modes.get(serial_number) is pending_mode
                and (thermostat := fresh.get(serial_number)) is not None
                and thermostat.online
                and thermostat.state is pending_mode.state
            ):
                self.async_clear_pending_mode(serial_number, confirmed=True)
        self._present_serials = set(fresh)
        # Retain previously discovered devices when an otherwise successful
        # account response temporarily omits one of them.
        return {**(self.data or {}), **fresh}

    def is_thermostat_available(self, serial_number: str) -> bool:
        """Return cloud and device availability without removing entities."""
        thermostat = (self.data or {}).get(serial_number)
        return (
            self.last_update_success
            and serial_number in self._present_serials
            and thermostat is not None
            and thermostat.online
        )
