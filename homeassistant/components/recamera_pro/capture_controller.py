"""Serialize device-native capture operations for one camera."""

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import logging
from typing import Any
import uuid

from recamera_protocol import (
    RecameraConnectionError,
    RecameraDeviceClient,
    RecameraError,
    RecameraProtocolError,
    RecameraValidationError,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, EVENT_CAPTURE_COMPLETED

_LOGGER = logging.getLogger(__name__)

_ACTIVE_CAPTURE_STATES = {"PENDING", "WRITING"}
_FAILED_CAPTURE_STATES = {"FAILED", "INTERRUPTED", "CANCELED"}
_COMPLETION_GRACE_SECONDS = 15.0
_STATUS_SILENCE_SECONDS = 10.0
_START_RECONCILE_SECONDS = 10.0
_MAX_RETRY_DELAY_SECONDS = 5.0
_OVERDUE_CHECK_INTERVAL_SECONDS = 30.0
_OVERDUE_MAX_CHECKS = 3
_SNAPSHOT_RESULT_TTL_SECONDS = 2.0
_STATUS_REQUEST_TIMEOUT_SECONDS = 5.0
_STOP_COMPLETION_TIMEOUT_SECONDS = 30.0


class CaptureState(StrEnum):
    """Device capture lifecycle."""

    IDLE = "idle"
    STARTING = "starting"
    RECORDING = "recording"
    COMPLETING = "completing"
    FAILED = "failed"
    UNKNOWN = "unknown"


class CaptureBusyError(RecameraValidationError):
    """Raised when the single device capture slot is unavailable."""


class CaptureRequestConflictError(RecameraValidationError):
    """Raised when one context expands into conflicting parameters."""

    def __init__(self) -> None:
        """Initialize a capture request conflict error."""
        super().__init__("device_capture_request_conflict")


class CaptureOwnershipError(RecameraValidationError):
    """Raised when the device task no longer belongs to this integration."""


class CaptureTerminalFailureError(RecameraProtocolError):
    """Raised when the device explicitly reports a terminal capture failure."""


@dataclass(slots=True)
class CaptureOperation:
    """One capture owned by this integration instance."""

    kind: str
    request_id: str
    fingerprint: str
    state: CaptureState = CaptureState.STARTING
    capture_id: str | None = None
    capture: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    stop_response: dict[str, Any] | None = None
    request_token: str = field(default_factory=lambda: uuid.uuid4().hex)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_monotonic: float = 0.0
    expected_end_monotonic: float = 0.0
    last_confirmed_monotonic: float = 0.0
    duration: int = 0
    overdue_checks: int = 0
    restored: bool = False
    completion_event: asyncio.Event = field(
        default_factory=asyncio.Event,
        repr=False,
    )


class CaptureController:
    """Own and reconcile the device's single asynchronous capture task."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: RecameraDeviceClient,
        *,
        device_id: str = "unknown",
        entry_id: str | None = None,
    ) -> None:
        """Initialize the single-slot device capture controller."""
        self.hass = hass
        self.client = client
        self.device_id = device_id
        self.entry_id = entry_id
        self._lock = asyncio.Lock()
        self._operation: CaptureOperation | None = None
        self._snapshot_task: asyncio.Task[dict[str, object]] | None = None
        self._monitor_task: asyncio.Task[None] | None = None
        self._history: list[dict[str, object]] = []
        self._snapshot_results: dict[
            tuple[str, str], tuple[float, dict[str, object]]
        ] = {}
        self._store = (
            Store[dict[str, Any]](hass, 1, f"{DOMAIN}.capture.{entry_id}")
            if entry_id
            else None
        )

    @property
    def state(self) -> CaptureState:
        """Return the current capture lifecycle state."""
        return (
            self._operation.state if self._operation is not None else CaptureState.IDLE
        )

    @property
    def operation(self) -> CaptureOperation | None:
        """Return the current in-memory operation."""
        return self._operation

    def diagnostics(self) -> dict[str, object]:
        """Return bounded, non-secret capture diagnostics."""
        operation = self._operation
        return {
            "state": self.state,
            "kind": operation.kind if operation else None,
            "capture_id": operation.capture_id if operation else None,
            "request_id": operation.request_id if operation else None,
            "error": operation.error if operation else None,
            "history": list(self._history[-10:]),
        }

    @staticmethod
    def _fingerprint(kind: str, output: str | None, duration: int | None = None) -> str:
        """Bind context deduplication to the actual action parameters."""
        return f"{kind}|{output or ''}|{duration or ''}"

    def _new_operation(
        self,
        kind: str,
        request_id: str,
        output: str | None,
        duration: int = 0,
    ) -> CaptureOperation:
        now = asyncio.get_running_loop().time()
        return CaptureOperation(
            kind=kind,
            request_id=request_id,
            fingerprint=self._fingerprint(kind, output, duration),
            started_monotonic=now,
            expected_end_monotonic=(now + duration + _COMPLETION_GRACE_SECONDS),
            last_confirmed_monotonic=now,
            duration=duration,
        )

    async def async_capture_snapshot(
        self, output: str | None, *, request_id: str
    ) -> dict[str, object]:
        """Capture one JPG, sharing only identical service expansions."""
        fingerprint = self._fingerprint("snapshot", output)
        async with self._lock:
            now = asyncio.get_running_loop().time()
            for key, (timestamp, _result) in list(self._snapshot_results.items()):
                if now - timestamp > _SNAPSHOT_RESULT_TTL_SECONDS:
                    del self._snapshot_results[key]
            for cached_request_id, cached_fingerprint in self._snapshot_results:
                if (
                    cached_request_id == request_id
                    and cached_fingerprint != fingerprint
                ):
                    raise CaptureRequestConflictError
            cached = self._snapshot_results.get((request_id, fingerprint))
            if cached is not None:
                return cached[1]
            if self._snapshot_task is not None:
                operation = self._operation
                if (
                    operation is not None
                    and operation.kind == "snapshot"
                    and operation.request_id == request_id
                ):
                    if operation.fingerprint != fingerprint:
                        raise CaptureRequestConflictError
                    task = self._snapshot_task
                else:
                    raise CaptureBusyError("device_capture_busy")
            else:
                await self._async_ensure_idle()
                operation = self._new_operation("snapshot", request_id, output)
                self._operation = operation
                task = self.hass.async_create_task(
                    self._async_run_snapshot(operation, output)
                )
                self._snapshot_task = task
        result = await asyncio.shield(task)
        self._snapshot_results[(request_id, fingerprint)] = (
            asyncio.get_running_loop().time(),
            result,
        )
        return result

    async def _async_run_snapshot(
        self, operation: CaptureOperation, output: str | None
    ) -> dict[str, object]:
        """Start and wait for one snapshot while keeping the slot reserved."""
        try:
            capture = await self.client.async_start_capture(
                "JPG",
                output=output,
                request_token=operation.request_token,
            )
            operation.capture = capture
            operation.capture_id = str(capture.get("sID") or "")
            operation.state = CaptureState.COMPLETING
            completed = await self.client.async_wait_for_capture(operation.capture_id)
            operation.capture = completed
            operation.state = CaptureState.IDLE
            self._record_history(operation, success=True)
        except RecameraConnectionError, RecameraProtocolError:
            try:
                completed = await self._async_reconcile_snapshot(operation)
            except (RecameraConnectionError, RecameraProtocolError) as reconcile_err:
                operation.state = (
                    CaptureState.FAILED
                    if isinstance(reconcile_err, CaptureTerminalFailureError)
                    else CaptureState.UNKNOWN
                )
                operation.error = str(reconcile_err)
                self._record_history(operation, success=False)
                raise
            operation.capture = completed
            operation.state = CaptureState.IDLE
            operation.error = None
            self._record_history(operation, success=True)
            return {"capture": completed}
        except Exception as err:
            operation.state = CaptureState.FAILED
            operation.error = str(err)
            self._record_history(operation, success=False)
            raise
        else:
            return {"capture": completed}
        finally:
            async with self._lock:
                if self._operation is operation:
                    self._operation = None
                if self._snapshot_task is asyncio.current_task():
                    self._snapshot_task = None

    async def _async_reconcile_snapshot(
        self,
        operation: CaptureOperation,
    ) -> dict[str, Any]:
        """Resolve an uncertain JPG start without submitting a second one."""
        deadline = asyncio.get_running_loop().time() + _START_RECONCILE_SECONDS
        retry = 0
        while asyncio.get_running_loop().time() < deadline:
            try:
                status = await self._async_get_status_limited()
            except (RecameraError, TimeoutError, OSError) as err:
                operation.error = str(err)
            else:
                capture = status.get("dLastCapture")
                if isinstance(capture, dict):
                    capture_id = str(capture.get("sID") or "")
                    request_token = str(capture.get("sRequestToken") or "")
                    if capture_id and (
                        capture_id == operation.capture_id
                        or request_token == operation.request_token
                    ):
                        operation.capture = capture
                        operation.capture_id = capture_id
                        capture_state = str(capture.get("sStatus") or "").upper()
                        if capture_state == "COMPLETED":
                            return capture
                        if capture_state in _FAILED_CAPTURE_STATES:
                            raise CaptureTerminalFailureError(
                                f"capture_{capture_state.lower()}"
                            )
                        if capture_state in _ACTIVE_CAPTURE_STATES:
                            return await self.client.async_wait_for_capture(capture_id)
            retry += 1
            await asyncio.sleep(min(5.0, retry * 0.5))
        raise RecameraConnectionError("capture_status_unconfirmed")

    async def async_start_recording(
        self, output: str | None, duration: int, *, request_id: str
    ) -> dict[str, object]:
        """Start one MP4 recording and monitor it in the background."""
        fingerprint = self._fingerprint("recording", output, duration)
        async with self._lock:
            if self._operation is not None:
                operation = self._operation
                if operation.kind == "recording" and operation.request_id == request_id:
                    if operation.fingerprint != fingerprint:
                        raise CaptureRequestConflictError
                    return {"capture": dict(operation.capture)}
                raise CaptureBusyError("device_capture_busy")
            await self._async_ensure_idle()
            operation = self._new_operation("recording", request_id, output, duration)
            self._operation = operation
            try:
                capture = await self.client.async_start_capture(
                    "MP4",
                    output=output,
                    duration=duration,
                    request_token=operation.request_token,
                )
            except asyncio.CancelledError:
                operation.state = CaptureState.UNKNOWN
                operation.error = "start_status_unconfirmed"
                self._monitor_task = self.hass.async_create_background_task(
                    self._async_reconcile_start(operation),
                    "recamera_pro.capture.start_reconcile",
                )
                raise
            except RecameraValidationError as err:
                operation.state = CaptureState.FAILED
                operation.error = str(err)
                self._record_history(operation, success=False)
                self._operation = None
                raise
            except RecameraConnectionError, RecameraProtocolError:
                operation.state = CaptureState.UNKNOWN
                operation.error = "start_status_unconfirmed"
                self._monitor_task = self.hass.async_create_background_task(
                    self._async_reconcile_start(operation),
                    "recamera_pro.capture.start_reconcile",
                )
                raise
            except Exception as err:
                operation.state = CaptureState.FAILED
                operation.error = str(err)
                self._record_history(operation, success=False)
                self._operation = None
                raise
            operation.capture = capture
            operation.capture_id = str(capture.get("sID") or "")
            operation.state = CaptureState.RECORDING
            operation.last_confirmed_monotonic = asyncio.get_running_loop().time()
            self._persist(operation)
            self._monitor_task = self.hass.async_create_background_task(
                self._async_monitor_recording(operation),
                f"recamera_pro.capture.{operation.capture_id}",
            )
            return {"capture": capture}

    async def _async_reconcile_start(self, operation: CaptureOperation) -> None:
        """Resolve a cancelled start without issuing another start request."""
        restored = False
        # The API request may consume more than the whole request budget before
        # it returns. Reconciliation gets its own deadline so at least one
        # status query can prove whether the device accepted the start.
        deadline = asyncio.get_running_loop().time() + _START_RECONCILE_SECONDS
        try:
            retry = 0
            while asyncio.get_running_loop().time() < deadline:
                try:
                    status = await self._async_get_status_limited()
                    capture = status.get("dLastCapture")
                    if isinstance(capture, dict) and self._capture_started_by_operation(
                        capture, operation
                    ):
                        operation.capture = capture
                        operation.capture_id = str(capture["sID"])
                        capture_state = str(capture.get("sStatus") or "").upper()
                        if capture_state == "COMPLETED":
                            operation.state = CaptureState.IDLE
                            self._record_history(operation, success=True)
                            await self._async_remove_persisted()
                            return
                        if capture_state in _FAILED_CAPTURE_STATES:
                            operation.state = CaptureState.FAILED
                            operation.error = f"capture_{capture_state.lower()}"
                            self._record_history(operation, success=False)
                            await self._async_remove_persisted()
                            return
                        if capture_state in _ACTIVE_CAPTURE_STATES:
                            operation.state = CaptureState.RECORDING
                            operation.last_confirmed_monotonic = (
                                asyncio.get_running_loop().time()
                            )
                            self._persist(operation)
                            restored = True
                            self._monitor_task = self.hass.async_create_background_task(
                                self._async_monitor_recording(operation),
                                "recamera_pro.capture.reconciled",
                            )
                            return
                    if status["bReadyToStartNew"]:
                        operation.state = CaptureState.FAILED
                        operation.error = "start_cancelled"
                        self._record_history(operation, success=False)
                        return
                    operation.state = CaptureState.UNKNOWN
                    operation.error = "start_status_unconfirmed"
                except asyncio.CancelledError:
                    raise
                except (RecameraError, TimeoutError, OSError) as err:
                    operation.state = CaptureState.UNKNOWN
                    operation.error = str(err)
                retry += 1
                await asyncio.sleep(min(_MAX_RETRY_DELAY_SECONDS, retry * 0.5))
            operation.state = CaptureState.UNKNOWN
            operation.error = "start_status_unconfirmed"
            self._record_history(operation, success=False)
        finally:
            async with self._lock:
                if not restored and self._operation is operation:
                    self._operation = None
                if self._monitor_task is asyncio.current_task():
                    self._monitor_task = None

    @staticmethod
    def _capture_started_by_operation(
        capture: dict[str, Any], operation: CaptureOperation
    ) -> bool:
        """Grant ownership only when firmware proves the request token."""
        request_token = capture.get("sRequestToken")
        return bool(request_token and request_token == operation.request_token)

    async def _async_monitor_recording(self, operation: CaptureOperation) -> None:
        """Track completion with bounded retries and ownership checks."""
        retry = 0
        try:
            while True:
                now = asyncio.get_running_loop().time()
                overdue = now > operation.expected_end_monotonic
                if (
                    not overdue
                    and now - operation.last_confirmed_monotonic
                    > _STATUS_SILENCE_SECONDS
                ):
                    operation.state = CaptureState.UNKNOWN
                    operation.error = "capture_status_unconfirmed"
                try:
                    status = await self._async_get_status_limited()
                except asyncio.CancelledError:
                    raise
                except (RecameraError, TimeoutError, OSError) as err:
                    operation.state = CaptureState.UNKNOWN
                    operation.error = str(err)
                    retry += 1
                    if overdue:
                        if self._overdue_exhausted(operation):
                            return
                        await asyncio.sleep(_OVERDUE_CHECK_INTERVAL_SECONDS)
                    else:
                        await asyncio.sleep(self._retry_delay(retry))
                    continue

                capture = status.get("dLastCapture")
                if (
                    not isinstance(capture, dict)
                    or str(capture.get("sID") or "") != operation.capture_id
                ):
                    operation.state = CaptureState.UNKNOWN
                    operation.error = "capture_status_unconfirmed"
                    retry += 1
                    if overdue:
                        if self._overdue_exhausted(operation):
                            return
                        await asyncio.sleep(_OVERDUE_CHECK_INTERVAL_SECONDS)
                    else:
                        await asyncio.sleep(min(_MAX_RETRY_DELAY_SECONDS, retry * 0.5))
                    continue

                operation.capture = capture
                operation.error = None
                retry = 0
                capture_state = str(capture.get("sStatus") or "").upper()
                if capture_state == "COMPLETED":
                    operation.state = CaptureState.IDLE
                    self._record_history(operation, success=True)
                    await self._async_remove_persisted()
                    return
                if capture_state in _FAILED_CAPTURE_STATES:
                    operation.state = CaptureState.FAILED
                    operation.error = f"capture_{capture_state.lower()}"
                    self._record_history(operation, success=False)
                    await self._async_remove_persisted()
                    return
                if capture_state in _ACTIVE_CAPTURE_STATES:
                    operation.last_confirmed_monotonic = now
                    operation.state = (
                        CaptureState.COMPLETING
                        if operation.stop_response is not None
                        else CaptureState.RECORDING
                    )
                    if overdue:
                        if self._overdue_exhausted(operation):
                            return
                        operation.state = CaptureState.UNKNOWN
                        operation.error = "capture_overdue_unconfirmed"
                        await asyncio.sleep(_OVERDUE_CHECK_INTERVAL_SECONDS)
                        continue
                else:
                    operation.state = CaptureState.UNKNOWN
                    operation.error = "capture_status_unconfirmed"
                    if overdue:
                        if self._overdue_exhausted(operation):
                            return
                        await asyncio.sleep(_OVERDUE_CHECK_INTERVAL_SECONDS)
                        continue
                await asyncio.sleep(0.5)
        finally:
            async with self._lock:
                if self._operation is operation:
                    self._operation = None
                if self._monitor_task is asyncio.current_task():
                    self._monitor_task = None
                operation.completion_event.set()

    def _overdue_exhausted(
        self,
        operation: CaptureOperation,
    ) -> bool:
        """Count one overdue status query and finish after the bounded limit."""
        operation.overdue_checks += 1
        if operation.overdue_checks < _OVERDUE_MAX_CHECKS:
            return False
        operation.state = CaptureState.UNKNOWN
        operation.error = "capture_overdue_unconfirmed"
        self._record_history(operation, success=False)
        return True

    async def _async_get_status_limited(self) -> dict[str, Any]:
        """Bound status requests so monitoring deadlines remain meaningful."""
        try:
            return await asyncio.wait_for(
                self.client.async_get_capture_status(),
                timeout=_STATUS_REQUEST_TIMEOUT_SECONDS,
            )
        except TimeoutError as err:
            raise RecameraConnectionError("capture_status_timeout") from err

    @staticmethod
    def _retry_delay(retry: int) -> float:
        """Cap exponential delay without computing an overflowing exponent."""
        return min(_MAX_RETRY_DELAY_SECONDS, 0.5 * (1 << min(retry, 4)))

    async def async_stop_capture(self, *, request_id: str) -> dict[str, object]:
        """Stop the owned recording and wait for its file to become terminal."""
        async with self._lock:
            operation = self._operation
            if operation is None:
                await self._async_restore_locked()
                operation = self._operation
            if operation is None:
                status = await self._async_get_status_limited()
                if status["bReadyToStartNew"]:
                    return {
                        "capture": {
                            "code": 0,
                            "message": "no_active_capture",
                        }
                    }
                raise CaptureBusyError("external_capture_active")
            if operation.kind != "recording":
                raise RecameraProtocolError("active_capture_is_not_recording")
            if operation.stop_response is None:
                status = await self._async_get_status_limited()
                capture = status.get("dLastCapture")
                if (
                    not isinstance(capture, dict)
                    or str(capture.get("sID") or "") != operation.capture_id
                ):
                    await self._async_abandon_locked(
                        operation, "capture_ownership_lost"
                    )
                    raise CaptureOwnershipError("capture_ownership_lost")
                capture_state = str(capture.get("sStatus") or "").upper()
                if capture_state not in _ACTIVE_CAPTURE_STATES:
                    if capture_state == "COMPLETED":
                        operation.capture = capture
                        operation.state = CaptureState.IDLE
                        operation.error = None
                        if self._monitor_task is not None:
                            self._monitor_task.cancel()
                            self._monitor_task = None
                        if self._operation is operation:
                            self._operation = None
                        self._record_history(operation, success=True)
                        await self._async_remove_persisted()
                        operation.completion_event.set()
                        return {
                            "capture": {
                                **capture,
                                "capture_id": operation.capture_id,
                                "terminal": True,
                                "outcome": "completed",
                            }
                        }
                    await self._async_abandon_locked(operation, "capture_not_active")
                    raise CaptureOwnershipError("capture_not_active")

                response = await self.client.async_stop_capture()
                operation.stop_response = response
                operation.state = CaptureState.COMPLETING
                self._persist(operation)
            else:
                response = operation.stop_response

        try:
            async with asyncio.timeout(_STOP_COMPLETION_TIMEOUT_SECONDS):
                await operation.completion_event.wait()
        except TimeoutError as err:
            raise RecameraConnectionError("capture_completion_timeout") from err

        if operation.state != CaptureState.IDLE:
            raise RecameraProtocolError(operation.error or "capture_stop_unconfirmed")
        return {
            "capture": {
                **dict(response),
                "capture_id": operation.capture_id,
                "terminal": True,
                "outcome": "completed",
            }
        }

    async def _async_ensure_idle(self) -> None:
        """Reject starts while an untracked external capture is active."""
        await self._async_restore_locked()
        if self._operation is not None:
            raise CaptureBusyError("device_capture_busy")
        status = await self._async_get_status_limited()
        if not status["bReadyToStartNew"]:
            raise CaptureBusyError("external_capture_active")

    async def _async_abandon_locked(
        self, operation: CaptureOperation, error: str
    ) -> None:
        """Forget stale ownership without stopping the current device task."""
        operation.state = CaptureState.UNKNOWN
        operation.error = error
        self._record_history(operation, success=False)
        if self._operation is operation:
            self._operation = None
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            self._monitor_task = None
        operation.completion_event.set()
        await self._async_remove_persisted()

    def _record_history(self, operation: CaptureOperation, *, success: bool) -> None:
        """Keep a bounded operation history for diagnostics."""
        capture = operation.capture
        terminal = success or operation.state == CaptureState.FAILED
        outcome = (
            "completed"
            if success
            else "failed"
            if operation.state == CaptureState.FAILED
            else "unknown"
            if operation.state == CaptureState.UNKNOWN
            else str(operation.state)
        )
        record = {
            "kind": operation.kind,
            "capture_id": operation.capture_id,
            "success": success,
            "state": operation.state,
            "terminal": terminal,
            "outcome": outcome,
            "restored": operation.restored,
            "error": operation.error,
            "sFileName": capture.get("sFileName"),
            "sOutputDirectory": capture.get("sOutputDirectory"),
        }
        self._history.append(record)
        del self._history[:-20]
        if not success:
            _LOGGER.warning(
                "reCamera %s capture failed: kind=%s id=%s state=%s error=%s",
                self.device_id,
                operation.kind,
                operation.capture_id,
                operation.state,
                operation.error,
            )
        bus = getattr(self.hass, "bus", None)
        if bus is not None:
            bus.async_fire(
                EVENT_CAPTURE_COMPLETED,
                {
                    "device_id": self.device_id,
                    "entry_id": self.entry_id,
                    **record,
                },
            )

    def _persist(self, operation: CaptureOperation) -> None:
        """Persist only information needed to revalidate one recording."""
        if self._store is None or operation.capture_id is None:
            return
        payload = {
            "device_id": self.device_id,
            "entry_id": self.entry_id,
            "capture_id": operation.capture_id,
            "kind": operation.kind,
            "started_at": operation.started_at.isoformat(),
            "duration": operation.duration,
        }
        self._store.async_delay_save(lambda: payload, 0)

    async def _async_remove_persisted(self) -> None:
        """Remove a completed or invalidated ownership record."""
        if self._store is not None:
            await self._store.async_remove()

    async def async_restore(self) -> None:
        """Restore ownership only when the device confirms the same task."""
        async with self._lock:
            await self._async_restore_locked()

    async def _async_restore_locked(self) -> None:
        """Reconcile the persisted task with current device state."""
        if self._store is None or self._operation is not None:
            return
        stored = await self._store.async_load()
        if not isinstance(stored, dict):
            return
        capture_id = str(stored.get("capture_id") or "")
        started_at_raw = str(stored.get("started_at") or "")
        try:
            started_at = datetime.fromisoformat(started_at_raw)
            duration = int(stored["duration"])
        except TypeError, ValueError, KeyError:
            await self._async_remove_persisted()
            return
        if (
            stored.get("device_id") != self.device_id
            or stored.get("entry_id") != self.entry_id
            or stored.get("kind") != "recording"
            or not capture_id
            or started_at.tzinfo is None
            or duration <= 0
        ):
            await self._async_remove_persisted()
            return

        now = asyncio.get_running_loop().time()
        elapsed = max(0.0, (datetime.now(UTC) - started_at).total_seconds())
        started_monotonic = now - elapsed
        try:
            status = await self._async_get_status_limited()
        except RecameraError, TimeoutError, OSError:
            operation = CaptureOperation(
                kind="recording",
                request_id="restored",
                fingerprint="restored",
                state=CaptureState.UNKNOWN,
                capture_id=capture_id,
                started_at=started_at,
                started_monotonic=started_monotonic,
                expected_end_monotonic=(
                    started_monotonic + duration + _COMPLETION_GRACE_SECONDS
                ),
                last_confirmed_monotonic=started_monotonic,
                duration=duration,
                error="capture_status_unconfirmed",
            )
            self._operation = operation
            self._monitor_task = self.hass.async_create_background_task(
                self._async_monitor_recording(operation),
                "recamera_pro.capture.restore_reconcile",
            )
            return

        capture = status.get("dLastCapture")
        if not isinstance(capture, dict) or str(capture.get("sID") or "") != capture_id:
            await self._async_remove_persisted()
            return
        capture_state = str(capture.get("sStatus") or "").upper()
        if capture_state == "COMPLETED":
            operation = CaptureOperation(
                kind="recording",
                request_id="restored",
                fingerprint="restored",
                state=CaptureState.IDLE,
                capture_id=capture_id,
                capture=capture,
                started_at=started_at,
                started_monotonic=started_monotonic,
                expected_end_monotonic=(
                    started_monotonic + duration + _COMPLETION_GRACE_SECONDS
                ),
                last_confirmed_monotonic=now,
                duration=duration,
                restored=True,
            )
            self._record_history(operation, success=True)
            await self._async_remove_persisted()
            return
        if capture_state in _FAILED_CAPTURE_STATES:
            operation = CaptureOperation(
                kind="recording",
                request_id="restored",
                fingerprint="restored",
                state=CaptureState.FAILED,
                capture_id=capture_id,
                capture=capture,
                started_at=started_at,
                started_monotonic=started_monotonic,
                expected_end_monotonic=(
                    started_monotonic + duration + _COMPLETION_GRACE_SECONDS
                ),
                last_confirmed_monotonic=now,
                duration=duration,
                error=f"capture_{capture_state.lower()}",
                restored=True,
            )
            self._record_history(operation, success=False)
            await self._async_remove_persisted()
            return
        if capture_state not in _ACTIVE_CAPTURE_STATES:
            await self._async_remove_persisted()
            return
        operation = CaptureOperation(
            kind="recording",
            request_id="restored",
            fingerprint="restored",
            state=CaptureState.RECORDING,
            capture_id=capture_id,
            capture=capture,
            started_at=started_at,
            started_monotonic=started_monotonic,
            expected_end_monotonic=(
                started_monotonic + duration + _COMPLETION_GRACE_SECONDS
            ),
            last_confirmed_monotonic=now,
            duration=duration,
            restored=True,
        )
        self._operation = operation
        self._monitor_task = self.hass.async_create_background_task(
            self._async_monitor_recording(operation),
            f"recamera_pro.capture.{capture_id}",
        )

    async def async_shutdown(self) -> None:
        """Cancel local waiters without issuing an implicit device stop."""
        for task in (self._snapshot_task, self._monitor_task):
            if task is None or task.done():
                continue
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._snapshot_task = None
        self._monitor_task = None
        if self._operation is not None:
            self._operation.completion_event.set()
            self._operation = None
        self._snapshot_results.clear()
        if self._store is not None:
            for method_name in (
                "_async_cleanup_delay_listener",
                "_async_cleanup_final_write_listener",
            ):
                cleanup = getattr(self._store, method_name, None)
                if callable(cleanup):
                    cleanup()
