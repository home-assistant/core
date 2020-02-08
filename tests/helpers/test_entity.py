"""Test the entity helper."""
# pylint: disable=protected-access
import asyncio
from datetime import timedelta
import threading
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from homeassistant.config import DATA_CUSTOMIZE
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_HIDDEN, STATE_UNAVAILABLE
from homeassistant.core import Context
from homeassistant.helpers import entity, entity_registry
from homeassistant.helpers.entity_values import EntityValues

from tests.common import get_test_home_assistant, mock_registry


def test_generate_entity_id_requires_hass_or_ids():
    """Ensure we require at least hass or current ids."""
    fmt = "test.{}"
    with pytest.raises(ValueError):
        entity.generate_entity_id(fmt, "hello world")


def test_generate_entity_id_given_keys():
    """Test generating an entity id given current ids."""
    fmt = "test.{}"
    assert (
        entity.generate_entity_id(
            fmt, "overwrite hidden true", current_ids=["test.overwrite_hidden_true"]
        )
        == "test.overwrite_hidden_true_2"
    )
    assert (
        entity.generate_entity_id(
            fmt, "overwrite hidden true", current_ids=["test.another_entity"]
        )
        == "test.overwrite_hidden_true"
    )


def test_async_update_support(hass):
    """Test async update getting called."""
    sync_update = []
    async_update = []

    class AsyncEntity(entity.Entity):
        entity_id = "sensor.test"

        def update(self):
            sync_update.append([1])

    ent = AsyncEntity()
    ent.hass = hass

    hass.loop.run_until_complete(ent.async_update_ha_state(True))

    assert len(sync_update) == 1
    assert len(async_update) == 0

    @asyncio.coroutine
    def async_update_func():
        """Async update."""
        async_update.append(1)

    ent.async_update = async_update_func

    hass.loop.run_until_complete(ent.async_update_ha_state(True))

    assert len(sync_update) == 1
    assert len(async_update) == 1


