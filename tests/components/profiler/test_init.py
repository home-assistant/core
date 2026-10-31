"""Test the Profiler config flow."""

import asyncio
from asyncio.events import Handle
import binascii
from datetime import datetime, timedelta
from functools import lru_cache, partial
import logging
import os
from pathlib import Path
import socket
import time
from typing import Any
from unittest.mock import patch
import zlib

from freezegun.api import FrozenDateTimeFactory
from lru import LRU
import objgraph
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.profiler.const import DOMAIN
from homeassistant.components.profiler.loop_timing import (
    DEFAULT_THRESHOLD_MS,
    LoopTiming,
    format_report,
)
from homeassistant.components.profiler.services import (
    _LRU_CACHE_WRAPPER_OBJECT,
    _SQLALCHEMY_LRU_OBJECT,
    CONF_SECONDS,
    CONF_THRESHOLD,
    SERVICE_DUMP_LOG_OBJECTS,
    SERVICE_DUMP_LOOP_TIMING,
    SERVICE_DUMP_SOCKETS,
    SERVICE_LOG_CURRENT_TASKS,
    SERVICE_LOG_EVENT_LOOP_SCHEDULED,
    SERVICE_LOG_THREAD_FRAMES,
    SERVICE_LRU_STATS,
    SERVICE_MEMORY,
    SERVICE_SET_ASYNCIO_DEBUG,
    SERVICE_START,
    SERVICE_START_LOG_OBJECT_SOURCES,
    SERVICE_START_LOG_OBJECTS,
    SERVICE_START_LOOP_TIMING,
    SERVICE_STOP_LOG_OBJECT_SOURCES,
    SERVICE_STOP_LOG_OBJECTS,
    SERVICE_STOP_LOOP_TIMING,
)
from homeassistant.config_entries import current_entry
from homeassistant.const import CONF_ENABLED, CONF_SCAN_INTERVAL, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later, async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util


