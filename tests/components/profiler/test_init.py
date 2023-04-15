"""Test the Profiler config flow."""
from datetime import timedelta
from functools import lru_cache
import os
from pathlib import Path
import sys
from unittest.mock import patch

from lru import LRU  # pylint: disable=no-name-in-module
import pytest

from homeassistant.components.profiler import (
    _LRU_CACHE_WRAPPER_OBJECT,
    _SQLALCHEMY_LRU_OBJECT,
    CONF_SECONDS,
    SERVICE_DUMP_LOG_OBJECTS,
    SERVICE_LOG_EVENT_LOOP_SCHEDULED,
    SERVICE_LOG_THREAD_FRAMES,
    SERVICE_LRU_STATS,
    SERVICE_MEMORY,
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
import homeassistant.util.dt as dt_util

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


@pytest.mark.skipif(
    sys.version_info >= (3, 11), reason="not yet available on python 3.11"
)
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


@pytest.mark.skipif(sys.version_info < (3, 11), reason="still works on python 3.10")
async def test_memory_usage_py311(hass: HomeAssistant) -> None:
    """Test raise an error on python3.11."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, SERVICE_MEMORY)
    with pytest.raises(
        HomeAssistantError,
        match="Memory profiling is not supported on Python 3.11. Please use Python 3.10.",
    ):
        await hass.services.async_call(
            DOMAIN, SERVICE_MEMORY, {CONF_SECONDS: 0.000001}, blocking=True
        )


async def test_object_growth_logging(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we can setup and the service and we can dump objects to the log."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_START_LOG_OBJECTS)
    assert hass.services.has_service(DOMAIN, SERVICE_STOP_LOG_OBJECTS)

    with patch("objgraph.growth"):
        await hass.services.async_call(
            DOMAIN, SERVICE_START_LOG_OBJECTS, {CONF_SCAN_INTERVAL: 10}, blocking=True
        )
        with pytest.raises(HomeAssistantError, match="Object logging already started"):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_START_LOG_OBJECTS,
                {CONF_SCAN_INTERVAL: 10},
                blocking=True,
            )

        assert "Growth" in caplog.text
        caplog.clear()

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
        await hass.async_block_till_done()
        assert "Growth" in caplog.text

    await hass.services.async_call(DOMAIN, SERVICE_STOP_LOG_OBJECTS, {}, blocking=True)
    caplog.clear()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=21))
    await hass.async_block_till_done()
    assert "Growth" not in caplog.text

    with pytest.raises(HomeAssistantError, match="Object logging not running"):
        await hass.services.async_call(
            DOMAIN, SERVICE_STOP_LOG_OBJECTS, {}, blocking=True
        )

    with patch("objgraph.growth"):
        await hass.services.async_call(
            DOMAIN, SERVICE_START_LOG_OBJECTS, {CONF_SCAN_INTERVAL: 10}, blocking=True
        )
        caplog.clear()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
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
        def __init__(self, fail):
            self.fail = fail

        def __repr__(self):
            if self.fail:
                raise Exception("failed")
            return "<DumpLogDummy success>"

    obj1 = DumpLogDummy(False)
    obj2 = DumpLogDummy(True)

    assert hass.services.has_service(DOMAIN, SERVICE_DUMP_LOG_OBJECTS)

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


async def test_log_scheduled(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we can log scheduled items in the event loop."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_LOG_EVENT_LOOP_SCHEDULED)

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
        def __init__(self):
            self._data = LRU(1)

    domain_data = DomainData()
    assert hass.services.has_service(DOMAIN, SERVICE_LRU_STATS)

    class LRUCache:
        def __init__(self):
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
        await hass.async_block_till_done()
        assert "No new object growth found" in caplog.text

    fake_object2 = FakeObject()

    with patch("gc.collect"), patch(
        "gc.get_objects", return_value=[fake_object, fake_object2]
    ):
        caplog.clear()

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=21))
        await hass.async_block_till_done()
        assert "New object FakeObject (1/2)" in caplog.text

    many_objects = [FakeObject() for _ in range(30)]
    with patch("gc.collect"), patch("gc.get_objects", return_value=many_objects):
        caplog.clear()

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()
        assert "New object FakeObject (2/30)" in caplog.text
        assert "New objects overflowed by {'FakeObject': 25}" in caplog.text

    await hass.services.async_call(
        DOMAIN, SERVICE_STOP_LOG_OBJECT_SOURCES, {}, blocking=True
    )
    caplog.clear()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=41))
    await hass.async_block_till_done()
    assert "FakeObject" not in caplog.text
    assert "No new object growth found" not in caplog.text

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=51))
    await hass.async_block_till_done()
    assert "FakeObject" not in caplog.text
    assert "No new object growth found" not in caplog.text

    with pytest.raises(HomeAssistantError, match="Object logging not running"):
        await hass.services.async_call(
            DOMAIN, SERVICE_STOP_LOG_OBJECT_SOURCES, {}, blocking=True
        )
