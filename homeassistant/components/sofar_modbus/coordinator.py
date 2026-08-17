"""DataUpdateCoordinator wrapping SofarInverter.async_update(), with retry-before-fail and tiered fast/slow polling."""

from collections import deque
from datetime import datetime, timedelta
import logging
from typing import Any, TypeVar, cast, override

from modbus_connection import (
    ModbusConnection,
    ModbusConnectionError,
    ModbusError,
    ModbusTimeoutError,
)
from sofar_modbus.model import SofarComponentBase, UpdateReport
from sofar_modbus.modern.device import SofarInverter

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

_TIMEOUT_DISCONNECT_THRESHOLD = 3
_SLOW_TIER_EVERY_N_CYCLES = 12  # ~60s at the 5s base scan interval
_HEALTH_WINDOW = 60  # ~5min at the 5s base scan interval

type SofarConfigEntry = ConfigEntry[SofarDataUpdateCoordinator]

_T = TypeVar("_T")

# Components polled every cycle (vs. the slow tier). Hand-maintained instead
# of derived from the sensor platform so the coordinator has no dependency
# on any platform module.
_VOLATILE_COMPONENTS: frozenset[str] = frozenset(
    {
        "battery_1_2",
        "battery_3_8",
        "battery_totals",
        "grid",
        "offgrid",
        "offgrid_single_phase",
        "offgrid_three_phase",
        "pv_1_2",
        "pv_3",
        "pv_4",
        "pv_5_6",
        "pv_7_8",
        "pv_9_10",
        "state",
    }
)


class SofarDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Polls one Sofar inverter's components, tiered by how often they change."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SofarConfigEntry,
        connection: ModbusConnection,
        device: SofarInverter,
        scan_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.connection = connection
        self.device = device
        self._consecutive_timeouts = 0
        self._consecutive_failures: dict[str, int] = {}
        self._poll_outcomes: deque[bool] = deque(maxlen=_HEALTH_WINDOW)
        self.last_error: str | None = None
        self.last_error_time: datetime | None = None
        self._cycle = 0
        self._fast: dict[str, SofarComponentBase] | None = None
        self._slow: dict[str, SofarComponentBase] | None = None
        if self.device.polled_components is not None:
            self._fast = {
                name: getattr(self.device, name)
                for name in self.device.polled_components
                if name in _VOLATILE_COMPONENTS
            }
            self._slow = {
                name: getattr(self.device, name)
                for name in self.device.polled_components
                if name not in _VOLATILE_COMPONENTS
            }
        self._force_slow_tier = True
        self.pending: dict[str, Any] = {}

    @property
    def success_rate(self) -> float | None:
        """Percent of the last `_HEALTH_WINDOW` poll cycles with no failed component.

        None until the first poll lands. Whole-device, not per-component: a
        cycle only counts as a failure if a component's poll still shows up
        in the returned report.failed after _retry_failed's one retry.
        """
        if not self._poll_outcomes:
            return None
        return round(100 * sum(self._poll_outcomes) / len(self._poll_outcomes), 1)

    def _record_poll_outcome(self, success: bool, error: ModbusError | None) -> None:
        self._poll_outcomes.append(success)
        if error is not None:
            self.last_error = f"{type(error).__name__}: {error}"
            self.last_error_time = dt_util.utcnow()

    @property
    def served_components(self) -> frozenset[str]:
        """All component names served by this inverter type."""
        if self.device.polled_components is not None:
            return frozenset(self.device.polled_components)
        if self.data is not None:
            return frozenset(self.data.updated | set(self.data.failed))
        return frozenset()

    def pending_or_live(self, key: str, live_value: _T) -> _T:
        """What a staged number/select/switch entity should show right now.

        The value the user last set this session, if any and if it hasn't
        been committed yet — otherwise whatever the last successful poll
        read. In-memory only: these registers are volatile on the device
        itself (no flash wear from writing them often), so there's nothing
        to persist across a restart either.
        """
        return cast("_T", self.pending.get(key, live_value))

    @override
    async def async_request_refresh(self) -> None:
        """Request a refresh, polling the slow tier too regardless of cadence."""
        self._force_slow_tier = True
        await super().async_request_refresh()

    @override
    async def async_refresh(self) -> None:
        """Refresh data immediately, polling the slow tier too regardless of cadence."""
        self._force_slow_tier = True
        await super().async_refresh()

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            if self._fast is None:
                report = await self._async_first_poll()
            else:
                report = await self._poll(self._components_due())
            self._cycle += 1
            report = await self._retry_failed(report)
            if not report.updated:
                errors = list(report.failed.values())
                self._record_poll_outcome(False, errors[0] if errors else None)
                if not errors:
                    raise UpdateFailed(f"{self.name}: no component answered")
                cause = (
                    errors[0]
                    if len(errors) == 1
                    else ExceptionGroup("all components failed to refresh", errors)
                )
                raise UpdateFailed(
                    f"{self.name}: no component answered: {errors[0]}"
                ) from cause
        except ModbusTimeoutError as err:
            self._consecutive_timeouts += 1
            if self._consecutive_timeouts >= _TIMEOUT_DISCONNECT_THRESHOLD:
                _LOGGER.debug(
                    "%s: %d consecutive timed-out polls, recycling the connection",
                    self.name,
                    self._consecutive_timeouts,
                )
                await self.connection.disconnect()
                self._consecutive_timeouts = 0
            self._record_poll_outcome(False, err)
            raise UpdateFailed(str(err)) from err
        except ModbusError as err:
            # ModbusConnectionError (dead link) reaches here,
            # while per-block failures once alive are contained in UpdateReport.failed.
            self._record_poll_outcome(False, err)
            raise UpdateFailed(str(err)) from err
        else:
            self._consecutive_timeouts = 0
            self._record_poll_outcome(
                not report.failed, next(iter(report.failed.values()), None)
            )
            return report

    async def _async_first_poll(self) -> UpdateReport:
        """Settle the fast/slow tier split from the inverter's served components.

        Also refreshes the fast tier on startup.
        """
        if self._fast is None:
            if self.device.polled_components is None:
                await self.device.async_setup()
            if not self.device.inverter_type:
                return UpdateReport(updated={"identity"}, failed={})
            polled = self.device.polled_components or ()
            self._fast = {
                name: getattr(self.device, name)
                for name in polled
                if name in _VOLATILE_COMPONENTS
            }
            self._slow = {
                name: getattr(self.device, name)
                for name in polled
                if name not in _VOLATILE_COMPONENTS
            }
        components_to_poll = self._fast or dict(self._slow or {})
        return await self._poll(components_to_poll)

    def _components_due(self) -> dict[str, SofarComponentBase]:
        assert self._fast is not None
        components = dict(self._fast)
        if self._force_slow_tier or (
            self._cycle > 0 and self._cycle % _SLOW_TIER_EVERY_N_CYCLES == 0
        ):
            assert self._slow is not None
            components.update(self._slow)
            self._force_slow_tier = False
        return components

    async def _poll(
        self,
        components: dict[str, SofarComponentBase],
        allow_fatal_timeout: bool = True,
    ) -> UpdateReport:
        """One attempt at each of ``components``, no retry."""
        updated: set[str] = set()
        failed: dict[str, ModbusError] = {}
        for name, component in components.items():
            try:
                await component.async_update()
            except ModbusConnectionError:
                raise
            except ModbusTimeoutError as err:
                if allow_fatal_timeout and not updated and not failed:
                    raise  # nothing answered at all: assume the rest time out too
                failed[name] = err
            except ModbusError as err:
                failed[name] = err
            else:
                updated.add(name)
        return UpdateReport(updated, failed)

    async def _retry_failed(self, report: UpdateReport) -> UpdateReport:
        """Give every failed component one more try before accepting the failure.

        Skipped when nothing answered on the first pass (e.g. an all-timeout
        outage) to avoid doubling the timeout latency when the link is down.
        """
        if report.failed and report.updated:
            retry = await self._poll(
                {name: getattr(self.device, name) for name in report.failed},
                allow_fatal_timeout=False,
            )
            report = UpdateReport(report.updated | retry.updated, retry.failed)

        for name, cause in report.failed.items():
            prev = self._consecutive_failures.get(name, 0)
            self._consecutive_failures[name] = prev + 1
            if prev == 0:
                _LOGGER.warning(
                    "%s: %s failed to refresh and is keeping its previous values: %s",
                    self.name,
                    name,
                    cause,
                )
        for name in report.updated:
            self._consecutive_failures.pop(name, None)

        return report