async def test_basic_usage(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test we can setup and the service is registered."""
    test_dir = tmp_path / "profiles"
    test_dir.mkdir()

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_START)

    last_filename = None

    def _mock_path(filename: str) -> str:
        nonlocal last_filename
        last_filename = str(test_dir / filename)
        return last_filename

    with patch("cProfile.Profile"), patch.object(hass.config, "path", _mock_path):
        await hass.services.async_call(
            DOMAIN, SERVICE_START, {CONF_SECONDS: 0.000001}, blocking=True
        )

    assert os.path.exists(last_filename)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_memory_usage(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test we can setup and the service is registered."""
    test_dir = tmp_path / "profiles"
    test_dir.mkdir()

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_MEMORY)

    last_filename = None

    def _mock_path(filename: str) -> str:
        nonlocal last_filename
        last_filename = str(test_dir / filename)
        return last_filename

    with patch("guppy.hpy") as mock_hpy, patch.object(hass.config, "path", _mock_path):
        await hass.services.async_call(
            DOMAIN, SERVICE_MEMORY, {CONF_SECONDS: 0.000001}, blocking=True
        )

        mock_hpy.assert_called_once()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_object_growth_logging(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test we can setup and the service and we can dump objects to the log."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_START_LOG_OBJECTS)
    assert hass.services.has_service(DOMAIN, SERVICE_STOP_LOG_OBJECTS)

    with patch.object(objgraph, "growth"):
        await hass.services.async_call(
            DOMAIN, SERVICE_START_LOG_OBJECTS, {CONF_SCAN_INTERVAL: 1}, blocking=True
        )
        with pytest.raises(HomeAssistantError, match="Object logging already started"):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_START_LOG_OBJECTS,
                {CONF_SCAN_INTERVAL: 1},
                blocking=True,
            )

        assert "Growth" in caplog.text
        await hass.async_block_till_done(wait_background_tasks=True)
        caplog.clear()

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert "Growth" in caplog.text

    await hass.services.async_call(DOMAIN, SERVICE_STOP_LOG_OBJECTS, {}, blocking=True)
    caplog.clear()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=21))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert "Growth" not in caplog.text

    with pytest.raises(HomeAssistantError, match="Object logging not running"):
        await hass.services.async_call(
            DOMAIN, SERVICE_STOP_LOG_OBJECTS, {}, blocking=True
        )

    with patch.object(objgraph, "growth"):
        await hass.services.async_call(
            DOMAIN, SERVICE_START_LOG_OBJECTS, {CONF_SCAN_INTERVAL: 10}, blocking=True
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        caplog.clear()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert "Growth" not in caplog.text


async def test_dump_log_object(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we can setup and the service is registered and logging works."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    class DumpLogDummy:
        def __init__(self, fail) -> None:
            self.fail = fail

        def __repr__(self):
            if self.fail:
                raise Exception("failed")  # noqa: TRY002
            return "<DumpLogDummy success>"

    obj1 = DumpLogDummy(False)
    obj2 = DumpLogDummy(True)

    assert hass.services.has_service(DOMAIN, SERVICE_DUMP_LOG_OBJECTS)

    with patch("objgraph.by_type", return_value=[obj1, obj2]):
        await hass.services.async_call(
            DOMAIN, SERVICE_DUMP_LOG_OBJECTS, {CONF_TYPE: "DumpLogDummy"}, blocking=True
        )

    assert "<DumpLogDummy success>" in caplog.text
    assert "Failed to serialize" in caplog.text
    del obj1
    del obj2
    caplog.clear()


async def test_log_thread_frames(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we can log thread frames."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_LOG_THREAD_FRAMES)

    await hass.services.async_call(DOMAIN, SERVICE_LOG_THREAD_FRAMES, {}, blocking=True)

    assert "SyncWorker_0" in caplog.text
    caplog.clear()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_log_current_tasks(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we can log current tasks."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_LOG_CURRENT_TASKS)

    await hass.services.async_call(DOMAIN, SERVICE_LOG_CURRENT_TASKS, {}, blocking=True)

    assert "test_log_current_tasks" in caplog.text
    caplog.clear()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_log_scheduled(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we can log scheduled items in the event loop."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_LOG_EVENT_LOOP_SCHEDULED)

    hass.loop.call_later(0.1, lambda: None)

    await hass.services.async_call(
        DOMAIN, SERVICE_LOG_EVENT_LOOP_SCHEDULED, {}, blocking=True
    )

    assert "Scheduled" in caplog.text
    caplog.clear()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("socket_enabled")
async def test_dump_sockets(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test dumping of sockets to the log."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    caplog.clear()

    sock = None
    try:
        # Try to bind ephemeral UDP port on localhost for testing
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

        assert hass.services.has_service(DOMAIN, SERVICE_DUMP_SOCKETS)
        await hass.services.async_call(DOMAIN, SERVICE_DUMP_SOCKETS, blocking=True)
    finally:
        if sock:
            sock.close()

    assert "Sockets used by Home Assistant" in caplog.text
    assert f"laddr=('127.0.0.1', {port})" in caplog.text


async def test_lru_stats(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test logging lru stats."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    @lru_cache(maxsize=1)
    def _dummy_test_lru_stats():
        return 1

    class DomainData:
        def __init__(self) -> None:
            self._data = LRU(1)

    domain_data = DomainData()
    assert hass.services.has_service(DOMAIN, SERVICE_LRU_STATS)

    class LRUCache:
        def __init__(self) -> None:
            self._data = {"sqlalchemy_test": 1}

    sqlalchemy_lru_cache = LRUCache()

    def _mock_by_type(type_):
        if type_ == _LRU_CACHE_WRAPPER_OBJECT:
            return [_dummy_test_lru_stats]
        if type_ == _SQLALCHEMY_LRU_OBJECT:
            return [sqlalchemy_lru_cache]
        return [domain_data]

    with patch("objgraph.by_type", side_effect=_mock_by_type):
        await hass.services.async_call(DOMAIN, SERVICE_LRU_STATS, blocking=True)

    assert "DomainData" in caplog.text
    assert "(0, 0)" in caplog.text
    assert "_dummy_test_lru_stats" in caplog.text
    assert "CacheInfo" in caplog.text
    assert "sqlalchemy_test" in caplog.text


async def test_log_object_sources(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we can setup and the service and we can dump objects to the log."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_START_LOG_OBJECT_SOURCES)
    assert hass.services.has_service(DOMAIN, SERVICE_STOP_LOG_OBJECT_SOURCES)

    class FakeObject:
        """Fake object."""

        def __repr__(self):
            """Return a fake repr.""."""
            return "<FakeObject>"

    fake_object = FakeObject()

    with patch("gc.collect"), patch("gc.get_objects", return_value=[fake_object]):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_LOG_OBJECT_SOURCES,
            {CONF_SCAN_INTERVAL: 10},
            blocking=True,
        )
        with pytest.raises(HomeAssistantError, match="Object logging already started"):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_START_LOG_OBJECT_SOURCES,
                {CONF_SCAN_INTERVAL: 10},
                blocking=True,
            )

        assert "New object FakeObject (0/1)" in caplog.text
        caplog.clear()

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert "No new object growth found" in caplog.text

    fake_object2 = FakeObject()

    with (
        patch("gc.collect"),
        patch("gc.get_objects", return_value=[fake_object, fake_object2]),
    ):
        caplog.clear()

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=21))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert "New object FakeObject (1/2)" in caplog.text

    many_objects = [FakeObject() for _ in range(30)]
    with patch("gc.collect"), patch("gc.get_objects", return_value=many_objects):
        caplog.clear()

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert "New object FakeObject (2/30)" in caplog.text
        assert "New objects overflowed by {'FakeObject': 25}" in caplog.text

    await hass.services.async_call(
        DOMAIN, SERVICE_STOP_LOG_OBJECT_SOURCES, {}, blocking=True
    )
    caplog.clear()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=41))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert "FakeObject" not in caplog.text
    assert "No new object growth found" not in caplog.text

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=51))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert "FakeObject" not in caplog.text
    assert "No new object growth found" not in caplog.text

    with pytest.raises(HomeAssistantError, match="Object logging not running"):
        await hass.services.async_call(
            DOMAIN, SERVICE_STOP_LOG_OBJECT_SOURCES, {}, blocking=True
        )


