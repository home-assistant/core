"""Dispatch coordinator for the Noonlight integration.

Owns the entire dispatch state machine for a single config entry:

* the ``idle → pending → dispatched → idle`` lifecycle,
* the cancelable entry-delay timer,
* the per-service de-dup window,
* the append-only audit log, and
* persistence of dedupe timestamps + last state across restarts.

Entities and services never touch state directly; they call the public
``async_dispatch`` / ``async_cancel`` / ``async_test_dispatch`` methods and read
``coordinator.data``.
"""

from datetime import timedelta
import json
import logging
import os
from typing import Any

from noonlight_dispatch import (
    SANDBOX_BASE_URL,
    NoonlightAuthError,
    NoonlightClient,
    NoonlightConnectionError,
    NoonlightError,
    NoonlightResponseError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util, slugify

from .const import (
    AUDIT_FILE_TEMPLATE,
    AUDIT_MAX_BYTES,
    CANCEL_SETTLE_SECONDS,
    CONF_ADDRESS,
    CONF_API_TOKEN,
    CONF_BASE_URL,
    CONF_CITY,
    CONF_DEDUPE_SECONDS,
    CONF_DEFAULT_ENTRY_DELAY,
    CONF_ENVIRONMENT,
    CONF_HEARTBEAT_MINUTES,
    CONF_LOCATION_ID,
    CONF_NAME,
    CONF_PHONE,
    CONF_STATE,
    CONF_ZIP,
    DEFAULT_DEDUPE_SECONDS,
    DEFAULT_ENTRY_DELAY,
    DEFAULT_ENVIRONMENT,
    DEFAULT_HEARTBEAT_MINUTES,
    DOMAIN,
    EVENT_CLEARED,
    EVENT_DISPATCH_CANCELED,
    EVENT_DISPATCH_DEDUPED,
    EVENT_DISPATCH_FIRED,
    EVENT_DISPATCH_REQUESTED,
    EVENT_ERROR,
    EVENT_STATUS_UPDATED,
    EVENT_TEST_DISPATCH,
    HEARTBEAT_FAILURE_THRESHOLD,
    HEARTBEAT_PROBE_ID,
    ISSUE_AUTH_FAILED,
    ISSUE_NETWORK_FAILED,
    ISSUE_UNEXPECTED_RESPONSE,
    POLL_INTERVAL,
    STATE_CANCELED,
    STATE_DISPATCHED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PENDING,
    STORAGE_KEY_TEMPLATE,
    STORAGE_VERSION,
    resolve_base_url,
)

_LOGGER = logging.getLogger(__name__)

# Noonlight statuses that mean the alarm is no longer active.
_TERMINAL_STATUSES = {"CANCELED", "RESOLVED", "COMPLETED", "FALSE"}

type NoonlightConfigEntry = ConfigEntry[NoonlightCoordinator]


class NoonlightCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate dispatch state for one Noonlight config entry."""

    def __init__(self, hass: HomeAssistant, entry: NoonlightConfigEntry) -> None:
        """Initialise the coordinator for ``entry``."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({entry.title})",
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )
        self.entry = entry
        self.account_slug = slugify(entry.title) or entry.entry_id[:8]

        self._environment = entry.data.get(CONF_ENVIRONMENT, DEFAULT_ENVIRONMENT)
        self.api = NoonlightClient(
            get_async_client(hass),
            entry.data[CONF_API_TOKEN],
            base_url=resolve_base_url(
                self._environment, entry.data.get(CONF_BASE_URL)
            ),
        )
        # A separate sandbox-only client backs ``test_dispatch`` so the test
        # always hits sandbox even when the entry runs in production.
        self._sandbox_api = NoonlightClient(
            get_async_client(hass),
            entry.data[CONF_API_TOKEN],
            base_url=SANDBOX_BASE_URL,
        )

        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY_TEMPLATE.format(entry_id=entry.entry_id),
        )
        self._audit_path = hass.config.path(
            ".storage", AUDIT_FILE_TEMPLATE.format(entry_id=entry.entry_id)
        )

        # Per-Noonlight-service epoch timestamp of the last *fired* dispatch.
        self._last_dispatch_ts: dict[str, float] = {}
        # Unsub handles for the entry-delay timer and the cancel-settle timer.
        self._pending_unsub: CALLBACK_TYPE | None = None
        self._settle_unsub: CALLBACK_TYPE | None = None
        # Free-text instructions for the pending dispatch (carried across the
        # entry-delay window to the eventual create_alarm call).
        self._pending_instructions: str | None = None
        # Idle-heartbeat bookkeeping: epoch of the last probe and the count of
        # consecutive failures (gates the Repair issue). Seed the clock so the
        # first probe lands ~POLL_INTERVAL after startup (not a full heartbeat
        # interval) — short enough to surface a broken token quickly, but not
        # during setup itself (the config flow already validated credentials).
        self._last_heartbeat: float = (
            dt_util.utcnow().timestamp() - self._heartbeat_interval + POLL_INTERVAL
        )
        self._heartbeat_failures: int = 0
        # True once at least one heartbeat probe has run; until then we keep the
        # fast (POLL_INTERVAL) refresh cadence so the first probe isn't delayed.
        self._probed_once: bool = False
        # Lazily ensure the audit dir exists exactly once (in the executor).
        self._audit_dir_ready: bool = False

        self.data = self._initial_state()

    # -- lifecycle ------------------------------------------------------------

    @staticmethod
    def _initial_state() -> dict[str, Any]:
        return {
            "state": STATE_IDLE,
            "alarm_id": None,
            "services": [],
            "last_event": None,
            # Heartbeat health: assume reachable until a probe proves otherwise.
            "api_healthy": True,
            "last_health_check": None,
        }

    async def async_load(self) -> None:
        """Restore persisted dedupe timestamps and last event from Store."""
        stored = await self._store.async_load()
        if not stored:
            return
        self._last_dispatch_ts = stored.get("last_dispatch_ts", {})
        # We deliberately do *not* restore an active ``pending``/``dispatched``
        # state on restart: a real alarm should not silently resume, and a
        # pending timer cannot survive a restart safely. Surface the last event
        # for history but settle to idle.
        last_event = stored.get("last_event")
        if last_event:
            self.data = {**self._initial_state(), "last_event": last_event}

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "last_dispatch_ts": self._last_dispatch_ts,
                "last_event": self.data.get("last_event"),
            }
        )

    async def async_shutdown(self) -> None:
        """Cancel timers on unload."""
        self._cancel_timer("_pending_unsub")
        self._cancel_timer("_settle_unsub")
        await super().async_shutdown()

    @callback
    def _cancel_timer(self, attr: str) -> None:
        """Cancel the timer whose unsub handle is stored in ``attr``."""
        unsub: CALLBACK_TYPE | None = getattr(self, attr)
        if unsub is not None:
            unsub()
            setattr(self, attr, None)

    # -- config helpers -------------------------------------------------------

    @property
    def _entry_delay_default(self) -> int:
        return self.entry.options.get(CONF_DEFAULT_ENTRY_DELAY, DEFAULT_ENTRY_DELAY)

    @property
    def _dedupe_seconds(self) -> int:
        return self.entry.options.get(CONF_DEDUPE_SECONDS, DEFAULT_DEDUPE_SECONDS)

    @property
    def _heartbeat_interval(self) -> int:
        """Seconds between idle heartbeat probes (from options)."""
        minutes = self.entry.options.get(
            CONF_HEARTBEAT_MINUTES, DEFAULT_HEARTBEAT_MINUTES
        )
        return int(minutes) * 60

    @property
    def _location_id(self) -> str | None:
        """Optional site/property label (sent to Noonlight as owner_id)."""
        return (self.entry.data.get(CONF_LOCATION_ID) or "").strip() or None

    def _build_instructions(self, instructions: str | None) -> str | None:
        """Combine the site label with per-dispatch instructions.

        Both are optional; the site label comes first so responders see e.g.
        "Site A — Triggered by Front Door motion".
        """
        parts = [p for p in (self._location_id, instructions) if p]
        return " — ".join(parts) if parts else None

    def _caller_payload(self) -> dict[str, str]:
        data = self.entry.data
        return {
            "name": data[CONF_NAME],
            "phone": data[CONF_PHONE],
            "address": data[CONF_ADDRESS],
            "city": data[CONF_CITY],
            "state": data[CONF_STATE],
            "zip_code": data[CONF_ZIP],
        }

    # -- polling --------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Drive the periodic timer.

        While a dispatch is active, poll the alarm's status every tick. While
        idle, run a lightweight heartbeat probe at the configured cadence so a
        bad token or unreachable API is surfaced *before* an emergency.
        """
        if self.data["state"] == STATE_DISPATCHED and self.data["alarm_id"]:
            data = await self._poll_active_alarm()
        elif self.data["state"] == STATE_IDLE and self._heartbeat_due():
            # Probe only while idle: never interfere with the entry-delay
            # (pending) window or the cancel-settle window.
            data = await self._run_heartbeat()
        else:
            data = self.data
        self._apply_refresh_interval(data["state"])
        return data

    def _heartbeat_due(self) -> bool:
        now = dt_util.utcnow().timestamp()
        return now - self._last_heartbeat >= self._heartbeat_interval

    @callback
    def _apply_refresh_interval(self, state: str) -> None:
        """Tune the poll cadence to the current dispatch state.

        Fast while a dispatch is active, slow (heartbeat cadence) while idle —
        but stay fast until the first heartbeat has run so startup detection
        isn't delayed.
        """
        if state == STATE_DISPATCHED or not self._probed_once:
            seconds = POLL_INTERVAL
        else:
            seconds = self._heartbeat_interval
        self.update_interval = timedelta(seconds=seconds)

    async def _run_heartbeat(self) -> dict[str, Any]:
        """Probe Noonlight (side-effect-free) and update health state.

        A GET on a bogus alarm id has no side effects: 401/403 means the token
        is bad, a connection error means unreachable, and anything else (e.g.
        404) means we are reachable + authorized.
        """
        self._last_heartbeat = dt_util.utcnow().timestamp()
        self._probed_once = True
        err: NoonlightError | None = None
        try:
            await self.api.get_alarm_status(HEARTBEAT_PROBE_ID)
            healthy = True  # 2xx (unlikely for a bogus id) — reachable + authed
        except NoonlightResponseError as probe_err:
            # Only a 404 on the bogus id proves reachable + authorized. A 5xx
            # outage or 429 rate-limit also raises NoonlightResponseError, and
            # must NOT be treated as healthy.
            healthy = probe_err.status_code == 404
            err = None if healthy else probe_err
        except NoonlightError as probe_err:  # auth / connection failures
            healthy, err = False, probe_err

        data = dict(self.data)
        if healthy:
            self._mark_healthy(data)
            return data

        self._heartbeat_failures += 1
        _LOGGER.warning(
            "Noonlight heartbeat failed (%s consecutive): %s",
            self._heartbeat_failures,
            err,
        )
        if self._heartbeat_failures >= HEARTBEAT_FAILURE_THRESHOLD:
            data["api_healthy"] = False
            # Reuse the dispatch error mapping: raises the right Repair issue
            # and starts reauth on an auth failure.
            self._handle_api_error(err)
        return data

    @callback
    def _mark_healthy(self, data: dict[str, Any]) -> None:
        """Record a successful probe/poll.

        Reset failures, clear issues, and stamp the health fields on ``data``.
        """
        self._heartbeat_failures = 0
        self._clear_health_issues()
        data["api_healthy"] = True
        data["last_health_check"] = dt_util.utcnow().isoformat()

    @callback
    def _clear_health_issues(self) -> None:
        """Delete any heartbeat-raised Repair issues once healthy again."""
        for key in (
            ISSUE_AUTH_FAILED,
            ISSUE_NETWORK_FAILED,
            ISSUE_UNEXPECTED_RESPONSE,
        ):
            ir.async_delete_issue(self.hass, DOMAIN, f"{key}_{self.entry.entry_id}")

    async def _poll_active_alarm(self) -> dict[str, Any]:
        """Poll Noonlight for the active alarm's status.

        A poll is also a live health signal: success marks the API healthy,
        failure marks it unhealthy (so the connectivity sensor doesn't claim
        'reachable' while polling of a live alarm is failing).
        """
        try:
            status = await self.api.get_alarm_status(self.data["alarm_id"])
        except NoonlightError as err:
            self._handle_api_error(err)
            # Keep the last known state; a transient poll failure should not
            # silently clear an active alarm.
            return {**self.data, "api_healthy": False}

        data = dict(self.data)
        self._mark_healthy(data)
        remote_status = str(status.get("status", "")).upper()
        await self._record_event(EVENT_STATUS_UPDATED, {"remote_status": remote_status})
        if remote_status in _TERMINAL_STATUSES:
            return self._transition(
                STATE_IDLE,
                event=EVENT_CLEARED,
                alarm_id=None,
                services=[],
                extra={
                    "api_healthy": True,
                    "last_health_check": data["last_health_check"],
                },
            )
        return data

    # -- public actions -------------------------------------------------------

    async def async_dispatch(
        self,
        services: list[str],
        entry_delay: int | None,
        instructions: str | None = None,
    ) -> None:
        """Request a dispatch for ``services`` after the entry-delay window.

        ``instructions`` is optional free-text context (e.g. the triggering
        sensor) forwarded to Noonlight when the dispatch fires.
        """
        delay = self._entry_delay_default if entry_delay is None else entry_delay

        deduped = self._deduped_services(services)
        active = [s for s in services if s not in deduped]
        if deduped:
            _LOGGER.warning(
                "Noonlight dispatch for %s suppressed by %ss de-dup window",
                ", ".join(sorted(deduped)),
                self._dedupe_seconds,
            )
            await self._record_event(
                EVENT_DISPATCH_DEDUPED, {"services": sorted(deduped)}
            )
        if not active:
            return

        self._cancel_timer("_pending_unsub")
        self._cancel_timer("_settle_unsub")
        self._pending_instructions = instructions

        self._transition(
            STATE_PENDING,
            event=EVENT_DISPATCH_REQUESTED,
            services=active,
            event_detail={
                "services": active,
                "entry_delay": delay,
                "instructions": instructions,
            },
        )

        if delay <= 0:
            await self._fire_dispatch()
            return

        self._pending_unsub = async_call_later(
            self.hass, delay, self._fire_dispatch_callback
        )

    async def async_cancel(self, reason: str | None) -> None:
        """Cancel a pending dispatch, or flag an active one as a false alarm."""
        state = self.data["state"]

        if state == STATE_PENDING:
            self._cancel_timer("_pending_unsub")
            self._transition(
                STATE_CANCELED,
                event=EVENT_DISPATCH_CANCELED,
                event_detail={"reason": reason, "phase": "pending"},
            )
            self._settle_unsub = async_call_later(
                self.hass, CANCEL_SETTLE_SECONDS, self._settle_callback
            )
            await self._async_save()
            return

        if state == STATE_DISPATCHED and self.data["alarm_id"]:
            alarm_id = self.data["alarm_id"]
            try:
                await self.api.cancel_alarm(alarm_id)
            except NoonlightError as err:
                self._handle_api_error(err)
                raise
            self._transition(
                STATE_CANCELED,
                event=EVENT_DISPATCH_CANCELED,
                event_detail={"reason": reason, "phase": "dispatched"},
            )
            self._settle_unsub = async_call_later(
                self.hass, CANCEL_SETTLE_SECONDS, self._settle_callback
            )
            await self._async_save()
            return

        _LOGGER.debug("Noonlight cancel called with nothing to cancel")

    async def async_test_dispatch(self) -> dict[str, Any]:
        """Round-trip a sandbox alarm to verify credentials + connectivity.

        Always uses the sandbox client, even in production mode, and never
        touches the live state machine.
        """
        try:
            result = await self._sandbox_api.create_alarm(
                services=["police"],
                instructions=self._build_instructions(
                    "Home Assistant test dispatch (ignore)"
                ),
                owner_id=self._location_id,
                **self._caller_payload(),
            )
            # Immediately cancel so the sandbox alarm does not linger.
            if result.get("id"):
                await self._sandbox_api.cancel_alarm(result["id"])
        except NoonlightError as err:
            self._handle_api_error(err)
            await self._record_event(EVENT_ERROR, {"context": "test_dispatch"})
            raise
        await self._record_event(EVENT_TEST_DISPATCH, {"alarm_id": result.get("id")})
        return result

    # -- internal: firing -----------------------------------------------------

    @callback
    def _fire_dispatch_callback(self, _now: Any) -> None:
        self.entry.async_create_background_task(
            self.hass, self._fire_dispatch(), "noonlight_fire_dispatch"
        )

    async def _fire_dispatch(self) -> None:
        """Actually POST the alarm to Noonlight (timer expired or delay==0)."""
        self._pending_unsub = None
        if self.data["state"] != STATE_PENDING:
            return  # canceled out from under us

        services = list(self.data["services"])
        instructions = self._build_instructions(self._pending_instructions)
        try:
            result = await self.api.create_alarm(
                services=services,
                instructions=instructions,
                owner_id=self._location_id,
                **self._caller_payload(),
            )
        except NoonlightError as err:
            self._handle_api_error(err)
            self._transition(
                STATE_ERROR,
                event=EVENT_ERROR,
                event_detail={"error": str(err)},
            )
            await self._async_save()
            return

        now = dt_util.utcnow().timestamp()
        for service in services:
            self._last_dispatch_ts[service] = now

        self._transition(
            STATE_DISPATCHED,
            event=EVENT_DISPATCH_FIRED,
            alarm_id=result.get("id"),
            services=services,
            event_detail={
                "alarm_id": result.get("id"),
                "services": services,
                "instructions": instructions,
            },
        )
        await self._async_save()

    @callback
    def _settle_callback(self, _now: Any) -> None:
        self._settle_unsub = None
        if self.data["state"] != STATE_CANCELED:
            return
        self._transition(STATE_IDLE, event=EVENT_CLEARED, alarm_id=None, services=[])

    # -- internal: dedupe -----------------------------------------------------

    def _deduped_services(self, services: list[str]) -> set[str]:
        """Return the subset of ``services`` still inside the de-dup window."""
        window = self._dedupe_seconds
        if window <= 0:
            return set()
        now = dt_util.utcnow().timestamp()
        return {
            service
            for service in services
            if now - self._last_dispatch_ts.get(service, 0.0) < window
        }

    # -- internal: state + audit ---------------------------------------------

    def _transition(
        self,
        new_state: str,
        *,
        event: str,
        alarm_id: Any = ...,
        services: list[str] | None = None,
        event_detail: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Move to ``new_state``, record an event, and push to entities."""
        data = dict(self.data)
        data["state"] = new_state
        if alarm_id is not ...:
            data["alarm_id"] = alarm_id
        if services is not None:
            data["services"] = services
        if extra:
            data.update(extra)
        data["last_event"] = {
            "type": event,
            "timestamp": dt_util.utcnow().isoformat(),
            "state": new_state,
        }
        # Retune the poll cadence to the new state before pushing, so
        # async_set_updated_data reschedules at the right interval.
        self._apply_refresh_interval(new_state)
        self.async_set_updated_data(data)
        self.hass.async_create_task(
            self._write_audit(event, new_state, event_detail or {})
        )
        return data

    async def _record_event(self, event: str, detail: dict[str, Any]) -> None:
        """Record an event without changing state (e.g. dedupe, status poll)."""
        await self._write_audit(event, self.data["state"], detail)

    async def _write_audit(
        self, event: str, state: str, detail: dict[str, Any]
    ) -> None:
        entry = {
            "ts": dt_util.utcnow().isoformat(),
            "event": event,
            "state": state,
            "environment": self._environment,
            "detail": detail,
        }
        line = json.dumps(entry, default=str)
        try:
            await self.hass.async_add_executor_job(self._append_audit_line, line)
        except OSError as err:  # pragma: no cover - disk failures are rare
            _LOGGER.error("Failed writing Noonlight audit log: %s", err)

    def _append_audit_line(self, line: str) -> None:
        """Append one JSONL record, rotating the file if it has grown large."""
        # The .storage dir normally exists (HA's Store creates it), but don't
        # depend on ordering: ensure it's there once so the first audit line on
        # a fresh install is never lost (runs in the executor).
        if not self._audit_dir_ready:
            os.makedirs(os.path.dirname(self._audit_path), exist_ok=True)
            self._audit_dir_ready = True
        try:
            if (
                os.path.exists(self._audit_path)
                and os.path.getsize(self._audit_path) >= AUDIT_MAX_BYTES
            ):
                os.replace(self._audit_path, f"{self._audit_path}.1")
        except OSError:
            pass
        with open(self._audit_path, "a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")

    # -- internal: error handling --------------------------------------------

    def _handle_api_error(self, err: NoonlightError) -> None:
        """Map an API error to a Repair issue (and reauth on auth failure)."""
        if isinstance(err, NoonlightAuthError):
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"{ISSUE_AUTH_FAILED}_{self.entry.entry_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key=ISSUE_AUTH_FAILED,
            )
            self.entry.async_start_reauth(self.hass)
        elif isinstance(err, NoonlightConnectionError):
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"{ISSUE_NETWORK_FAILED}_{self.entry.entry_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_NETWORK_FAILED,
            )
        elif isinstance(err, NoonlightResponseError):
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"{ISSUE_UNEXPECTED_RESPONSE}_{self.entry.entry_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_UNEXPECTED_RESPONSE,
            )
        _LOGGER.error("Noonlight API error: %s", err)
