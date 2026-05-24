"""Tests for the CalDAV coordinator concurrency cap."""

import asyncio
from unittest.mock import MagicMock

import pytest

from homeassistant.components.caldav.coordinator import (
    MAX_CONCURRENT_REQUESTS,
    REQUEST_SEMAPHORE,
    CalDavUpdateCoordinator,
    close_idle_connections,
)
from homeassistant.components.caldav.todo import (
    REQUEST_SEMAPHORE as TODO_REQUEST_SEMAPHORE,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


def _build_coordinator(
    hass: HomeAssistant, calendar: MagicMock
) -> CalDavUpdateCoordinator:
    """Build a coordinator suitable for direct unit testing."""
    return CalDavUpdateCoordinator(
        hass=hass,
        entry=None,
        calendar=calendar,
        days=1,
        include_all_day=True,
        search=None,
    )


async def test_concurrent_searches_are_capped(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Many concurrent refreshes must not exceed MAX_CONCURRENT_REQUESTS in-flight searches.

    Regression test for thread-pool starvation seen on instances with many
    calendars (e.g. iCloud accounts with 30+ shared calendars): without the
    cap, every coordinator fires its first refresh in parallel at boot and
    saturates the executor.

    Replaces ``hass.async_add_executor_job`` with a coroutine so that
    concurrency tracking and the release barrier stay on the event loop —
    blocking real executor threads inside a per-test timeout window is
    fragile and can starve the worker's thread pool.
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

    num_calendars = 20
    coordinators: list[CalDavUpdateCoordinator] = []
    for idx in range(num_calendars):
        calendar = MagicMock()
        calendar.name = f"cal-{idx}"
        calendar.client = MagicMock(session=MagicMock())
        coordinators.append(_build_coordinator(hass, calendar))

    now = dt_util.now()
    tasks = [
        asyncio.create_task(c.async_get_events(hass, now, now)) for c in coordinators
    ]

    # The semaphore must let exactly MAX_CONCURRENT_REQUESTS pass and block
    # the rest on `__aenter__`.
    await asyncio.wait_for(enter_event.wait(), timeout=5.0)

    # Give the loop additional ticks so any over-cap searches would have
    # had time to start. A correctly-capped semaphore will keep them blocked.
    for _ in range(50):
        await asyncio.sleep(0)

    assert peak == MAX_CONCURRENT_REQUESTS, (
        f"semaphore failed to cap concurrency: peak={peak} "
        f"(expected {MAX_CONCURRENT_REQUESTS})"
    )

    release_event.set()
    await asyncio.gather(*tasks)


async def test_request_semaphore_module_singleton() -> None:
    """The semaphore is a module-level singleton shared by every entity."""
    assert isinstance(REQUEST_SEMAPHORE, asyncio.Semaphore)
    # Calendar coordinator and todo entity must reference the *same* object,
    # otherwise the cap wouldn't be global across both platforms.
    assert REQUEST_SEMAPHORE is TODO_REQUEST_SEMAPHORE


async def test_search_closes_idle_connections(hass: HomeAssistant) -> None:
    """After each search, idle urllib3 connections are dropped to prevent CLOSE_WAIT buildup."""
    calendar = MagicMock()
    calendar.name = "cal"
    session = MagicMock()
    calendar.client = MagicMock(session=session)
    calendar.search = MagicMock(return_value=[])

    coordinator = _build_coordinator(hass, calendar)
    now = dt_util.now()
    await coordinator.async_get_events(hass, now, now)

    session.close.assert_called_once()


async def test_search_closes_idle_connections_on_error(hass: HomeAssistant) -> None:
    """Idle connections are still closed when the search itself raises."""
    calendar = MagicMock()
    calendar.name = "cal"
    session = MagicMock()
    calendar.client = MagicMock(session=session)
    calendar.search = MagicMock(side_effect=RuntimeError("boom"))

    coordinator = _build_coordinator(hass, calendar)
    now = dt_util.now()
    with pytest.raises(RuntimeError):
        await coordinator.async_get_events(hass, now, now)

    session.close.assert_called_once()


def test_close_idle_connections_handles_no_session() -> None:
    """Helper is a no-op when the DAVClient has no ``session`` attribute yet."""
    client = MagicMock(spec=[])  # no `session` attr
    close_idle_connections(client)  # must not raise