async def test_set_asyncio_debug(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setting asyncio debug."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_SET_ASYNCIO_DEBUG)

    hass.loop.set_debug(False)
    original_level = logging.getLogger().getEffectiveLevel()
    logging.getLogger().setLevel(logging.WARNING)

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_ASYNCIO_DEBUG, {CONF_ENABLED: False}, blocking=True
    )
    # Ensure logging level is only increased if we enable
    assert logging.getLogger().getEffectiveLevel() == logging.WARNING

    await hass.services.async_call(DOMAIN, SERVICE_SET_ASYNCIO_DEBUG, {}, blocking=True)
    assert hass.loop.get_debug() is True

    # Ensure logging is at least at INFO level
    assert logging.getLogger().getEffectiveLevel() == logging.INFO

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_ASYNCIO_DEBUG, {CONF_ENABLED: False}, blocking=True
    )
    assert hass.loop.get_debug() is False

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_ASYNCIO_DEBUG, {CONF_ENABLED: True}, blocking=True
    )
    assert hass.loop.get_debug() is True

    logging.getLogger().setLevel(original_level)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


def _spin(seconds: float) -> None:
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        pass


async def _setup_profiler(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Profiler")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.parametrize(
    "service", [SERVICE_DUMP_LOOP_TIMING, SERVICE_STOP_LOOP_TIMING]
)
async def test_loop_timing_needs_a_running_timing(
    hass: HomeAssistant, service: str
) -> None:
    """Dump and stop refuse while nothing is being timed."""
    await _setup_profiler(hass)
    with pytest.raises(HomeAssistantError, match="not running"):
        await hass.services.async_call(DOMAIN, service, {}, blocking=True)


