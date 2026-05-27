"""Tests for the CalDAV coordinator concurrency cap and unload-time cleanup."""

import asyncio
import contextlib
from unittest.mock import MagicMock

import pytest

from homeassistant.components.caldav import CalDavRuntimeData
from homeassistant.components.caldav.coordinator import (
    MAX_CONCURRENT_REQUESTS,
    CalDavUpdateCoordinator,
    close_client_session,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


def _build_coordinator(
    hass: HomeAssistant,
    calendar: MagicMock,
    semaphore: asyncio.Semaphore | None,
) -> CalDavUpdateCoordinator:
    """Build a coordinator suitable for direct unit testing.

    Passing ``semaphore=None`` exercises the legacy-YAML code path where no
    config entry (and therefore no per-entry semaphore) exists.
    """
    if semaphore is None:
        entry = None
    else:
        entry = MagicMock()
        entry.runtime_data = CalDavRuntimeData(
            client=MagicMock(),
            request_semaphore=semaphore,
        )
    return CalDavUpdateCoordinator(
        hass=hass,
        entry=entry,
        calendar=calendar,
        days=1,
        include_all_day=True,
        search=None,
    )


async def test_concurrent_searches_are_capped(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A per-entry semaphore caps in-flight searches at MAX_CONCURRENT_REQUESTS.

    Regression test for thread-pool starvation seen on instances with many
    calendars (e.g. iCloud accounts with 30+ shared calendars): without the
    cap, every coordinator fires its first refresh in parallel at boot and
    saturates the executor.

    Replaces ``hass.async_add_executor_job`` with a coroutine so concurrency
    tracking and the release barrier stay on the event loop — blocking real
    executor threads inside a per-test timeout window is fragile and can
    starve the worker's thread pool.
    """
    in_flight = 0
    peak = 0
    enter_event = asyncio.Event()
    release_event = asyncio.Event()

    async def fake_executor_job(_func, *_args, **_kwargs):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        if in_flight >= MAX_CONCURRENT_REQUESTS:
            enter_event.set()
        try:
            await release_event.wait()
            return []
        finally:
            in_flight -= 1

    monkeypatch.setattr(hass, "async_add_executor_job", fake_executor_job)

    # Single per-entry semaphore shared across this test's coordinators —
    # constructed locally so the test is isolated from any other CalDAV
    # tests sharing the same pytest worker.
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    num_calendars = 20
    coordinators: list[CalDavUpdateCoordinator] = []
    for idx in range(num_calendars):
        calendar = MagicMock()
        calendar.name = f"cal-{idx}"
        coordinators.append(_build_coordinator(hass, calendar, semaphore))

    now = dt_util.now()
    tasks = [
        asyncio.create_task(c.async_get_events(hass, now, now)) for c in coordinators
    ]

    try:
        # The semaphore must let exactly MAX_CONCURRENT_REQUESTS pass and
        # block the rest on ``__aenter__``.
        await asyncio.wait_for(enter_event.wait(), timeout=5.0)

        # Give the loop additional ticks so any over-cap searches would have
        # had time to start. A correctly-capped semaphore keeps them blocked.
        for _ in range(50):
            await asyncio.sleep(0)

        assert peak == MAX_CONCURRENT_REQUESTS, (
            f"semaphore failed to cap concurrency: peak={peak} "
            f"(expected {MAX_CONCURRENT_REQUESTS})"
        )
    finally:
        # Always release waiters and gather tasks so a failed assertion
        # cannot leak pending tasks or wedge the test worker.
        release_event.set()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_per_entry_semaphores_are_independent(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A saturated semaphore on entry A does not block entry B.

    The whole point of moving from a module-global semaphore to a per-entry
    one is that a slow account cannot delay updates for an unrelated
    account. Verify the observable behavior — entry B's search completes
    while entry A's search is held off by an externally-saturated semaphore.
    """
    release_b = asyncio.Event()
    # Use explicit sentinel callables for search rather than relying on
    # MagicMock's auto-generated child-mock caching for identity routing.
    search_a = MagicMock(name="search_a")
    search_b = MagicMock(name="search_b")
    cal_a = MagicMock()
    cal_a.name = "a"
    cal_a.search = search_a
    cal_b = MagicMock()
    cal_b.name = "b"
    cal_b.search = search_b

    async def fake_executor_job(func, *_args, **_kwargs):
        # Route by the partial's underlying ``calendar.search`` reference. The
        # test keeps entry B's job pending until it explicitly releases it,
        # while entry A's job must never reach the executor at all (its
        # semaphore is fully saturated by the test).
        bound = getattr(func, "func", None)
        if bound is search_b:
            await release_b.wait()
            return []
        if bound is search_a:
            pytest.fail("Entry A reached the executor despite saturated semaphore")
        return []

    monkeypatch.setattr(hass, "async_add_executor_job", fake_executor_job)

    sem_a = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    sem_b = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    # Saturate sem_a externally so coord_a is fully blocked at acquisition.
    for _ in range(MAX_CONCURRENT_REQUESTS):
        await sem_a.acquire()

    coord_a = _build_coordinator(hass, cal_a, sem_a)
    coord_b = _build_coordinator(hass, cal_b, sem_b)

    now = dt_util.now()
    task_a = asyncio.create_task(coord_a.async_get_events(hass, now, now))
    task_b = asyncio.create_task(coord_b.async_get_events(hass, now, now))

    try:
        # B can complete: its semaphore has permits and the executor releases.
        release_b.set()
        await asyncio.wait_for(task_b, timeout=5.0)

        # Give the loop ticks so that if sem_a were shared, A would have
        # raced past acquisition by now. It must not.
        for _ in range(50):
            await asyncio.sleep(0)

        assert not task_a.done(), (
            "Entry A's task completed despite sem_a being saturated — "
            "the semaphore is not actually per-entry"
        )
    finally:
        task_a.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task_a


async def test_legacy_yaml_coordinator_has_no_semaphore(
    hass: HomeAssistant,
) -> None:
    """Coordinators created from YAML config (no entry) skip the per-entry cap.

    Observable behavior: ``async_get_events`` completes without raising even
    though no per-entry semaphore is wired up. If the coordinator tried to
    enter ``None`` as an async context manager, this would error.
    """
    calendar = MagicMock()
    calendar.search = MagicMock(return_value=[])
    coordinator = _build_coordinator(hass, calendar, semaphore=None)
    now = dt_util.now()
    await coordinator.async_get_events(hass, now, now)
    # The search executor job is dispatched only if the coordinator's
    # ``_semaphore_ctx`` returned an async-enterable object (``nullcontext``
    # for the no-entry path). If it had returned ``None``, ``async with``
    # would have raised before reaching this call.
    calendar.search.assert_called_once()


def test_close_client_session_handles_no_session() -> None:
    """Helper is a no-op when the DAVClient has no ``session`` attribute yet."""
    client = MagicMock(spec=[])  # no `session` attr
    close_client_session(client)  # must not raise


def test_close_client_session_calls_session_close() -> None:
    """Helper closes the underlying niquests Session exactly once."""
    client = MagicMock()
    close_client_session(client)
    client.session.close.assert_called_once()