class TestHelpersEntity:
    """Test homeassistant.helpers.entity module."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.entity = entity.Entity()
        self.entity.entity_id = "test.overwrite_hidden_true"
        self.hass = self.entity.hass = get_test_home_assistant()
        self.entity.schedule_update_ha_state()
        self.hass.block_till_done()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_default_hidden_not_in_attributes(self):
        """Test that the default hidden property is set to False."""
        assert ATTR_HIDDEN not in self.hass.states.get(self.entity.entity_id).attributes

    def test_overwriting_hidden_property_to_true(self):
        """Test we can overwrite hidden property to True."""
        self.hass.data[DATA_CUSTOMIZE] = EntityValues(
            {self.entity.entity_id: {ATTR_HIDDEN: True}}
        )
        self.entity.schedule_update_ha_state()
        self.hass.block_till_done()

        state = self.hass.states.get(self.entity.entity_id)
        assert state.attributes.get(ATTR_HIDDEN)

    def test_generate_entity_id_given_hass(self):
        """Test generating an entity id given hass object."""
        fmt = "test.{}"
        assert (
            entity.generate_entity_id(fmt, "overwrite hidden true", hass=self.hass)
            == "test.overwrite_hidden_true_2"
        )

    def test_device_class(self):
        """Test device class attribute."""
        state = self.hass.states.get(self.entity.entity_id)
        assert state.attributes.get(ATTR_DEVICE_CLASS) is None
        with patch(
            "homeassistant.helpers.entity.Entity.device_class", new="test_class"
        ):
            self.entity.schedule_update_ha_state()
            self.hass.block_till_done()
        state = self.hass.states.get(self.entity.entity_id)
        assert state.attributes.get(ATTR_DEVICE_CLASS) == "test_class"


@asyncio.coroutine
def test_warn_slow_update(hass):
    """Warn we log when entity update takes a long time."""
    update_call = False

    @asyncio.coroutine
    def async_update():
        """Mock async update."""
        nonlocal update_call
        update_call = True

    mock_entity = entity.Entity()
    mock_entity.hass = hass
    mock_entity.entity_id = "comp_test.test_entity"
    mock_entity.async_update = async_update

    with patch.object(hass.loop, "call_later", MagicMock()) as mock_call:
        yield from mock_entity.async_update_ha_state(True)
        assert mock_call.called
        assert len(mock_call.mock_calls) == 2

        timeout, logger_method = mock_call.mock_calls[0][1][:2]

        assert timeout == entity.SLOW_UPDATE_WARNING
        assert logger_method == entity._LOGGER.warning

        assert mock_call().cancel.called

        assert update_call


@asyncio.coroutine
def test_warn_slow_update_with_exception(hass):
    """Warn we log when entity update takes a long time and trow exception."""
    update_call = False

    @asyncio.coroutine
    def async_update():
        """Mock async update."""
        nonlocal update_call
        update_call = True
        raise AssertionError("Fake update error")

    mock_entity = entity.Entity()
    mock_entity.hass = hass
    mock_entity.entity_id = "comp_test.test_entity"
    mock_entity.async_update = async_update

    with patch.object(hass.loop, "call_later", MagicMock()) as mock_call:
        yield from mock_entity.async_update_ha_state(True)
        assert mock_call.called
        assert len(mock_call.mock_calls) == 2

        timeout, logger_method = mock_call.mock_calls[0][1][:2]

        assert timeout == entity.SLOW_UPDATE_WARNING
        assert logger_method == entity._LOGGER.warning

        assert mock_call().cancel.called

        assert update_call


@asyncio.coroutine
def test_warn_slow_device_update_disabled(hass):
    """Disable slow update warning with async_device_update."""
    update_call = False

    @asyncio.coroutine
    def async_update():
        """Mock async update."""
        nonlocal update_call
        update_call = True

    mock_entity = entity.Entity()
    mock_entity.hass = hass
    mock_entity.entity_id = "comp_test.test_entity"
    mock_entity.async_update = async_update

    with patch.object(hass.loop, "call_later", MagicMock()) as mock_call:
        yield from mock_entity.async_device_update(warning=False)

        assert not mock_call.called
        assert update_call


@asyncio.coroutine
def test_async_schedule_update_ha_state(hass):
    """Warn we log when entity update takes a long time and trow exception."""
    update_call = False

    @asyncio.coroutine
    def async_update():
        """Mock async update."""
        nonlocal update_call
        update_call = True

    mock_entity = entity.Entity()
    mock_entity.hass = hass
    mock_entity.entity_id = "comp_test.test_entity"
    mock_entity.async_update = async_update

    mock_entity.async_schedule_update_ha_state(True)
    yield from hass.async_block_till_done()

    assert update_call is True


async def test_async_async_request_call_without_lock(hass):
    """Test for async_requests_call works without a lock."""
    updates = []

    class AsyncEntity(entity.Entity):
        def __init__(self, entity_id):
            """Initialize Async test entity."""
            self.entity_id = entity_id
            self.hass = hass

        async def testhelper(self, count):
            """Helper function."""
            updates.append(count)

    ent_1 = AsyncEntity("light.test_1")
    ent_2 = AsyncEntity("light.test_2")
    try:
        job1 = ent_1.async_request_call(ent_1.testhelper(1))
        job2 = ent_2.async_request_call(ent_2.testhelper(2))

        await asyncio.wait([job1, job2])
        while True:
            if len(updates) >= 2:
                break
            await asyncio.sleep(0)
    finally:
        pass

    assert len(updates) == 2
    updates.sort()
    assert updates == [1, 2]


async def test_async_async_request_call_with_lock(hass):
    """Test for async_requests_call works with a semaphore."""
    updates = []

    test_semaphore = asyncio.Semaphore(1)

    class AsyncEntity(entity.Entity):
        def __init__(self, entity_id, lock):
            """Initialize Async test entity."""
            self.entity_id = entity_id
            self.hass = hass
            self.parallel_updates = lock

        async def testhelper(self, count):
            """Helper function."""
            updates.append(count)

    ent_1 = AsyncEntity("light.test_1", test_semaphore)
    ent_2 = AsyncEntity("light.test_2", test_semaphore)

    try:
        assert test_semaphore.locked() is False
        await test_semaphore.acquire()
        assert test_semaphore.locked()

        job1 = ent_1.async_request_call(ent_1.testhelper(1))
        job2 = ent_2.async_request_call(ent_2.testhelper(2))

        hass.async_create_task(job1)
        hass.async_create_task(job2)

        assert len(updates) == 0
        assert updates == []
        assert test_semaphore._value == 0

        test_semaphore.release()

        while True:
            if len(updates) >= 2:
                break
            await asyncio.sleep(0)
    finally:
        test_semaphore.release()

    assert len(updates) == 2
    updates.sort()
    assert updates == [1, 2]


async def test_async_parallel_updates_with_zero(hass):
    """Test parallel updates with 0 (disabled)."""
    updates = []
    test_lock = asyncio.Event()

    class AsyncEntity(entity.Entity):
        def __init__(self, entity_id, count):
            """Initialize Async test entity."""
            self.entity_id = entity_id
            self.hass = hass
            self._count = count

        async def async_update(self):
            """Test update."""
            updates.append(self._count)
            await test_lock.wait()

    ent_1 = AsyncEntity("sensor.test_1", 1)
    ent_2 = AsyncEntity("sensor.test_2", 2)

    try:
        ent_1.async_schedule_update_ha_state(True)
        ent_2.async_schedule_update_ha_state(True)

        while True:
            if len(updates) >= 2:
                break
            await asyncio.sleep(0)

        assert len(updates) == 2
        assert updates == [1, 2]
    finally:
        test_lock.set()


async def test_async_parallel_updates_with_zero_on_sync_update(hass):
    """Test parallel updates with 0 (disabled)."""
    updates = []
    test_lock = threading.Event()

    class AsyncEntity(entity.Entity):
        def __init__(self, entity_id, count):
            """Initialize Async test entity."""
            self.entity_id = entity_id
            self.hass = hass
            self._count = count

        def update(self):
            """Test update."""
            updates.append(self._count)
            if not test_lock.wait(timeout=1):
                # if timeout populate more data to fail the test
                updates.append(self._count)

    ent_1 = AsyncEntity("sensor.test_1", 1)
    ent_2 = AsyncEntity("sensor.test_2", 2)

    try:
        ent_1.async_schedule_update_ha_state(True)
        ent_2.async_schedule_update_ha_state(True)

        while True:
            if len(updates) >= 2:
                break
            await asyncio.sleep(0)

        assert len(updates) == 2
        assert updates == [1, 2]
    finally:
        test_lock.set()
        await asyncio.sleep(0)


async def test_async_parallel_updates_with_one(hass):
    """Test parallel updates with 1 (sequential)."""
    updates = []
    test_lock = asyncio.Lock()
    test_semaphore = asyncio.Semaphore(1)

    class AsyncEntity(entity.Entity):
        def __init__(self, entity_id, count):
            """Initialize Async test entity."""
            self.entity_id = entity_id
            self.hass = hass
            self._count = count
            self.parallel_updates = test_semaphore

        async def async_update(self):
            """Test update."""
            updates.append(self._count)
            await test_lock.acquire()

    ent_1 = AsyncEntity("sensor.test_1", 1)
    ent_2 = AsyncEntity("sensor.test_2", 2)
    ent_3 = AsyncEntity("sensor.test_3", 3)

    await test_lock.acquire()

    try:
        ent_1.async_schedule_update_ha_state(True)
        ent_2.async_schedule_update_ha_state(True)
        ent_3.async_schedule_update_ha_state(True)

        while True:
            if len(updates) >= 1:
                break
            await asyncio.sleep(0)

        assert len(updates) == 1
        assert updates == [1]

        updates.clear()
        test_lock.release()
        await asyncio.sleep(0)

        while True:
            if len(updates) >= 1:
                break
            await asyncio.sleep(0)

        assert len(updates) == 1
        assert updates == [2]

        updates.clear()
        test_lock.release()
        await asyncio.sleep(0)

        while True:
            if len(updates) >= 1:
                break
            await asyncio.sleep(0)

        assert len(updates) == 1
        assert updates == [3]

        updates.clear()
        test_lock.release()
        await asyncio.sleep(0)

    finally:
        # we may have more than one lock need to release in case test failed
        for _ in updates:
            test_lock.release()
            await asyncio.sleep(0)
        test_lock.release()


async def test_async_parallel_updates_with_two(hass):
    """Test parallel updates with 2 (parallel)."""
    updates = []
    test_lock = asyncio.Lock()
    test_semaphore = asyncio.Semaphore(2)

    class AsyncEntity(entity.Entity):
        def __init__(self, entity_id, count):
            """Initialize Async test entity."""
            self.entity_id = entity_id
            self.hass = hass
            self._count = count
            self.parallel_updates = test_semaphore

        @asyncio.coroutine
        def async_update(self):
            """Test update."""
            updates.append(self._count)
            yield from test_lock.acquire()

    ent_1 = AsyncEntity("sensor.test_1", 1)
    ent_2 = AsyncEntity("sensor.test_2", 2)
    ent_3 = AsyncEntity("sensor.test_3", 3)
    ent_4 = AsyncEntity("sensor.test_4", 4)

    await test_lock.acquire()

    try:

        ent_1.async_schedule_update_ha_state(True)
        ent_2.async_schedule_update_ha_state(True)
        ent_3.async_schedule_update_ha_state(True)
        ent_4.async_schedule_update_ha_state(True)

        while True:
            if len(updates) >= 2:
                break
            await asyncio.sleep(0)

        assert len(updates) == 2
        assert updates == [1, 2]

        updates.clear()
        test_lock.release()
        await asyncio.sleep(0)
        test_lock.release()
        await asyncio.sleep(0)

        while True:
            if len(updates) >= 2:
                break
            await asyncio.sleep(0)

        assert len(updates) == 2
        assert updates == [3, 4]

        updates.clear()
        test_lock.release()
        await asyncio.sleep(0)
        test_lock.release()
        await asyncio.sleep(0)
    finally:
        # we may have more than one lock need to release in case test failed
        for _ in updates:
            test_lock.release()
            await asyncio.sleep(0)
        test_lock.release()


@asyncio.coroutine
def test_async_remove_no_platform(hass):
    """Test async_remove method when no platform set."""
    ent = entity.Entity()
    ent.hass = hass
    ent.entity_id = "test.test"
    yield from ent.async_update_ha_state()
    assert len(hass.states.async_entity_ids()) == 1
    yield from ent.async_remove()
    assert len(hass.states.async_entity_ids()) == 0


async def test_async_remove_runs_callbacks(hass):
    """Test async_remove method when no platform set."""
    result = []

    ent = entity.Entity()
    ent.hass = hass
    ent.entity_id = "test.test"
    ent.async_on_remove(lambda: result.append(1))
    await ent.async_remove()
    assert len(result) == 1


async def test_set_context(hass):
    """Test setting context."""
    context = Context()
    ent = entity.Entity()
    ent.hass = hass
    ent.entity_id = "hello.world"
    ent.async_set_context(context)
    await ent.async_update_ha_state()
    assert hass.states.get("hello.world").context == context


async def test_set_context_expired(hass):
    """Test setting context."""
    context = Context()

    with patch.object(
        entity.Entity, "context_recent_time", new_callable=PropertyMock
    ) as recent:
        recent.return_value = timedelta(seconds=-5)
        ent = entity.Entity()
        ent.hass = hass
        ent.entity_id = "hello.world"
        ent.async_set_context(context)
        await ent.async_update_ha_state()

    assert hass.states.get("hello.world").context != context
    assert ent._context is None
    assert ent._context_set is None


async def test_warn_disabled(hass, caplog):
    """Test we warn once if we write to a disabled entity."""
    entry = entity_registry.RegistryEntry(
        entity_id="hello.world",
        unique_id="test-unique-id",
        platform="test-platform",
        disabled_by="user",
    )
    mock_registry(hass, {"hello.world": entry})

    ent = entity.Entity()
    ent.hass = hass
    ent.entity_id = "hello.world"
    ent.registry_entry = entry
    ent.platform = MagicMock(platform_name="test-platform")

    caplog.clear()
    ent.async_write_ha_state()
    assert hass.states.get("hello.world") is None
    assert "Entity hello.world is incorrectly being triggered" in caplog.text

    caplog.clear()
    ent.async_write_ha_state()
    assert hass.states.get("hello.world") is None
    assert caplog.text == ""


async def test_disabled_in_entity_registry(hass):
    """Test entity is removed if we disable entity registry entry."""
    entry = entity_registry.RegistryEntry(
        entity_id="hello.world",
        unique_id="test-unique-id",
        platform="test-platform",
        disabled_by="user",
    )
    registry = mock_registry(hass, {"hello.world": entry})

    ent = entity.Entity()
    ent.hass = hass
    ent.entity_id = "hello.world"
    ent.registry_entry = entry
    ent.platform = MagicMock(platform_name="test-platform")

    await ent.async_internal_added_to_hass()
    ent.async_write_ha_state()
    assert hass.states.get("hello.world") is None

    entry2 = registry.async_update_entity("hello.world", disabled_by=None)
    await hass.async_block_till_done()
    assert entry2 != entry
    assert ent.registry_entry == entry2
    assert ent.enabled is True

    entry3 = registry.async_update_entity("hello.world", disabled_by="user")
    await hass.async_block_till_done()
    assert entry3 != entry2
    assert ent.registry_entry == entry3
    assert ent.enabled is False


async def test_capability_attrs(hass):
    """Test we still include capabilities even when unavailable."""
    with patch.object(
        entity.Entity, "available", PropertyMock(return_value=False)
    ), patch.object(
        entity.Entity,
        "capability_attributes",
        PropertyMock(return_value={"always": "there"}),
    ):
        ent = entity.Entity()
        ent.hass = hass
        ent.entity_id = "hello.world"
        ent.async_write_ha_state()

    state = hass.states.get("hello.world")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes["always"] == "there"


async def test_warn_slow_write_state(hass, caplog):
    """Check that we log a warning if reading properties takes too long."""
    mock_entity = entity.Entity()
    mock_entity.hass = hass
    mock_entity.entity_id = "comp_test.test_entity"
    mock_entity.platform = MagicMock(platform_name="hue")

    with patch("homeassistant.helpers.entity.timer", side_effect=[0, 10]):
        mock_entity.async_write_ha_state()

    assert (
        "Updating state for comp_test.test_entity "
        "(<class 'homeassistant.helpers.entity.Entity'>) "
        "took 10.000 seconds. Please create a bug report at "
        "https://github.com/home-assistant/home-assistant/issues?"
        "q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+hue%22"
    ) in caplog.text
