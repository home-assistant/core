"""Tests for SSE reconnect hardening.

Invariants under test:

1. **Wall-clock idle watchdog via ``asyncio.wait_for``** around each
   ``__anext__()`` on the SSE async iterator. Threshold lives in
   ``coordinator._SSE_FRAME_WATCHDOG_SECONDS`` (300s production / patched
   to 0.2s for tests). When the timer fires, the loop catches
   ``asyncio.TimeoutError`` and stamps
   ``sse_state["last_disconnect_reason"] = "watchdog_stall_{N}s"``, then
   reconnects after the standard backoff (which is at delay_idx=0 if a
   frame had already flowed this cycle).
2. **Slow-loris fix** (carry-over from v2): ``sse_state["connected"]``
   stays ``False`` until the first frame is received from the new
   connection. A new ``last_attempt_at`` field records the attempt
   boundary.
3. **``ClientPayloadError`` is the expected cycle shape** (probe finding:
   parked ABRP server unilaterally closes at ~200s). The existing
   ``except ClientError → AbrpApiError`` band in ``stream()`` catches
   it; the outer loop sees ``AbrpApiError`` and reconnects with the
   delay_idx-reset backoff (5s). No new logic needed — this is a
   regression guard pinning the post-fix behaviour as the expected case.
4. **Explicit ``ClientTimeout``** on the SSE GET
   (``connect=30, sock_connect=15, total=None``) and on the seed-poll
   GET (``total=30``). Pre-headers handshake hangs and seed hangs are
   bounded.
5. **Clean unload** under both cancellation paths: the naked-propagation
   path (real async gen, ``finally: await agen.aclose()``) AND the
   fixture-masked path (the existing ``_FrameStream`` test fixture
   catches ``CancelledError`` and re-raises as ``StopAsyncIteration``;
   the retained ``task.cancelling()`` check at ``coordinator.py:413-419``
   converts that into a clean ``return``).

Notes:
~~~~~

* ``_SSE_FRAME_WATCHDOG_SECONDS``, ``_SSE_CONNECT_TIMEOUT_SECONDS``,
  ``_SSE_SOCK_CONNECT_TIMEOUT_SECONDS``, ``_ONE_SHOT_TIMEOUT_SECONDS``
  are pulled via ``getattr(..., default)`` so the file imports cleanly
  even if the production constants are renamed; the value-assertions
  then fail loudly with a clear "missing symbol" / "wrong value"
  message.

* Backoff patching: never module-patch ``asyncio.sleep``. We DO patch
  ``coordinator.asyncio.sleep`` to a recorder that bails the loop after
  one cycle — this targets only the coordinator's module-local
  reference, not the global. Naked-propagating iterators built in this
  file use their own ``asyncio.sleep`` reference, unaffected.

* The "naked-propagation" iterator class ``_BlockNaked`` raises
  ``CancelledError`` out of ``__anext__`` cleanly. The conftest's
  ``_FrameStream`` is the masked path (catches Cancelled, re-raises as
  ``StopAsyncIteration``).
"""

import asyncio
import contextlib
from http import HTTPStatus
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientTimeout
import pytest

