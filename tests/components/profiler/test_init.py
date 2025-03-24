"""Test the Profiler config flow."""

from datetime import timedelta
from functools import lru_cache
import logging
import os
from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from lru import LRU
import objgraph
import pytest

from homeassistant.components.profiler import (
    _LRU_CACHE_WRAPPER_OBJECT,
    _SQLALCHEMY_LRU_OBJECT,
    CONF_ENABLED,
    CONF_SECONDS,
    SERVICE_DUMP_LOG_OBJECTS,
    SERVICE_LOG_CURRENT_TASKS,
    SERVICE_LOG_EVENT_LOOP_SCHEDULED,
    SERVICE_LOG_THREAD_FRAMES,
    SERVICE_LRU_STATS,
    SERVICE_MEMORY,
    SERVICE_SET_ASYNCIO_DEBUG,
    SERVICE_START,
    SERVICE_START_LOG_OBJECT_SOURCES,
    SERVICE_START_LOG_OBJECTS,
    SERVICE_STOP_LOG_OBJECT_SOURCES,
    SERVICE_STOP_LOG_OBJECTS,
)
from homeassistant.components.profiler.const import DOMAIN
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


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
