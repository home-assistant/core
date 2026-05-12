"""Ohme coordinators."""

from abc import abstractmethod
import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, cast

from ohme import ApiException, ChargerStatus, OhmeApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .history import async_sync_repair_energy_history, async_sync_session_energy_history

_LOGGER = logging.getLogger(__name__)

DAILY_REPAIR_INTERVAL = timedelta(days=1)
FINALIZED_SYNC_RETRY_DELAY = timedelta(minutes=15)


def _client_session_timestamp(client: OhmeApiClient, attribute: str) -> datetime | None:
    """Return a typed optional session timestamp from the Ohme client."""
    return cast(datetime | None, getattr(client, attribute, None))


@dataclass(slots=True)
class HistorySyncRequest:
    """Describe a queued history sync request."""

    reason: str
    session_start: datetime | None = None


@dataclass()
class OhmeRuntimeData:
    """Dataclass to hold ohme coordinators."""

    charge_session_coordinator: OhmeChargeSessionCoordinator
    device_info_coordinator: OhmeDeviceInfoCoordinator


type OhmeConfigEntry = ConfigEntry[OhmeRuntimeData]


class OhmeBaseCoordinator(DataUpdateCoordinator[Any]):
    """Base for all Ohme coordinators."""

    config_entry: OhmeConfigEntry
    client: OhmeApiClient
    _default_update_interval: timedelta | None = timedelta(minutes=1)
    coordinator_name: str = ""

    def __init__(
        self, hass: HomeAssistant, config_entry: OhmeConfigEntry, client: OhmeApiClient
    ) -> None:
        """Initialise coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="",
            update_interval=self._default_update_interval,
        )

        self.name = f"Ohme {self.coordinator_name}"
        self.client = client

    async def _async_update_data(self) -> Any:
        """Fetch data from API endpoint."""
        try:
            return await self._internal_update_data()
        except ApiException as e:
            raise UpdateFailed(
                translation_key="api_failed", translation_domain=DOMAIN
            ) from e

    @abstractmethod
    async def _internal_update_data(self) -> Any:
        """Update coordinator data."""


class OhmeChargeSessionCoordinator(OhmeBaseCoordinator):
    """Coordinator to pull live charge-session updates from the API."""

    coordinator_name = "Charge Sessions"
    _default_update_interval = timedelta(seconds=30)

    def __init__(
        self, hass: HomeAssistant, config_entry: OhmeConfigEntry, client: OhmeApiClient
    ) -> None:
        """Initialize the charge-session coordinator."""
        super().__init__(hass, config_entry, client)
        self._history_sync_enabled = False
        self._history_sync_task: asyncio.Task[None] | None = None
        self._pending_history_sync: HistorySyncRequest | None = None
        self._remove_daily_repair_listener: Callable[[], None] | None = None
        self._remove_delayed_retry_listener: Callable[[], None] | None = None
        self._tracked_session_start: datetime | None = None
        self._last_status: ChargerStatus | None = None
        self._completed_session_marker: tuple[datetime, datetime] | None = None

    def enable_history_sync(self) -> None:
        """Enable automatic history-sync orchestration."""
        if self._history_sync_enabled:
            return

        self._history_sync_enabled = True
        _LOGGER.debug("Enabled Ohme history sync orchestration for %s", self.name)
        self._remove_daily_repair_listener = async_track_time_interval(
            self.hass,
            self._async_daily_repair_listener,
            DAILY_REPAIR_INTERVAL,
        )

    def disable_history_sync(self) -> None:
        """Disable automatic history-sync orchestration."""
        self._history_sync_enabled = False
        self._pending_history_sync = None
        self._tracked_session_start = None
        _LOGGER.debug("Disabled Ohme history sync orchestration for %s", self.name)
        if self._remove_daily_repair_listener is not None:
            self._remove_daily_repair_listener()
            self._remove_daily_repair_listener = None
        self._cancel_delayed_retry()

    def seed_history_sync_state(self) -> None:
        """Seed transition tracking from the coordinator's current client state."""
        status = self.client.status
        session_start = _client_session_timestamp(self.client, "session_start")
        session_finish = _client_session_timestamp(self.client, "session_finish")

        self._last_status = status
        if session_start is not None and session_finish is not None:
            self._completed_session_marker = (session_start, session_finish)
            self._tracked_session_start = None
            return

        self._completed_session_marker = None
        self._tracked_session_start = (
            session_start if session_start is not None and session_finish is None else None
        )
        _LOGGER.debug(
            "Seeded Ohme history sync state: status=%s session_start=%s session_finish=%s tracked_session_start=%s completed_marker=%s",
            status,
            session_start,
            session_finish,
            self._tracked_session_start,
            self._completed_session_marker,
        )

    async def _async_daily_repair_listener(self, _: datetime) -> None:
        """Run the bounded daily repair sync."""
        self._queue_history_sync(HistorySyncRequest(reason="daily_repair"))

    def _merge_history_sync_requests(
        self,
        current: HistorySyncRequest | None,
        new: HistorySyncRequest,
    ) -> HistorySyncRequest:
        """Merge overlapping history sync requests conservatively."""
        if current is None:
            return new

        if current.session_start is None or new.session_start is None:
            return current if current.session_start is None else new

        return new if new.session_start < current.session_start else current

    def _queue_history_sync(self, request: HistorySyncRequest) -> None:
        """Schedule a non-overlapping history sync request."""
        if not self._history_sync_enabled:
            return

        if self._history_sync_task and not self._history_sync_task.done():
            self._pending_history_sync = self._merge_history_sync_requests(
                self._pending_history_sync, request
            )
            _LOGGER.debug(
                "Merged pending Ohme history sync request: reason=%s session_start=%s",
                self._pending_history_sync.reason,
                self._pending_history_sync.session_start,
            )
            return

        _LOGGER.debug(
            "Queueing Ohme history sync: reason=%s session_start=%s",
            request.reason,
            request.session_start,
        )
        self._history_sync_task = self.config_entry.async_create_background_task(
            self.hass,
            self._async_run_history_sync(request),
            f"Ohme history sync ({request.reason})",
        )

    async def _async_run_history_sync(self, request: HistorySyncRequest) -> None:
        """Run a history sync request and schedule any queued follow-up."""
        try:
            if request.session_start is None:
                result = await async_sync_repair_energy_history(
                    self.hass,
                    self.config_entry,
                    reason=request.reason,
                )
            else:
                result = await async_sync_session_energy_history(
                    self.hass,
                    self.config_entry,
                    session_start=request.session_start,
                    reason=request.reason,
                )
        except Exception:
            _LOGGER.exception("Failed Ohme history sync (%s)", request.reason)
        else:
            _LOGGER.debug("Completed Ohme history sync: %s", result)
        finally:
            self._history_sync_task = None
            pending_request = self._pending_history_sync
            self._pending_history_sync = None
            if pending_request is not None and self._history_sync_enabled:
                self._queue_history_sync(pending_request)

    def _schedule_delayed_retry(self, session_start: datetime | None) -> None:
        """Schedule one delayed sync retry for late Ohme finalization."""
        self._cancel_delayed_retry()
        _LOGGER.debug(
            "Scheduling delayed Ohme history sync retry: session_start=%s delay=%s",
            session_start,
            FINALIZED_SYNC_RETRY_DELAY,
        )

        @callback
        def _retry(_: datetime) -> None:
            self._remove_delayed_retry_listener = None
            _LOGGER.debug(
                "Running delayed Ohme history sync retry: session_start=%s",
                session_start,
            )
            self._queue_history_sync(
                HistorySyncRequest(
                    reason="session_finalized_retry",
                    session_start=session_start,
                )
            )

        self._remove_delayed_retry_listener = async_call_later(
            self.hass,
            FINALIZED_SYNC_RETRY_DELAY,
            _retry,
        )

    def _cancel_delayed_retry(self) -> None:
        """Cancel any pending delayed retry."""
        if self._remove_delayed_retry_listener is not None:
            self._remove_delayed_retry_listener()
            self._remove_delayed_retry_listener = None

    def _handle_charge_session_transition(self) -> None:
        """Detect finalized-session boundaries and trigger bounded history syncs."""
        status = self.client.status
        session_start = _client_session_timestamp(self.client, "session_start")
        session_finish = _client_session_timestamp(self.client, "session_finish")
        was_active_status = self._last_status in {
            ChargerStatus.CHARGING,
            ChargerStatus.PLUGGED_IN,
            ChargerStatus.PAUSED,
        }

        if session_start is not None and session_finish is None:
            self._tracked_session_start = session_start

        if session_start is not None and session_finish is not None:
            completed_marker = (session_start, session_finish)
            if completed_marker != self._completed_session_marker:
                self._completed_session_marker = completed_marker
                self._tracked_session_start = None
                _LOGGER.debug(
                    "Detected finalized Ohme session marker: status=%s session_start=%s session_finish=%s",
                    status,
                    session_start,
                    session_finish,
                )
                self._queue_history_sync(
                    HistorySyncRequest(
                        reason="session_finalized",
                        session_start=session_start,
                    )
                )
                self._schedule_delayed_retry(session_start)
        elif (
            self._tracked_session_start is not None
            and self._last_status is not None
            and self._last_status is not ChargerStatus.UNPLUGGED
            and status is ChargerStatus.UNPLUGGED
        ):
            session_anchor = self._tracked_session_start
            self._tracked_session_start = None
            _LOGGER.debug(
                "Detected Ohme unplug after tracked session: last_status=%s session_start=%s",
                self._last_status,
                session_anchor,
            )
            self._queue_history_sync(
                HistorySyncRequest(
                    reason="session_unplugged",
                    session_start=session_anchor,
                )
            )
            self._schedule_delayed_retry(session_anchor)
        elif was_active_status and status is ChargerStatus.FINISHED:
            _LOGGER.debug(
                "Observed Ohme finished state without session_finish; waiting for disconnect before syncing"
            )
        # A real 2026-04-05 Ohme probe stayed FINISHED_CHARGE for ~87 minutes
        # with stale summary/session totals; the meaningful summary update only
        # appeared once the charger transitioned to DISCONNECTED / unplugged.
        elif was_active_status and status is ChargerStatus.UNPLUGGED:
            _LOGGER.debug(
                "Detected Ohme unplug without usable session markers; running bounded repair sync"
            )
            self._queue_history_sync(
                HistorySyncRequest(reason="session_marker_missing")
            )
            self._schedule_delayed_retry(None)
        elif status is ChargerStatus.UNPLUGGED and session_start is None:
            self._tracked_session_start = None

        self._last_status = status

    async def _internal_update_data(self) -> None:
        """Fetch data from the live charge-session endpoint."""
        await self.client.async_get_charge_session()

        if self._history_sync_enabled:
            self._handle_charge_session_transition()


class OhmeDeviceInfoCoordinator(OhmeBaseCoordinator):
    """Coordinator to pull device info and charger settings from the API."""

    coordinator_name = "Device Info"
    _default_update_interval = timedelta(minutes=30)

    async def _internal_update_data(self) -> None:
        """Fetch data from API endpoint."""
        await self.client.async_update_device_info()