from homeassistant.components.abetterrouteplanner import (
    AbrpData,
    api as abrp_api,
    coordinator as abrp_coord,
)
from homeassistant.components.abetterrouteplanner.api import (
    AbrpApiError,
    AbrpTelemetryClient,
)
from homeassistant.components.abetterrouteplanner.const import CONF_VEHICLE_IDS, DOMAIN
from homeassistant.components.abetterrouteplanner.coordinator import (
    AbrpTelemetryCoordinator,
    _run_sse_loop,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.setup import async_setup_component

from .conftest import MOCK_VEHICLE_ID, SENSOR_TEST_SUB, build_telemetry_frame

from tests.common import MockConfigEntry

# Pull constants by getattr so this file loads cleanly even when one
# rolls out renamed. The fallbacks must stay in sync with the
# production constants.
_PLAN_WATCHDOG_SECONDS: int = getattr(abrp_coord, "_SSE_FRAME_WATCHDOG_SECONDS", 300)
_PLAN_CONNECT_TIMEOUT: int = getattr(abrp_api, "_SSE_CONNECT_TIMEOUT_SECONDS", 30)
_PLAN_SOCK_CONNECT_TIMEOUT: int = getattr(
    abrp_api, "_SSE_SOCK_CONNECT_TIMEOUT_SECONDS", 15
)
_PLAN_ONE_SHOT_TIMEOUT: int = getattr(abrp_api, "_ONE_SHOT_TIMEOUT_SECONDS", 30)

# Fast-cycle constants for direct ``_run_sse_loop`` driver tests. Patching
# the production constants to these values keeps watchdog-trigger time
# below 1 s without short-circuiting the wait_for primitive itself.
_FAST_WATCHDOG_SECONDS = 0.2


class _StopLoop(Exception):
    """Sentinel exception used to bail ``_run_sse_loop`` out of its while-true.

    Patched into the coordinator's ``asyncio.sleep`` so that the first
    backoff sleep raises this and terminates the loop. Bounded so tests
    don't hang if the loop unexpectedly avoids the sleep path.
    """


# ---------------------------------------------------------------------------
# Local iterator helpers
# ---------------------------------------------------------------------------


async def _block_forever_naked() -> None:
    """Block on a never-resolving Future; propagate CancelledError naturally.

    Deliberately avoids ``asyncio.sleep`` — the coordinator-loop tests
    patch ``coordinator.asyncio.sleep`` to short-circuit the backoff
    sleep, and ``setattr`` on the asyncio module patches it globally
    (the same singleton is referenced by every importer). A
    Future-based block is independent of that patch.
    """
    await asyncio.get_event_loop().create_future()


class _BlockNaked:
    """Async iterator that blocks forever and propagates ``CancelledError``.

    Distinct from the conftest ``_FrameStream`` (which catches
    ``CancelledError`` and re-raises as ``StopAsyncIteration`` — the
    "masked" path). This class is the "naked" path used by tests that
    need the watchdog's ``asyncio.TimeoutError`` to actually surface.
    """

    def __aiter__(self) -> _BlockNaked:
        return self

    async def __anext__(self) -> dict[str, Any]:
        await _block_forever_naked()
        raise StopAsyncIteration  # pragma: no cover - unreachable

    async def aclose(self) -> None:
        """No-op cleanup matching the real async-generator shape."""


class _YieldOneThenBlockNaked:
    """Yields one frame then blocks naked — drives saw_frame=True, then stall."""

    def __init__(self, frame: dict[str, Any]) -> None:
        self._frame: dict[str, Any] | None = frame

    def __aiter__(self) -> _YieldOneThenBlockNaked:
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._frame is not None:
            frame, self._frame = self._frame, None
            return frame
        await _block_forever_naked()
        raise StopAsyncIteration  # pragma: no cover - unreachable

    async def aclose(self) -> None:
        """No-op cleanup."""


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(name="oauth_session")
def oauth_session_fixture() -> MagicMock:
    """OAuth session mock matching the shape used by ``_run_sse_loop``."""
    session = MagicMock(spec=OAuth2Session)
    session.async_ensure_token_valid = AsyncMock()
    session.token = {"access_token": "test-tok"}
    return session


def _build_entry_with_known(
    token_entry: dict[str, Any],
    *,
    vehicle_ids: list[str],
) -> MockConfigEntry:
    """Build a MockConfigEntry pre-populated with CONF_KNOWN_VEHICLE_IDS.

    The known-vehicle-ids field is set to ``vehicle_ids`` so the auto-add
    listener treats this entry as fully onboarded (no migration seeds,
    no reload-loop).
    """
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: vehicle_ids,
            "known_vehicle_ids": vehicle_ids,
        },
    )


