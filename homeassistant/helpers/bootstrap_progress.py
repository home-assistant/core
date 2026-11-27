"""Watch the setups that are pending during bootstrap and report the progress."""

import asyncio
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from functools import partial
import logging
from time import monotonic
from typing import TypedDict

from homeassistant import core
from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.setup import _async_get_setup_results
from homeassistant.util.hass_dict import HassKey

from . import singleton

_LOGGER = logging.getLogger(__name__)

LOG_SLOW_STARTUP_INTERVAL = 60
SLOW_STARTUP_CHECK_INTERVAL = 1

_DATA_BOOTSTRAP_PROGRESS: HassKey[_BootstrapProgressData] = HassKey(
    "bootstrap_progress"
)


class BootstrapPhase(StrEnum):
    """Startup phases reported in the bootstrap progress."""

    PREPARING = "preparing"
    """Resolving the domains to set up; the total is not known yet."""
    SETUP = "setup"
    """Setting up the integrations of a bootstrap stage."""
    WRAP_UP = "wrap_up"
    """Waiting for the tasks created during integration setup."""
    STARTING = "starting"
    """CoreState.starting: start event listeners and startup jobs."""
    RUNNING = "running"
    """CoreState.running: startup is finished."""


class BootstrapIntegrationsProgress(TypedDict):
    """Integrations whose setup attempt finished during bootstrap."""

    total: int | None
    done: int
    failed: list[str]


class BootstrapProgress(TypedDict):
    """Startup progress sent by bootstrap."""

    phase: BootstrapPhase
    elapsed: float
    integrations: BootstrapIntegrationsProgress
    active: dict[str, float]


@dataclass(slots=True)
class _BootstrapProgressData:
    """Startup progress listeners and the source of the current progress."""

    listeners: list[Callable[[BootstrapProgress], None]] = field(default_factory=list)
    source: Callable[[], BootstrapProgress] | None = None


@singleton.singleton(_DATA_BOOTSTRAP_PROGRESS)
def _bootstrap_progress(hass: core.HomeAssistant) -> _BootstrapProgressData:
    """Return the startup progress listeners and source."""
    return _BootstrapProgressData()


@callback
def async_subscribe_bootstrap_progress(
    hass: HomeAssistant, listener: Callable[[BootstrapProgress], None]
) -> CALLBACK_TYPE:
    """Subscribe to the startup progress.

    Once bootstrap has started, the listener is called with the current
    progress right away.
    """
    data = _bootstrap_progress(hass)
    data.listeners.append(listener)
    if data.source is not None:
        _send_bootstrap_progress(listener, data.source())
    return partial(data.listeners.remove, listener)


@callback
def _async_set_bootstrap_progress_source(
    hass: HomeAssistant, source: Callable[[], BootstrapProgress]
) -> None:
    """Set the source of the current progress and send it to the listeners."""
    _bootstrap_progress(hass).source = source
    _async_dispatch_bootstrap_progress(hass)


@callback
def _async_dispatch_bootstrap_progress(hass: HomeAssistant) -> None:
    """Send the current progress to the listeners."""
    data = _bootstrap_progress(hass)
    # The progress is only built when someone listens.
    if not data.listeners or data.source is None:
        return
    progress = data.source()
    # Listeners can unsubscribe while the progress is sent.
    for listener in data.listeners.copy():
        _send_bootstrap_progress(listener, progress)


def _send_bootstrap_progress(
    listener: Callable[[BootstrapProgress], None], progress: BootstrapProgress
) -> None:
    """Send the progress to a listener, logging its errors."""
    try:
        listener(progress)
    except Exception:
        _LOGGER.exception("Error sending bootstrap progress to %s", listener)


