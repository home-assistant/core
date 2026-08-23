"""Runs one of SofarInverter's update methods on its own interval."""

from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import override

from modbus_connection import ModbusConnectionError, ModbusError
from sofar_modbus.model import UpdateReport
from sofar_modbus.modern.device import SofarInverter

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

_HEALTH_WINDOW = 60  # ~5min at the 5s readings interval


class SofarDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Runs one of SofarInverter's update methods on its own interval."""

    config_entry: SofarConfigEntry
    device: SofarInverter

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SofarConfigEntry,
        device: SofarInverter,
        poll: Callable[[], Awaitable[UpdateReport]],
        interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=interval,
        )
        self.device = device
        self._poll = poll
        self._consecutive_failures: dict[str, int] = {}
        self._poll_outcomes: deque[bool] = deque(maxlen=_HEALTH_WINDOW)
        self.last_error: str | None = None
        self.last_error_time: datetime | None = None

    @property
    def success_rate(self) -> float | None:
        """Success rate over recent cycles — whole-device, not per-component."""
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
        """Component names this poll serves; empty before first refresh."""
        if self.data is not None:
            return frozenset(self.data.updated | set(self.data.failed))
        return frozenset()

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self._poll()
            report = await self._retry_failed(report)
            if not report.updated:
                errors = list(report.failed.values())
                self._record_poll_outcome(False, errors[0] if errors else None)
                if not errors:
                    raise UpdateFailed(f"{self.name}: no component answered")
                raise UpdateFailed(
                    f"{self.name}: no component answered"
                ) from ExceptionGroup("all components failed to refresh", errors)
        except ModbusError as err:
            # ModbusConnectionError (dead link) and ModbusTimeoutError reach
            # here; per-block failures once alive land in report.failed instead.
            self._record_poll_outcome(False, err)
            raise UpdateFailed(str(err)) from err
        else:
            self._record_poll_outcome(
                not report.failed, next(iter(report.failed.values()), None)
            )
            return report

    async def _retry_failed(self, report: UpdateReport) -> UpdateReport:
        """Retry failures once; skip if none answered, to avoid doubling timeout."""
        if report.failed and report.updated:
            updated: set[str] = set()
            failed: dict[str, ModbusError] = {}
            for name in report.failed:
                try:
                    await getattr(self.device, name).async_update()
                except ModbusConnectionError:
                    raise
                except ModbusError as err:
                    failed[name] = err
                else:
                    updated.add(name)
            report = UpdateReport(report.updated | updated, failed)

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


@dataclass
class SofarRuntimeData:
    """Both coordinators, tiered by how often their components change."""

    readings: SofarDataUpdateCoordinator
    settings: SofarDataUpdateCoordinator

    @property
    def served_components(self) -> frozenset[str]:
        """Component names either poll serves; empty before first refresh."""
        return self.readings.served_components | self.settings.served_components

    def coordinator_for(self, component: str) -> SofarDataUpdateCoordinator:
        """Which coordinator owns a given component's data."""
        if component in self.readings.served_components:
            return self.readings
        return self.settings


type SofarConfigEntry = ConfigEntry[SofarRuntimeData]