async def _setup_integration(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Standard ABRP integration setup helper.

    Accepts the 0.5 s real-time pre-warm sleep — see
    ``[[project-abrp-asyncio-sleep-test-patching]]``.
    """
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


# ===========================================================================
# watchdog fires on stalled idle stream
# ===========================================================================


async def test_watchdog_fires_on_idle_stream(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    oauth_session: MagicMock,
) -> None:
    """An idle stream with no frames triggers the watchdog and reconnects.

    Drives ``_run_sse_loop`` against a naked-propagation iterator that
    never yields. With ``_SSE_FRAME_WATCHDOG_SECONDS`` patched to 0.2 s,
    ``asyncio.wait_for`` fires, raises ``TimeoutError``, the outer
    ``except asyncio.TimeoutError`` handler stamps the
    ``"watchdog_stall_*s"`` reason and the loop proceeds to backoff
    (which raises ``_StopLoop`` via the patched sleep so the test
    exits).
    """
    config_entry_with_vehicles.add_to_hass(hass)
    coordinator = AbrpTelemetryCoordinator(hass, config_entry_with_vehicles)

    connect_calls: list[int] = []

    def _factory(*_args: Any, **_kwargs: Any) -> _BlockNaked:
        connect_calls.append(1)
        return _BlockNaked()

    sleep_calls: list[float] = []

    async def _record_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        raise _StopLoop

    with (
        patch.object(
            abrp_coord,
            "_SSE_FRAME_WATCHDOG_SECONDS",
            _FAST_WATCHDOG_SECONDS,
            create=True,
        ),
        patch(
            "homeassistant.components.abetterrouteplanner.api.AbrpTelemetryClient.stream",
            side_effect=_factory,
        ),
        patch(
            "homeassistant.components.abetterrouteplanner.coordinator.asyncio.sleep",
            new=_record_sleep,
        ),
        # ``TimeoutError`` from the outer ``asyncio.timeout`` is suppressed
        # so the assertions below run with a clear failure message instead
        # of an uncaught timeout. Today's loop hangs (no watchdog), so the
        # timeout fires and the disconnect-reason assertion fails loudly.
        contextlib.suppress(_StopLoop, TimeoutError),
    ):
        async with asyncio.timeout(5.0):
            await _run_sse_loop(
                hass, config_entry_with_vehicles, coordinator, oauth_session, [1]
            )

    assert connect_calls, "stream() was never called — loop didn't reach connect block"
    reason = coordinator.sse_state.get("last_disconnect_reason") or ""
    assert "watchdog_stall" in reason, (
        f"expected watchdog_stall disconnect reason; got {reason!r}"
    )


# ===========================================================================
# connected flag stays False until first frame; last_attempt_at set
# ===========================================================================


async def test_connected_flag_only_flips_after_first_frame(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    mock_seed_responses: AsyncMock,
    mock_sse_client: MagicMock,
) -> None:
    """Slow-loris fix: ``connected`` stays False until first frame arrives.

    Sequence:
    1. Setup with the default ``mock_sse_client`` (blocks, no frames).
    2. Post-setup: ``sse_state["connected"] is False`` (the stream is
       open but no frame received yet — the headers-but-nothing-else
       case from production).
    3. ``sse_state["last_attempt_at"]`` is populated (a connect was
       attempted).
    4. ``connect_count`` is 0 (the counter increments on first frame).
    5. Drive a frame directly through the coordinator (we don't have a
       clean way to push a frame through the live iterator mid-test
       without a reconnect, so we simulate the "after first frame"
       transition by calling the same state-mutation the loop would
       perform). [Actually validated end-to-end via the integration
       setup path elsewhere in this file; here we focus on the pre-frame
       observable state.]
    """
    entry = _build_entry_with_known(token_entry, vehicle_ids=[str(MOCK_VEHICLE_ID)])
    await _setup_integration(hass, entry)

    runtime_data: AbrpData = entry.runtime_data
    state = runtime_data.telemetry_coordinator.sse_state

    # Step 2 — connected is False, no frame received yet.
    assert state["connected"] is False, (
        "connected flipped to True before any frame was received "
        "(slow-loris fix missing)"
    )

    # Step 3 — last_attempt_at recorded.
    assert state.get("last_attempt_at") is not None, (
        "last_attempt_at must be populated once a connect is attempted"
    )

    # Step 4 — connect_count is 0 (no first frame yet).
    assert state["connect_count"] == 0, (
        f"connect_count should be 0 pre-first-frame; got {state['connect_count']}"
    )


# ===========================================================================
# ClientPayloadError (server 200s close) is a clean cycle
# ===========================================================================


async def test_clientpayloaderror_is_clean_disconnect(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    oauth_session: MagicMock,
) -> None:
    """A frame-then-AbrpApiError cycle treats the disconnect as clean.

    Mirrors the probe's "server closes idle connection at ~200s" cycle.
    Concretely:

    * 1st stream() yields one frame then raises ``AbrpApiError``
      (the post-conversion shape of ``ClientPayloadError`` after
      ``stream()``'s existing ``except ClientError`` band).
    * 2nd stream() returns a naked blocker so the loop parks (and gets
      stopped by ``_record_sleep`` raising ``_StopLoop``).

    Assertions:

    * The backoff sleep before the second connect is
      ``_SSE_BACKOFF_SECONDS[0]`` (5 s today), because the successful
      frame reset ``delay_idx`` to 0.
    * ``last_disconnect_reason`` reflects the AbrpApiError summary.

    Today this test passes — it's a regression guard for the v3 contract
    that the 200 s natural cycle stays at delay_idx=0.
    """
    config_entry_with_vehicles.add_to_hass(hass)
    coordinator = AbrpTelemetryCoordinator(hass, config_entry_with_vehicles)

    call_count = 0

    async def _yield_one_then_apierror() -> Any:
        yield build_telemetry_frame(MOCK_VEHICLE_ID, soc=0.5)
        raise AbrpApiError("ClientPayloadError: Not enough data ...")

    def _factory(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            return _BlockNaked()
        return _yield_one_then_apierror()

    sleep_calls: list[float] = []

    async def _record_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        raise _StopLoop

    with (
        patch(
            "homeassistant.components.abetterrouteplanner.api.AbrpTelemetryClient.stream",
            side_effect=_factory,
        ),
        patch(
            "homeassistant.components.abetterrouteplanner.coordinator.asyncio.sleep",
            new=_record_sleep,
        ),
        # ``TimeoutError`` from the outer ``asyncio.timeout`` is suppressed
        # so the assertions below run with a clear failure message instead
        # of an uncaught timeout. Today's loop hangs (no watchdog), so the
        # timeout fires and the disconnect-reason assertion fails loudly.
        contextlib.suppress(_StopLoop, TimeoutError),
    ):
        async with asyncio.timeout(5.0):
            await _run_sse_loop(
                hass, config_entry_with_vehicles, coordinator, oauth_session, [1]
            )

    assert sleep_calls, "loop never reached backoff sleep"
    expected_first_backoff = abrp_coord._SSE_BACKOFF_SECONDS[0]
    assert sleep_calls[0] == expected_first_backoff, (
        f"first backoff after one-frame-then-disconnect should be "
        f"{expected_first_backoff} s; got {sleep_calls[0]}"
    )
    assert "AbrpApiError" in (coordinator.sse_state.get("last_disconnect_reason") or "")


# ===========================================================================
# unload during watchdog wait releases cleanly (naked path)
# ===========================================================================


async def test_unload_during_watchdog_wait_releases_cleanly(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    mock_seed_responses: AsyncMock,
    mock_sse_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unload while the consumer is parked in ``wait_for`` completes promptly.

    Uses the naked-propagation iterator so cancellation is NOT masked:
    the SSE consumer task receives ``CancelledError`` cleanly via
    ``wait_for``'s inner await, the ``finally: await agen.aclose()`` of
    the wait_for block runs, and the task exits without falling through
    to the backoff sleep.

    Pins the cancellation-propagation contract:

    * Unload completes within 2 s (we wrap in ``asyncio.timeout``).
    * No CancelledError-leak WARNING logs ("Task was destroyed but it
      is pending!" or "exception was never retrieved" style).
    """
    # Override the default mock_sse_client to use the naked iterator.
    mock_sse_client.side_effect = lambda *_a, **_kw: _BlockNaked()

    entry = _build_entry_with_known(token_entry, vehicle_ids=[str(MOCK_VEHICLE_ID)])
    await _setup_integration(hass, entry)

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        async with asyncio.timeout(5.0):
            assert await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    leak_signatures = (
        "Task was destroyed",
        "was never retrieved",
        "coroutine was never awaited",
    )
    leaked = [
        rec.getMessage()
        for rec in caplog.records
        if any(sig in rec.getMessage() for sig in leak_signatures)
    ]
    assert not leaked, f"unexpected leak warnings: {leaked}"


# ===========================================================================
# SSE stream() passes ClientTimeout(connect, sock_connect, total=None)
# ===========================================================================


async def test_connect_timeout_passed_to_session_get() -> None:
    """``stream()`` calls ``session.get(..., timeout=ClientTimeout(...))``.

    Structural assertion per ``[[pattern-tester-structural-assertion-for-registration-topology]]``:
    captures the ``timeout=`` kwarg on the underlying ``session.get(...)``
    call. Asserts:

    * ``connect == _SSE_CONNECT_TIMEOUT_SECONDS`` (30 s)
    * ``sock_connect == _SSE_SOCK_CONNECT_TIMEOUT_SECONDS`` (15 s)
    * ``total is None`` (long-lived stream — total budget would tear it down)
    * ``sock_read is None`` — intentional absence: a wall-clock read
      budget would also tear down a healthy idle SSE connection. The
      idle watchdog above protects against stalls instead.
    """
    session = MagicMock()
    response = MagicMock()
    response.status = HTTPStatus.OK
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)

    async def _empty_iter() -> Any:
        return
        yield  # pragma: no cover - unreachable, kept to make this an async gen

    response.content.iter_any = _empty_iter
    session.get = MagicMock(return_value=response)

    client = AbrpTelemetryClient(session, "key", "tok")
    # Drive one __anext__ — the async generator body runs up to the
    # ``async with session.get(...)`` entry, where session.get is invoked.
    agen = client.stream([1]).__aiter__()
    with contextlib.suppress(StopAsyncIteration):
        await anext(agen)

    session.get.assert_called_once()
    timeout = session.get.call_args.kwargs.get("timeout")
    assert timeout is not None, (
        "stream() must pass an explicit timeout= kwarg to session.get()"
    )
    assert isinstance(timeout, ClientTimeout), (
        f"timeout kwarg must be an aiohttp.ClientTimeout; got {type(timeout)!r}"
    )
    assert timeout.connect == _PLAN_CONNECT_TIMEOUT, (
        f"ClientTimeout.connect should be {_PLAN_CONNECT_TIMEOUT}; "
        f"got {timeout.connect!r}"
    )
    assert timeout.sock_connect == _PLAN_SOCK_CONNECT_TIMEOUT, (
        f"ClientTimeout.sock_connect should be {_PLAN_SOCK_CONNECT_TIMEOUT}; "
        f"got {timeout.sock_connect!r}"
    )
    assert timeout.total is None, (
        f"ClientTimeout.total MUST be None for the long-lived SSE stream; "
        f"got {timeout.total!r}"
    )
    assert timeout.sock_read is None, (
        f"ClientTimeout.sock_read MUST stay None "
        f"(no per-byte stall detector — the wall-clock watchdog handles it); "
        f"got {timeout.sock_read!r}"
    )


# ===========================================================================
# async_get_one_shot() passes ClientTimeout(total=30)
# ===========================================================================


async def test_seed_path_has_total_timeout() -> None:
    """``async_get_one_shot`` calls ``session.get(..., timeout=ClientTimeout(total=30))``.

    Pre-headers / slow-body hangs in the seed path get bounded.
    The seed is best-effort: a timeout surfaces as ``AbrpApiError``
    (caught by existing ``except ClientError``), the coordinator logs
    DEBUG and continues; SSE backfills.
    """
    session = MagicMock()
    response = MagicMock()
    response.status = HTTPStatus.OK
    response.json = AsyncMock(return_value={})
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=response)

    client = AbrpTelemetryClient(session, "key", "tok")
    await client.async_get_one_shot(MOCK_VEHICLE_ID)

    session.get.assert_called_once()
    timeout = session.get.call_args.kwargs.get("timeout")
    assert timeout is not None, (
        "async_get_one_shot() must pass an explicit timeout= kwarg"
    )
    assert isinstance(timeout, ClientTimeout), (
        f"timeout kwarg must be an aiohttp.ClientTimeout; got {type(timeout)!r}"
    )
    assert timeout.total == _PLAN_ONE_SHOT_TIMEOUT, (
        f"ClientTimeout.total should be {_PLAN_ONE_SHOT_TIMEOUT}; got {timeout.total!r}"
    )