@pytest.mark.parametrize("threshold", [-1, 60_001, "inf"])
async def test_loop_timing_rejects_a_threshold_out_of_range(
    hass: HomeAssistant, threshold: float | str
) -> None:
    """The threshold is validated like the UI selector, not left to overflow."""
    await _setup_profiler(hass)
    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_LOOP_TIMING,
            {CONF_THRESHOLD: threshold},
            blocking=True,
        )
    assert Handle._run.__qualname__ == "Handle._run"


async def test_loop_timing_starts_once_and_stops_on_unload(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Start installs the wrapper once; stop or unload restore the original."""
    entry = await _setup_profiler(hass)
    original_run = Handle._run

    await hass.services.async_call(
        DOMAIN, SERVICE_START_LOOP_TIMING, {CONF_THRESHOLD: 50}, blocking=True
    )
    assert Handle._run is not original_run
    assert "callbacks over 50.0 ms are kept" in caplog.text
    with pytest.raises(HomeAssistantError, match="already started"):
        await hass.services.async_call(
            DOMAIN, SERVICE_START_LOOP_TIMING, {}, blocking=True
        )

    caplog.clear()
    report = await hass.services.async_call(
        DOMAIN, SERVICE_STOP_LOOP_TIMING, {}, blocking=True, return_response=True
    )
    assert Handle._run is original_run
    assert report is not None
    assert report["threshold_ms"] == 50.0
    assert "Event loop timing stopped" in caplog.text

    await hass.services.async_call(DOMAIN, SERVICE_START_LOOP_TIMING, {}, blocking=True)
    assert Handle._run is not original_run
    caplog.clear()
    await hass.config_entries.async_unload(entry.entry_id)
    assert Handle._run is original_run
    # What was recorded is not lost with the entry
    assert "Event loop timing stopped by unload" in caplog.text
    assert "Event loop callbacks since" in caplog.text


async def test_loop_timing_attribution(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Callbacks count for what ran and the config entry; slow ones are listed."""
    entry = await _setup_profiler(hass)
    await hass.services.async_call(
        DOMAIN, SERVICE_START_LOOP_TIMING, {CONF_THRESHOLD: 50}, blocking=True
    )

    class SlowCoordinator(DataUpdateCoordinator[int]):
        """Spin in a step after the first await, like a slow parser would."""

        async def _async_update_data(self) -> int:
            await asyncio.sleep(0)
            _spin(0.08)
            return 1

    def quick() -> None:
        pass

    @callback
    def later(_now: datetime) -> None:
        _spin(0.06)

    @callback
    def at_point(_now: datetime) -> None:
        pass

    def cancel_self() -> None:
        handle.cancel()

    hass.loop.call_soon(quick)
    hass.loop.call_soon(quick)
    handle = hass.loop.call_soon(cancel_self)
    token = current_entry.set(entry)
    try:
        async_call_later(hass, 0, later)
        async_track_point_in_utc_time(hass, at_point, dt_util.utcnow())
        coordinator = SlowCoordinator(
            hass,
            logging.getLogger(__name__),
            config_entry=entry,
            name="slow",
            update_interval=timedelta(seconds=30),
        )
        unsub = coordinator.async_add_listener(lambda: None)
    finally:
        current_entry.reset(token)
    # No freezer: it would freeze the clocks the spin and the timing read
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    unsub()

    report = await hass.services.async_call(
        DOMAIN, SERVICE_DUMP_LOOP_TIMING, {}, blocking=True, return_response=True
    )
    assert report is not None
    assert report["errors"] == 0
    rows = {(row["callback"], row["config_entry"]): row for row in report["callbacks"]}
    here = f"{__name__}.test_loop_timing_attribution.<locals>"
    # The core coroutine shows the integration's class, and the entry
    step = rows[(f"{here}.SlowCoordinator._handle_refresh_interval", entry.entry_id)]
    assert step["count"] == 1
    assert 75 <= step["max_ms"] <= step["total_ms"]
    assert step["entry"] == {"domain": DOMAIN, "title": "Profiler"}
    # The job handed to call_later counts for its target
    timer = rows[(f"{here}.later", entry.entry_id)]
    assert timer["count"] == 1
    assert timer["max_ms"] >= 55
    # A helper scheduled as a callable instance counts for its class
    point = rows[
        ("homeassistant.helpers.event._TrackPointUTCTime.__call__", entry.entry_id)
    ]
    assert point["count"] == 1
    quick_row = rows[(f"{here}.quick", None)]
    assert quick_row["count"] == 2
    assert "entry" not in quick_row
    # A callback that cancels its own handle is still known by name
    assert rows[(f"{here}.cancel_self", None)]["count"] == 1
    assert all(row["count"] for row in report["callbacks"])
    slow = {
        (row["callback"], row["config_entry"])
        for row in report["slow"]
        if row["callback"].startswith(here)
    }
    # A subset: a loaded CI worker can stall a no-op callback past 50 ms
    assert {
        (f"{here}.later", entry.entry_id),
        (f"{here}.SlowCoordinator._handle_refresh_interval", entry.entry_id),
    } <= slow
    assert [row["seq"] for row in report["slow"]] == list(
        range(1, len(report["slow"]) + 1)
    )

    caplog.clear()
    await hass.services.async_call(DOMAIN, SERVICE_DUMP_LOOP_TIMING, {}, blocking=True)
    assert f"{here}.later [profiler: Profiler]: 1 calls" in caplog.text
    assert "Callbacks over 50.0 ms:" in caplog.text
    assert "  #1 " in caplog.text
    await hass.config_entries.async_unload(entry.entry_id)


async def test_loop_timing_keeps_other_loops_and_exceptions_alone(
    hass: HomeAssistant,
) -> None:
    """Another loop is not timed, and a failing callback still reaches the handler."""
    entry = await _setup_profiler(hass)
    await hass.services.async_call(DOMAIN, SERVICE_START_LOOP_TIMING, {}, blocking=True)

    def fail() -> None:
        raise ValueError("boom")

    handled: list[dict[str, Any]] = []
    exception_handler = hass.loop.get_exception_handler()
    hass.loop.set_exception_handler(lambda _loop, context: handled.append(context))
    try:
        hass.loop.call_soon(fail)
        await hass.async_block_till_done()
    finally:
        hass.loop.set_exception_handler(exception_handler)
    assert isinstance(handled[0]["exception"], ValueError)

    def run_other_loop() -> None:
        other = asyncio.new_event_loop()
        try:
            other.call_soon(partial(_spin, 0.01))
            other.call_soon(other.stop)
            other.run_forever()
        finally:
            other.close()

    await hass.async_add_executor_job(run_other_loop)

    report = await hass.services.async_call(
        DOMAIN, SERVICE_STOP_LOOP_TIMING, {}, blocking=True, return_response=True
    )
    assert report is not None
    labels = [row["callback"] for row in report["callbacks"]]
    assert f"{__name__}._spin" not in labels
    here = (
        f"{__name__}.test_loop_timing_keeps_other_loops_and_exceptions_alone.<locals>"
    )
    assert f"{here}.fail" in labels
    await hass.config_entries.async_unload(entry.entry_id)


def test_loop_timing_tells_c_functions_apart() -> None:
    """Two C functions with the same name but different modules get their own rows."""
    loop = asyncio.new_event_loop()
    timing = LoopTiming(loop, DEFAULT_THRESHOLD_MS)
    timing.start()
    try:
        loop.call_soon(partial(zlib.crc32, b"x"))
        loop.call_soon(partial(binascii.crc32, b"x"))
        loop.call_soon(loop.stop)
        loop.run_forever()
    finally:
        timing.stop()
        loop.close()
    labels = {row["callback"] for row in timing.report()["callbacks"]}
    assert {"zlib.crc32", "binascii.crc32"} <= labels


def test_loop_timing_numbers_slow_callbacks_past_the_limit() -> None:
    """Sequence numbers keep counting after the slow list drops old entries."""
    loop = asyncio.new_event_loop()
    timing = LoopTiming(loop, 0)
    timing.start()
    try:
        for _ in range(150):
            loop.call_soon(int)
        loop.call_soon(loop.stop)
        loop.run_forever()
    finally:
        timing.stop()
        loop.close()
    seqs = [row["seq"] for row in timing.report()["slow"]]
    assert len(seqs) == 100
    assert seqs == list(range(seqs[0], seqs[0] + 100))
    assert seqs[-1] >= 151


def test_loop_timing_lets_system_exit_through() -> None:
    """SystemExit from a callback leaves the loop as it does without timing."""

    def leave() -> None:
        raise SystemExit(3)

    loop = asyncio.new_event_loop()
    timing = LoopTiming(loop, DEFAULT_THRESHOLD_MS)
    timing.start()
    try:
        loop.call_soon(leave)
        with pytest.raises(SystemExit, match="3"):
            loop.run_forever()
    finally:
        timing.stop()
        loop.close()
    assert Handle._run.__qualname__ == "Handle._run"
    assert timing.errors == 0


def test_loop_timing_counts_a_callback_it_cannot_attribute(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A callable that breaks when looked at still runs, counted under other callbacks."""

    class Prickly:
        # Only the name breaks: asyncio's debug mode looks at other
        # attributes when the callback is scheduled
        def __getattr__(self, name: str) -> Any:
            if name == "__qualname__":
                raise RuntimeError("do not look at me")
            raise AttributeError(name)

        def __call__(self) -> None:
            ran.append(True)

    ran: list[bool] = []
    loop = asyncio.new_event_loop()
    timing = LoopTiming(loop, DEFAULT_THRESHOLD_MS)
    timing.start()
    try:
        loop.call_soon(Prickly())
        loop.call_soon(Prickly())
        loop.call_soon(loop.stop)
        loop.run_forever()
    finally:
        timing.stop()
        loop.close()
    assert ran == [True, True]
    assert timing.errors == 2
    report = timing.report()
    other = next(
        row for row in report["callbacks"] if row["callback"] == "other callbacks"
    )
    assert other["count"] == 2
    assert "Callbacks that could not be attributed: 2" in format_report(report)
    # The cause is logged once
    assert caplog.text.count("Could not attribute a callback") == 1
    assert "do not look at me" in caplog.text


def test_loop_timing_caps_the_rows(caplog: pytest.LogCaptureFixture) -> None:
    """Past the cap, new callbacks share one row instead of growing the table."""
    loop = asyncio.new_event_loop()
    timing = LoopTiming(loop, DEFAULT_THRESHOLD_MS)
    timing.start()
    try:
        with patch("homeassistant.components.profiler.loop_timing.MAX_ROWS", 2):
            loop.call_soon(partial(zlib.crc32, b"x"))
            loop.call_soon(partial(binascii.crc32, b"x"))
            loop.call_soon(int)
            loop.call_soon(str)
            loop.call_soon(loop.stop)
            loop.run_forever()
    finally:
        timing.stop()
        loop.close()
    report = timing.report()
    rows = {row["callback"]: row["count"] for row in report["callbacks"]}
    assert rows["zlib.crc32"] == 1
    assert rows["binascii.crc32"] == 1
    # int, str and loop.stop, none of which fit any more
    assert rows["other callbacks"] == 3
    assert len(rows) == 3
    assert report["overflowed"] == 3
    assert "table full: 3" in format_report(report)
    assert caplog.text.count("keeps 2 callbacks apart") == 1


def test_loop_timing_keeps_alike_functions_apart() -> None:
    """Code objects compare by value, so two alike functions must not share a row."""
    source = "def cb():\n    return 1\n"
    first: dict[str, Any] = {"__name__": "first"}
    second: dict[str, Any] = {"__name__": "second"}
    exec(compile(source, "/first.py", "exec"), first)  # noqa: S102
    exec(compile(source, "/second.py", "exec"), second)  # noqa: S102
    assert first["cb"].__code__ == second["cb"].__code__
    loop = asyncio.new_event_loop()
    timing = LoopTiming(loop, DEFAULT_THRESHOLD_MS)
    timing.start()
    try:
        loop.call_soon(first["cb"])
        loop.call_soon(second["cb"])
        loop.call_soon(loop.stop)
        loop.run_forever()
    finally:
        timing.stop()
        loop.close()
    rows = {row["callback"]: row["count"] for row in timing.report()["callbacks"]}
    assert rows["first.cb"] == 1
    assert rows["second.cb"] == 1


def test_loop_timing_left_under_another_wrapper_passes_through(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Stopped under something else's wrapper, the timing records nothing more."""
    loop = asyncio.new_event_loop()
    timing = LoopTiming(loop, DEFAULT_THRESHOLD_MS)
    original_run = Handle._run
    timing.start()
    ours = Handle._run

    def other(handle: Handle) -> None:
        ours(handle)

    try:
        Handle._run = other  # type: ignore[method-assign, assignment]
        timing.stop()
        assert "Something else patched Handle._run" in caplog.text
        # Not ours on top: the other wrapper stays, ours only passes calls on
        assert Handle._run is other
        loop.call_soon(int)
        loop.call_soon(loop.stop)
        loop.run_forever()
        assert timing.report()["callbacks"] == []
    finally:
        Handle._run = original_run  # type: ignore[method-assign]
        loop.close()


def test_loop_timing_log_says_when_rows_are_left_out() -> None:
    """The log shows the busiest callbacks and says how many it left out."""
    report = {
        "since": "now",
        "threshold_ms": 100.0,
        "errors": 0,
        "overflowed": 0,
        "slow": [],
        "callbacks": [
            {
                "callback": f"cb{i}",
                "config_entry": None,
                "count": 1,
                "total_ms": 0.1,
                "max_ms": 0.1,
                "max_at": "now",
            }
            for i in range(52)
        ],
    }
    text = format_report(report)
    assert "cb49:" in text
    assert "cb50:" not in text
    assert "... and 2 more callbacks" in text


def test_loop_timing_log_keeps_the_id_of_a_removed_entry() -> None:
    """A config entry removed while timing ran still tells its rows apart."""
    row = {
        "callback": "cb",
        "count": 1,
        "total_ms": 0.1,
        "max_ms": 0.1,
        "max_at": "now",
    }
    report = {
        "since": "now",
        "threshold_ms": 100.0,
        "errors": 0,
        "overflowed": 0,
        "slow": [],
        "callbacks": [
            {**row, "config_entry": "gone"},
            {**row, "config_entry": "kept", "entry": {"domain": "hue", "title": "Hue"}},
            {**row, "config_entry": None},
        ],
    }
    lines = format_report(report).splitlines()[1:]
    assert lines == [
        "  cb [gone]: 1 calls, 0.1 ms total, longest 0.1 ms at now",
        "  cb [hue: Hue]: 1 calls, 0.1 ms total, longest 0.1 ms at now",
        "  cb: 1 calls, 0.1 ms total, longest 0.1 ms at now",
    ]