class WatchPendingSetups:
    """Periodic log and dispatch of setups that are pending."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        setup_started: dict[tuple[str, str | None], float],
        started: float,
    ) -> None:
        """Initialize the WatchPendingSetups class."""
        self._hass = hass
        self._setup_started = setup_started
        self._duration_count = 0
        self._handle: asyncio.TimerHandle | None = None
        self._loop = hass.loop
        self._started = started
        self._phase = BootstrapPhase.PREPARING
        self._planned_domains: set[str] | None = None
        self._progress_handle: asyncio.TimerHandle | None = None

    def _async_watch(self) -> None:
        """Periodic log of setups that are pending."""
        now = monotonic()
        self._duration_count += SLOW_STARTUP_CHECK_INTERVAL

        remaining_with_setup_started: defaultdict[str, float] = defaultdict(float)
        for integration_group, start_time in self._setup_started.items():
            domain, _ = integration_group
            remaining_with_setup_started[domain] += now - start_time

        if remaining_with_setup_started:
            _LOGGER.debug("Integration remaining: %s", remaining_with_setup_started)
        elif waiting_tasks := self._hass._active_tasks:  # noqa: SLF001
            _LOGGER.debug("Waiting on tasks: %s", waiting_tasks)
        _async_dispatch_bootstrap_progress(self._hass)
        if (
            self._setup_started
            and self._duration_count % LOG_SLOW_STARTUP_INTERVAL == 0
        ):
            # We log every LOG_SLOW_STARTUP_INTERVAL until all integrations are done
            # once we take over LOG_SLOW_STARTUP_INTERVAL (60s) to start up
            _LOGGER.warning(
                "Waiting for integrations to complete setup: %s",
                self._setup_started,
            )

        _LOGGER.debug("Running timeout Zones: %s", self._hass.timeout.zones)
        self._async_schedule_next()

    @core.callback
    def async_set_planned_domains(self, domains: set[str]) -> None:
        """Set the domains bootstrap will set up, including dependencies."""
        self._planned_domains = domains

    @core.callback
    def async_set_phase(self, phase: BootstrapPhase) -> None:
        """Set the current phase and dispatch the progress."""
        self._phase = phase
        if phase is not BootstrapPhase.RUNNING:
            _async_dispatch_bootstrap_progress(self._hass)
            return
        # Later subscribers get the summary from when Core started running.
        summary = self._async_progress()
        _async_set_bootstrap_progress_source(self._hass, lambda: summary)

    @core.callback
    def _async_core_state_changed(self, phase: BootstrapPhase, _: core.Event) -> None:
        """Dispatch the progress when the core state changes after bootstrap."""
        self.async_set_phase(phase)
        if phase is BootstrapPhase.STARTING:
            self._async_schedule_progress()
        elif self._progress_handle:
            self._progress_handle.cancel()
            self._progress_handle = None

    def _async_schedule_progress(self) -> None:
        """Schedule the next progress dispatch while Core is starting."""
        self._progress_handle = self._loop.call_later(
            SLOW_STARTUP_CHECK_INTERVAL, self._async_progress_tick
        )

    def _async_progress_tick(self) -> None:
        """Dispatch the progress while Core is starting."""
        if self._hass.state is not core.CoreState.starting:
            self._progress_handle = None
            return
        _async_dispatch_bootstrap_progress(self._hass)
        self._async_schedule_progress()

    def _async_progress(self) -> BootstrapProgress:
        """Return the startup progress.

        Progress is counted in integrations (domains) whose setup attempt
        finished, out of those bootstrap scheduled. It does not measure time.
        """
        now = monotonic()
        active: dict[str, float] = {}
        # The running message is kept for late subscribers, so it lists no setups.
        if self._phase is not BootstrapPhase.RUNNING:
            for (domain, _), start_time in self._setup_started.items():
                active[domain] = max(active.get(domain, 0.0), now - start_time)

        integrations = BootstrapIntegrationsProgress(total=None, done=0, failed=[])
        if (planned := self._planned_domains) is not None:
            results = _async_get_setup_results(self._hass, planned)
            integrations["total"] = len(planned)
            integrations["done"] = sum(
                result is not None for result in results.values()
            )
            integrations["failed"] = sorted(
                domain for domain, result in results.items() if result is False
            )

        return BootstrapProgress(
            phase=self._phase,
            elapsed=now - self._started,
            integrations=integrations,
            active=active,
        )

    def _async_schedule_next(self) -> None:
        """Schedule the next call."""
        self._handle = self._loop.call_later(
            SLOW_STARTUP_CHECK_INTERVAL, self._async_watch
        )

    def async_start(self) -> None:
        """Start watching."""
        _async_set_bootstrap_progress_source(self._hass, self._async_progress)
        self._async_schedule_next()

    def async_stop(self) -> None:
        """Stop watching pending setups.

        The progress is still dispatched on the start and started events.
        """
        _async_dispatch_bootstrap_progress(self._hass)
        # Progress keeps the wrap up phase until the core state changes.
        for event_type, phase in (
            (EVENT_HOMEASSISTANT_START, BootstrapPhase.STARTING),
            (EVENT_HOMEASSISTANT_STARTED, BootstrapPhase.RUNNING),
        ):
            self._hass.bus.async_listen_once(
                event_type, partial(self._async_core_state_changed, phase)
            )
        if self._handle:
            self._handle.cancel()
            self._handle = None
