"""DataUpdateCoordinator wrapping SofarInverter's readings/settings polls, with retry-before-fail and tiered cadence."""

from collections import deque
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, TypeVar, cast, override

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
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_MODBUS_ADDR,
    CONF_READ_EPS,
    DEFAULT_MODBUS_ADDR,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

_TIMEOUT_DISCONNECT_THRESHOLD = 3
_SLOW_TIER_EVERY_N_CYCLES = 12  # ~60s at the 5s base scan interval
_HEALTH_WINDOW = 60  # ~5min at the 5s base scan interval

type SofarConfigEntry = ConfigEntry[SofarDataUpdateCoordinator]

_T = TypeVar("_T")


class SofarDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Polls one Sofar inverter's components, tiered by how often they change."""

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
        self.config_entry: SofarConfigEntry = entry
        self.connection = connection
        self.device: SofarInverter
        self._consecutive_timeouts = 0
        self._consecutive_failures: dict[str, int] = {}
        self._poll_outcomes: deque[bool] = deque(maxlen=_HEALTH_WINDOW)
        self.last_error: str | None = None
        self.last_error_time: datetime | None = None
        self._cycle = 0
        self._force_slow_tier = True
        self.pending: dict[str, Any] = {}

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator before the first refresh."""
        serial = self.config_entry.unique_id
        if TYPE_CHECKING:
            assert serial is not None
        inverter_type, model = identify(serial)
        if not inverter_type:
            raise ConfigEntryError(
                f"Unrecognized Sofar inverter model for {self.config_entry.title}"
            )
        self.device = SofarInverter(
            self.connection.for_unit(
                int(self.config_entry.data.get(CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR))
            ),
            serial_number=serial,
            model=model,
            inverter_type=inverter_type,
            read_eps=self.config_entry.data.get(CONF_READ_EPS, False),
        )

    @property
    def success_rate(self) -> float | None:
        """Percent of the last _HEALTH_WINDOW cycles with no failed component. Whole-device, not per-component; None until the first poll lands."""
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
        """All component names served by this inverter type. Empty until the first refresh lands."""
        if self.data is not None:
            return frozenset(self.data.updated | set(self.data.failed))
        return frozenset()

    def pending_or_live(self, key: str, live_value: _T) -> _T:
        """What a staged number/select/switch entity should show: the pending value if set this session, else the last live read. In-memory only — these registers are volatile on the device anyway, so there's nothing to persist."""
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

    async def _retry_failed(self, report: UpdateReport) -> UpdateReport:
        """Give every failed component one more try; skipped entirely if nothing answered, to avoid doubling the timeout latency during an outage."""
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
