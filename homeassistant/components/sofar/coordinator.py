"""Wraps SofarInverter's polls: retry-before-fail, tiered cadence."""

from collections import deque
from datetime import datetime, timedelta
import logging
from typing import override

from modbus_connection import (
    ModbusConnection,
    ModbusConnectionError,
    ModbusError,
    ModbusTimeoutError,
)
from sofar_modbus.model import UpdateReport
from sofar_modbus.modern.device import SofarInverter, identify

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_READ_EPS, CONF_UNIT_ID, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

_TIMEOUT_DISCONNECT_THRESHOLD = 3
_SLOW_TIER_EVERY_N_CYCLES = 12  # ~60s at the 5s base scan interval
_HEALTH_WINDOW = 60  # ~5min at the 5s base scan interval

type SofarConfigEntry = ConfigEntry[SofarDataUpdateCoordinator]


class SofarDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Polls one Sofar inverter's components, tiered by how often they change."""

    config_entry: SofarConfigEntry
    device: SofarInverter

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SofarConfigEntry,
        connection: ModbusConnection,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.connection = connection
        self._consecutive_timeouts = 0
        self._consecutive_failures: dict[str, int] = {}
        self._poll_outcomes: deque[bool] = deque(maxlen=_HEALTH_WINDOW)
        self.last_error: str | None = None
        self.last_error_time: datetime | None = None
        self._cycle = 0
        self._force_slow_tier = True

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator before the first refresh."""
        serial = self.config_entry.unique_id
        assert serial is not None
        # async_setup_entry already checked identify(serial) is recognized.
        inverter_type, model = identify(serial)
        self.device = SofarInverter(
            self.connection.for_unit(self.config_entry.data[CONF_UNIT_ID]),
            serial_number=serial,
            model=model,
            inverter_type=inverter_type,
            read_eps=self.config_entry.data.get(CONF_READ_EPS, False),
        )

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
        """Component names this inverter type serves; empty before first refresh."""
        if self.data is not None:
            return frozenset(self.data.updated | set(self.data.failed))
        return frozenset()

    @override
    async def async_request_refresh(self) -> None:
        """Request a refresh, polling the slow tier too regardless of cadence."""
        self._force_slow_tier = True
        await super().async_request_refresh()

    @override
    async def async_refresh(self) -> None:
        """Refresh immediately, polling the slow tier regardless of cadence."""
        self._force_slow_tier = True
        await super().async_refresh()

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self.device.async_update_readings()
            self._cycle += 1
            if self._force_slow_tier or (
                self._cycle > 0 and self._cycle % _SLOW_TIER_EVERY_N_CYCLES == 0
            ):
                self._force_slow_tier = False
                settings_report = await self.device.async_update_settings()
                report = UpdateReport(
                    report.updated | settings_report.updated,
                    {**report.failed, **settings_report.failed},
                )
            report = await self._retry_failed(report)
            if not report.updated:
                errors = list(report.failed.values())
                self._record_poll_outcome(False, errors[0] if errors else None)
                if not errors:
                    raise UpdateFailed(f"{self.name}: no component answered")
                raise UpdateFailed(
                    f"{self.name}: no component answered"
                ) from ExceptionGroup("all components failed to refresh", errors)
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
            # ModbusConnectionError (dead link) reaches here; per-block failures
            # once alive land in UpdateReport.failed instead.
            self._record_poll_outcome(False, err)
            raise UpdateFailed(str(err)) from err
        else:
            self._consecutive_timeouts = 0
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