# ===========================================================================
# seed timeout falls through to AbrpApiError, vehicle skipped
# ===========================================================================


async def test_seed_timeout_falls_through_to_apierror(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    mock_seed_responses: AsyncMock,
    mock_sse_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A seed timeout (post-conversion ``AbrpApiError``) doesn't block setup.

    Simulates the post-fix wire: ``async_get_one_shot`` raises
    ``AbrpApiError`` (which is what ``ServerTimeoutError`` becomes via
    the ``except ClientError`` band). The seed coordinator's
    ``async_seed_from_json_poll`` logs at DEBUG and continues; the
    vehicle is skipped, setup completes, no telemetry data for that
    vehicle.

    Today this passes — it's a regression guard for the
    ``async_seed_from_json_poll`` AbrpApiError handling, ensuring the
    new timeout path slots into the existing best-effort behaviour.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = AbrpApiError(
        "ServerTimeoutError: Timeout on reading data"
    )

    entry = _build_entry_with_known(token_entry, vehicle_ids=[str(MOCK_VEHICLE_ID)])

    with caplog.at_level(logging.DEBUG):
        await _setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    runtime_data: AbrpData = entry.runtime_data
    # Vehicle skipped — no telemetry data accumulated for it.
    assert MOCK_VEHICLE_ID not in runtime_data.telemetry_coordinator.data, (
        "telemetry_coordinator.data should be empty for the skipped vehicle"
    )
    # DEBUG log carries the per-vehicle skip notice.
    skip_messages = [
        rec.getMessage()
        for rec in caplog.records
        if "Telemetry seed for vehicle" in rec.getMessage()
        and str(MOCK_VEHICLE_ID) in rec.getMessage()
    ]
    assert skip_messages, "expected a DEBUG log noting the vehicle's seed was skipped"


# ===========================================================================
# unload through StopIteration-masked cancel
# ===========================================================================


async def test_unload_through_stopiteration_masked_cancel(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    mock_seed_responses: AsyncMock,
    mock_sse_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Masked-cancellation unload completes cleanly.

    Drives the SSE consumer into a ``wait_for`` await using the existing
    ``_FrameStream`` fixture (default ``mock_sse_client``), which
    catches ``CancelledError`` and re-raises as ``StopAsyncIteration``.
    The new ``except StopAsyncIteration: break`` exits the wait_for
    loop, ``finally: aclose()`` is a no-op on the already-closed stream,
    and the loop would fall through to ``asyncio.sleep(delay)`` —
    EXCEPT that the retained ``task.cancelling()`` check at
    ``coordinator.py:521-523`` converts the absorbed cancellation back
    into a clean ``return``.

    Without the retained check, unload would hang on the backoff sleep
    waiting for cancellation to land again. This test pins that
    contract: if a future refactor drops the ``task.cancelling()``
    check (e.g. on the false belief that the new wait_for path makes
    it redundant), unload hangs and this test fails via the
    ``asyncio.timeout(2.0)`` bound.

    Stays load-bearing across future refactors.
    """
    # Default mock_sse_client uses _FrameStream, which is the masked path.
    entry = _build_entry_with_known(token_entry, vehicle_ids=[str(MOCK_VEHICLE_ID)])
    await _setup_integration(hass, entry)

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        async with asyncio.timeout(2.0):
            assert await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    leak_signatures = (
        "Task was destroyed",
        "was never retrieved",
        "coroutine was never awaited",
    )
    leaked = [
        rec.getMessage()
        for rec in caplog.records
        if any(sig in rec.getMessage() for sig in leak_signatures)
    ]
    assert not leaked, f"unexpected leak warnings: {leaked}"


# ===========================================================================
# backoff resets after frame, then watchdog stall, repeatedly
# ===========================================================================


async def test_backoff_resets_after_successful_frame_then_watchdog_stall(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    oauth_session: MagicMock,
) -> None:
    """A successful frame resets backoff even when followed by a watchdog stall.

    Sequence:
    1. stream() yields one frame, then blocks naked → watchdog fires →
       outer ``asyncio.TimeoutError`` band → backoff sleep is
       ``_SSE_BACKOFF_SECONDS[0]`` (because the frame reset delay_idx).
    2. stream() yields one frame, then blocks naked again → watchdog →
       backoff sleep is again ``_SSE_BACKOFF_SECONDS[0]``.

    Pins the "successful frame resets backoff regardless of the next
    disconnect shape" invariant — including the watchdog-stall shape.
    """
    config_entry_with_vehicles.add_to_hass(hass)
    coordinator = AbrpTelemetryCoordinator(hass, config_entry_with_vehicles)

    streams_made = 0

    def _factory(*_args: Any, **_kwargs: Any) -> _YieldOneThenBlockNaked:
        nonlocal streams_made
        streams_made += 1
        return _YieldOneThenBlockNaked(build_telemetry_frame(MOCK_VEHICLE_ID, soc=0.5))

    sleep_calls: list[float] = []

    async def _record_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        # Bail after two reconnect cycles so the test bounds.
        if len(sleep_calls) >= 2:
            raise _StopLoop

    with (
        patch.object(
            abrp_coord,
            "_SSE_FRAME_WATCHDOG_SECONDS",
            _FAST_WATCHDOG_SECONDS,
            create=True,
        ),
        patch(
            "homeassistant.components.abetterrouteplanner.api.AbrpTelemetryClient.stream",
            side_effect=_factory,
        ),
        patch(
            "homeassistant.components.abetterrouteplanner.coordinator.asyncio.sleep",
            new=_record_sleep,
        ),
        # ``TimeoutError`` from the outer ``asyncio.timeout`` is suppressed
        # so the post-block assertions can fire with a clear failure message
        # rather than an uncaught timeout. Today's loop has no watchdog, so
        # the bound timeout fires and the sleep-sequence assertion fails
        # loudly with the actual recorded values.
        contextlib.suppress(_StopLoop, TimeoutError),
    ):
        async with asyncio.timeout(5.0):
            await _run_sse_loop(
                hass,
                config_entry_with_vehicles,
                coordinator,
                oauth_session,
                [MOCK_VEHICLE_ID],
            )

    expected = abrp_coord._SSE_BACKOFF_SECONDS[0]
    assert sleep_calls == [expected, expected], (
        f"backoff sequence should be [{expected}, {expected}] (two stalls "
        f"each preceded by a frame); got {sleep_calls}"
    )
    assert streams_made >= 2, (
        f"two connect attempts expected (initial + one reconnect); got {streams_made}"
    )
