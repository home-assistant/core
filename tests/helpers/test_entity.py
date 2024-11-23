"""Test the entity helper."""

import asyncio
from collections.abc import Iterable
import dataclasses
from datetime import timedelta
from enum import IntFlag
import logging
import threading
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

from freezegun.api import FrozenDateTimeFactory
from propcache import cached_property
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import (
    Context,
    HassJobType,
    HomeAssistant,
    ReleaseChannel,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from tests.common import (
    MockConfigEntry,
    MockEntity,
    MockEntityPlatform,
    MockModule,
    MockPlatform,
    mock_integration,
    mock_registry,
)


def test_generate_entity_id_requires_hass_or_ids() -> None:
    """Ensure we require at least hass or current ids."""
    with pytest.raises(ValueError):
        entity.generate_entity_id("test.{}", "hello world")


def test_generate_entity_id_given_keys() -> None:
    """Test generating an entity id given current ids."""
    assert (
        entity.generate_entity_id(
            "test.{}",
            "overwrite hidden true",
            current_ids=["test.overwrite_hidden_true"],
        )
        == "test.overwrite_hidden_true_2"
    )
    assert (
        entity.generate_entity_id(
            "test.{}", "overwrite hidden true", current_ids=["test.another_entity"]
        )
        == "test.overwrite_hidden_true"
    )


async def test_generate_entity_id_given_hass(hass: HomeAssistant) -> None:
    """Test generating an entity id given hass object."""
    hass.states.async_set("test.overwrite_hidden_true", "test")

    fmt = "test.{}"
    assert (
        entity.generate_entity_id(fmt, "overwrite hidden true", hass=hass)
        == "test.overwrite_hidden_true_2"
    )


async def test_async_update_support(hass: HomeAssistant) -> None:
    """Test async update getting called."""
    sync_update = []
    async_update = []

    class AsyncEntity(entity.Entity):
        """A test entity."""

        entity_id = "sensor.test"

        def update(self):
            """Update entity."""
            sync_update.append([1])

    ent = AsyncEntity()
    ent.hass = hass

    await ent.async_update_ha_state(True)

    assert len(sync_update) == 1
    assert len(async_update) == 0

    async def async_update_func():
        """Async update."""
        async_update.append(1)

    # pylint: disable-next=attribute-defined-outside-init
    ent.async_update = async_update_func

    await ent.async_update_ha_state(True)

    assert len(sync_update) == 1
    assert len(async_update) == 1


async def test_device_class(hass: HomeAssistant) -> None:
    """Test device class attribute."""
    ent = entity.Entity()
    ent.entity_id = "test.overwrite_hidden_true"
    ent.hass = hass
    ent.async_write_ha_state()
    state = hass.states.get(ent.entity_id)
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None

    ent._attr_device_class = "test_class"
    ent.async_write_ha_state()
    state = hass.states.get(ent.entity_id)
    assert state.attributes.get(ATTR_DEVICE_CLASS) == "test_class"


async def test_warn_slow_update(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Warn we log when entity update takes a long time."""
    update_call = False

    async def async_update():
        """Mock async update."""
        nonlocal update_call
        await asyncio.sleep(0.00001)
        update_call = True

    mock_entity = entity.Entity()
    mock_entity.hass = hass
    mock_entity.entity_id = "comp_test.test_entity"
    mock_entity.async_update = async_update

    fast_update_time = 0.0000001

    with patch.object(entity, "SLOW_UPDATE_WARNING", fast_update_time):
        await mock_entity.async_update_ha_state(True)
        assert str(fast_update_time) in caplog.text
        assert mock_entity.entity_id in caplog.text
        assert update_call


async def test_warn_slow_update_with_exception(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Warn we log when entity update takes a long time and trow exception."""
    update_call = False

    async def async_update():
        """Mock async update."""
        nonlocal update_call
        update_call = True
        await asyncio.sleep(0.00001)
        raise AssertionError("Fake update error")

    mock_entity = entity.Entity()
    mock_entity.hass = hass
    mock_entity.entity_id = "comp_test.test_entity"
    mock_entity.async_update = async_update

    fast_update_time = 0.0000001

    with patch.object(entity, "SLOW_UPDATE_WARNING", fast_update_time):
        await mock_entity.async_update_ha_state(True)
        assert str(fast_update_time) in caplog.text
        assert mock_entity.entity_id in caplog.text
        assert update_call


async def test_warn_slow_device_update_disabled(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Disable slow update warning with async_device_update."""
    update_call = False

    async def async_update():
        """Mock async update."""
        nonlocal update_call
        await asyncio.sleep(0.00001)
        update_call = True

    mock_entity = entity.Entity()
    mock_entity.hass = hass
    mock_entity.entity_id = "comp_test.test_entity"
    mock_entity.async_update = async_update

    fast_update_time = 0.0000001

    with patch.object(entity, "SLOW_UPDATE_WARNING", fast_update_time):
        await mock_entity.async_device_update(warning=False)
        assert str(fast_update_time) not in caplog.text
        assert mock_entity.entity_id not in caplog.text
        assert update_call


async def test_async_schedule_update_ha_state(hass: HomeAssistant) -> None:
    """Warn we log when entity update takes a long time and trow exception."""
    update_call = False

    async def async_update():
        """Mock async update."""
        nonlocal update_call
        update_call = True

    mock_entity = entity.Entity()
    mock_entity.hass = hass
    mock_entity.entity_id = "comp_test.test_entity"
    mock_entity.async_update = async_update

    mock_entity.async_schedule_update_ha_state(True)
    await hass.async_block_till_done()

    assert update_call is True


async def test_async_async_request_call_without_lock(hass: HomeAssistant) -> None:
    """Test for async_requests_call works without a lock."""
    updates = []

    class AsyncEntity(entity.Entity):
        """Test entity."""

        def __init__(self, entity_id: str) -> None:
            """Initialize Async test entity."""
            self.entity_id = entity_id
            self.hass = hass

        async def testhelper(self, count: int) -> None:
            """Helper function."""
            updates.append(count)

    ent_1 = AsyncEntity("light.test_1")
    ent_2 = AsyncEntity("light.test_2")
    try:
        job1 = ent_1.async_request_call(ent_1.testhelper(1))
        job2 = ent_2.async_request_call(ent_2.testhelper(2))

        await asyncio.gather(job1, job2)
        while True:
            if len(updates) >= 2:
                break
            await asyncio.sleep(0)
    finally:
        pass

    assert len(updates) == 2
    updates.sort()
    assert updates == [1, 2]


async def test_async_async_request_call_with_lock(hass: HomeAssistant) -> None:
    """Test for async_requests_call works with a semaphore."""
    updates = []

    test_semaphore = asyncio.Semaphore(1)

    class AsyncEntity(entity.Entity):
        """Test entity."""

        def __init__(self, entity_id: str, lock: asyncio.Semaphore) -> None:
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


async def test_async_parallel_updates_with_zero(hass: HomeAssistant) -> None:
    """Test parallel updates with 0 (disabled)."""
    updates = []
    test_lock = asyncio.Event()

    class AsyncEntity(entity.Entity):
        """Test entity."""

        def __init__(self, entity_id: str, count: int) -> None:
            """Initialize Async test entity."""
            self.entity_id = entity_id
            self.hass = hass
            self._count = count

        async def async_update(self) -> None:
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


async def test_async_parallel_updates_with_zero_on_sync_update(
    hass: HomeAssistant,
) -> None:
    """Test parallel updates with 0 (disabled)."""
    updates = []
    test_lock = threading.Event()

    class AsyncEntity(entity.Entity):
        """Test entity."""

        def __init__(self, entity_id: str, count: int) -> None:
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


async def test_async_parallel_updates_with_one(hass: HomeAssistant) -> None:
    """Test parallel updates with 1 (sequential)."""
    updates = []
    test_lock = asyncio.Lock()
    test_semaphore = asyncio.Semaphore(1)

    class AsyncEntity(entity.Entity):
        """Test entity."""

        def __init__(self, entity_id: str, count: int) -> None:
            """Initialize Async test entity."""
            self.entity_id = entity_id
            self.hass = hass
            self._count = count
            self.parallel_updates = test_semaphore

        async def async_update(self) -> None:
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


async def test_async_parallel_updates_with_two(hass: HomeAssistant) -> None:
    """Test parallel updates with 2 (parallel)."""
    updates = []
    test_lock = asyncio.Lock()
    test_semaphore = asyncio.Semaphore(2)

    class AsyncEntity(entity.Entity):
        """Test entity."""

        def __init__(self, entity_id: str, count: int) -> None:
            """Initialize Async test entity."""
            self.entity_id = entity_id
            self.hass = hass
            self._count = count
            self.parallel_updates = test_semaphore

        async def async_update(self) -> None:
            """Test update."""
            updates.append(self._count)
            await test_lock.acquire()

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


async def test_async_parallel_updates_with_one_using_executor(
    hass: HomeAssistant,
) -> None:
    """Test parallel updates with 1 (sequential) using the executor."""
    test_semaphore = asyncio.Semaphore(1)
    locked = []

    class SyncEntity(entity.Entity):
        """Test entity."""

        def __init__(self, entity_id: str) -> None:
            """Initialize sync test entity."""
            self.entity_id = entity_id
            self.hass = hass
            self.parallel_updates = test_semaphore

        def update(self) -> None:
            """Test update."""
            locked.append(self.parallel_updates.locked())

    entities = [SyncEntity(f"sensor.test_{i}") for i in range(3)]

    await asyncio.gather(
        *[
            hass.async_create_task(
                ent.async_update_ha_state(True),
                f"Entity schedule update ha state {ent.entity_id}",
            )
            for ent in entities
        ]
    )

    assert locked == [True, True, True]


async def test_async_remove_no_platform(hass: HomeAssistant) -> None:
    """Test async_remove method when no platform set."""
    ent = entity.Entity()
    ent.hass = hass
    ent.entity_id = "test.test"
    ent.async_write_ha_state()
    assert len(hass.states.async_entity_ids()) == 1
    await ent.async_remove()
    assert len(hass.states.async_entity_ids()) == 0


async def test_async_remove_runs_callbacks(hass: HomeAssistant) -> None:
    """Test async_remove runs on_remove callback."""
    result = []

    platform = MockEntityPlatform(hass, domain="test")
    ent = entity.Entity()
    ent.entity_id = "test.test"
    await platform.async_add_entities([ent])
    ent.async_on_remove(lambda: result.append(1))
    await ent.async_remove()
    assert len(result) == 1


async def test_async_remove_ignores_in_flight_polling(hass: HomeAssistant) -> None:
    """Test in flight polling is ignored after removing."""
    result = []

    platform = MockEntityPlatform(hass, domain="test")
    ent = entity.Entity()
    ent.entity_id = "test.test"
    ent.async_on_remove(lambda: result.append(1))
    await platform.async_add_entities([ent])
    assert hass.states.get("test.test").state == STATE_UNKNOWN

    # Remove the entity from the entity registry
    await ent.async_remove()
    assert len(result) == 1
    assert hass.states.get("test.test") is None

    # Simulate an in-flight poll after the entity was removed
    ent.async_write_ha_state()
    assert len(result) == 1
    assert hass.states.get("test.test") is None


async def test_async_remove_twice(hass: HomeAssistant) -> None:
    """Test removing an entity twice only cleans up once."""
    result = []

    class MockEntity(entity.Entity):
        def __init__(self) -> None:
            self.remove_calls = []

        async def async_will_remove_from_hass(self) -> None:
            self.remove_calls.append(None)

    platform = MockEntityPlatform(hass, domain="test")
    ent = MockEntity()
    ent.hass = hass
    ent.entity_id = "test.test"
    ent.async_on_remove(lambda: result.append(1))
    await platform.async_add_entities([ent])
    assert hass.states.get("test.test").state == STATE_UNKNOWN

    await ent.async_remove()
    assert len(result) == 1
    assert len(ent.remove_calls) == 1

    await ent.async_remove()
    assert len(result) == 1
    assert len(ent.remove_calls) == 1


async def test_set_context(hass: HomeAssistant) -> None:
    """Test setting context."""
    context = Context()
    ent = entity.Entity()
    ent.hass = hass
    ent.entity_id = "hello.world"
    ent.async_set_context(context)
    ent.async_write_ha_state()
    assert hass.states.get("hello.world").context == context


async def test_set_context_expired(hass: HomeAssistant) -> None:
    """Test setting context."""
    context = Context()

    with patch("homeassistant.helpers.entity.CONTEXT_RECENT_TIME_SECONDS", -5):
        ent = entity.Entity()
        ent.hass = hass
        ent.entity_id = "hello.world"
        ent.async_set_context(context)
        ent.async_write_ha_state()

    assert hass.states.get("hello.world").context != context
    assert ent._context is None
    assert ent._context_set is None


async def test_warn_disabled(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we warn once if we write to a disabled entity."""
    entry = er.RegistryEntry(
        entity_id="hello.world",
        unique_id="test-unique-id",
        platform="test-platform",
        disabled_by=er.RegistryEntryDisabler.USER,
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


async def test_disabled_in_entity_registry(hass: HomeAssistant) -> None:
    """Test entity is removed if we disable entity registry entry."""
    entry = er.RegistryEntry(
        entity_id="hello.world",
        unique_id="test-unique-id",
        platform="test-platform",
        disabled_by=None,
    )
    registry = mock_registry(hass, {"hello.world": entry})

    ent = entity.Entity()
    ent.hass = hass
    ent.entity_id = "hello.world"
    ent.registry_entry = entry
    assert ent.enabled is True

    ent.add_to_platform_start(hass, MagicMock(platform_name="test-platform"), None)
    await ent.add_to_platform_finish()
    assert hass.states.get("hello.world") is not None

    entry2 = registry.async_update_entity(
        "hello.world", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert entry2 != entry
    assert ent.registry_entry == entry2
    assert ent.enabled is False
    assert hass.states.get("hello.world") is None

    entry3 = registry.async_update_entity("hello.world", disabled_by=None)
    await hass.async_block_till_done()
    assert entry3 != entry2
    # Entry is no longer updated, entity is no longer tracking changes
    assert ent.registry_entry == entry2


async def test_capability_attrs(hass: HomeAssistant) -> None:
    """Test we still include capabilities even when unavailable."""
    with (
        patch.object(entity.Entity, "available", PropertyMock(return_value=False)),
        patch.object(
            entity.Entity,
            "capability_attributes",
            PropertyMock(return_value={"always": "there"}),
        ),
    ):
        ent = entity.Entity()
        ent.hass = hass
        ent.entity_id = "hello.world"
        ent.async_write_ha_state()

    state = hass.states.get("hello.world")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes["always"] == "there"


async def test_warn_slow_write_state(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
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
        "https://github.com/home-assistant/core/issues?"
        "q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+hue%22"
    ) in caplog.text


async def test_warn_slow_write_state_custom_component(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Check that we log a warning if reading properties takes too long."""

    class CustomComponentEntity(entity.Entity):
        """Custom component entity."""

        __module__ = "custom_components.bla.sensor"

    mock_entity = CustomComponentEntity()
    mock_entity.hass = hass
    mock_entity.entity_id = "comp_test.test_entity"
    mock_entity.platform = MagicMock(platform_name="hue")

    with patch("homeassistant.helpers.entity.timer", side_effect=[0, 10]):
        mock_entity.async_write_ha_state()

    assert (
        "Updating state for comp_test.test_entity (<class 'custom_components.bla.sensor"
        ".test_warn_slow_write_state_custom_component.<locals>.CustomComponentEntity'>)"
        " took 10.000 seconds. Please report it to the author of the 'hue' custom "
        "integration"
    ) in caplog.text


async def test_setup_source(hass: HomeAssistant) -> None:
    """Check that we register sources correctly."""
    platform = MockEntityPlatform(hass)

    entity_platform = MockEntity(name="Platform Config Source")
    await platform.async_add_entities([entity_platform])

    platform.config_entry = MockConfigEntry()
    entity_entry = MockEntity(name="Config Entry Source")
    await platform.async_add_entities([entity_entry])

    assert entity.entity_sources(hass) == {
        "test_domain.platform_config_source": {
            "custom_component": False,
            "domain": "test_platform",
        },
        "test_domain.config_entry_source": {
            "config_entry": platform.config_entry.entry_id,
            "custom_component": False,
            "domain": "test_platform",
        },
    }

    await platform.async_reset()

    assert entity.entity_sources(hass) == {}


async def test_removing_entity_unavailable(hass: HomeAssistant) -> None:
    """Test removing an entity that is still registered creates an unavailable state."""
    platform = MockEntityPlatform(hass, domain="hello")
    ent = entity.Entity()
    ent.entity_id = "hello.world"
    ent._attr_unique_id = "test-unique-id"
    await platform.async_add_entities([ent])

    state = hass.states.get("hello.world")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    await ent.async_remove()

    state = hass.states.get("hello.world")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_get_supported_features_entity_registry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test get_supported_features falls back to entity registry."""
    entity_id = entity_registry.async_get_or_create(
        "hello", "world", "5678", supported_features=456
    ).entity_id
    assert entity.get_supported_features(hass, entity_id) == 456


async def test_get_supported_features_prioritize_state(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test get_supported_features gives priority to state."""
    entity_id = entity_registry.async_get_or_create(
        "hello", "world", "5678", supported_features=456
    ).entity_id
    assert entity.get_supported_features(hass, entity_id) == 456

    hass.states.async_set(entity_id, None, {"supported_features": 123})

    assert entity.get_supported_features(hass, entity_id) == 123


async def test_get_supported_features_raises_on_unknown(hass: HomeAssistant) -> None:
    """Test get_supported_features raises on unknown entity_id."""
    with pytest.raises(HomeAssistantError):
        entity.get_supported_features(hass, "hello.world")


async def test_float_conversion(hass: HomeAssistant) -> None:
    """Test conversion of float state to string rounds."""
    assert 2.4 + 1.2 != 3.6
    with patch.object(entity.Entity, "state", PropertyMock(return_value=2.4 + 1.2)):
        ent = entity.Entity()
        ent.hass = hass
        ent.entity_id = "hello.world"
        ent.async_write_ha_state()

    state = hass.states.get("hello.world")
    assert state is not None
    assert state.state == "3.6"


async def test_attribution_attribute(hass: HomeAssistant) -> None:
    """Test attribution attribute."""
    mock_entity = entity.Entity()
    mock_entity.hass = hass
    mock_entity.entity_id = "hello.world"
    mock_entity._attr_attribution = "Home Assistant"

    mock_entity.async_schedule_update_ha_state(True)
    await hass.async_block_till_done()

    state = hass.states.get(mock_entity.entity_id)
    assert state.attributes.get(ATTR_ATTRIBUTION) == "Home Assistant"


async def test_entity_category_property(hass: HomeAssistant) -> None:
    """Test entity category property."""
    mock_entity1 = entity.Entity()
    mock_entity1.hass = hass
    mock_entity1.entity_description = entity.EntityDescription(
        key="abc", entity_category="ignore_me"
    )
    mock_entity1.entity_id = "hello.world"
    mock_entity1._attr_entity_category = EntityCategory.CONFIG
    assert mock_entity1.entity_category == "config"

    mock_entity2 = entity.Entity()
    mock_entity2.hass = hass
    mock_entity2.entity_description = entity.EntityDescription(
        key="abc", entity_category=EntityCategory.CONFIG
    )
    mock_entity2.entity_id = "hello.world"
    assert mock_entity2.entity_category == "config"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("config", EntityCategory.CONFIG),
        ("diagnostic", EntityCategory.DIAGNOSTIC),
    ],
)
def test_entity_category_schema(value, expected) -> None:
    """Test entity category schema."""
    schema = vol.Schema(entity.ENTITY_CATEGORIES_SCHEMA)
    result = schema(value)
    assert result == expected
    assert isinstance(result, EntityCategory)


@pytest.mark.parametrize("value", [None, "non_existing"])
def test_entity_category_schema_error(value) -> None:
    """Test entity category schema."""
    schema = vol.Schema(entity.ENTITY_CATEGORIES_SCHEMA)
    with pytest.raises(
        vol.Invalid,
        match=r"expected EntityCategory or one of 'config', 'diagnostic'",
    ):
        schema(value)


async def test_entity_description_fallback() -> None:
    """Test entity description has same defaults as entity."""
    ent = entity.Entity()
    ent_with_description = entity.Entity()
    ent_with_description.entity_description = entity.EntityDescription(key="test")

    for field in dataclasses.fields(entity.EntityDescription._dataclass):
        if field.name == "key":
            continue

        assert getattr(ent, field.name) == getattr(ent_with_description, field.name)


async def _test_friendly_name(
    hass: HomeAssistant,
    ent: entity.Entity,
    expected_friendly_name: str | None,
) -> None:
    """Test friendly name."""

    async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Mock setup entry method."""
        async_add_entities([ent])

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry(entry_id="super-mock-id")
    config_entry.add_to_hass(hass)
    entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    assert await entity_platform.async_setup_entry(config_entry)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1
    state = hass.states.async_all()[0]
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == expected_friendly_name

    await async_update_entity(hass, ent.entity_id)
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == expected_friendly_name


@pytest.mark.parametrize(
    (
        "has_entity_name",
        "entity_name",
        "device_name",
        "expected_friendly_name",
    ),
    [
        (False, "Entity Blu", "Device Bla", "Entity Blu"),
        (False, None, "Device Bla", None),
        (True, "Entity Blu", "Device Bla", "Device Bla Entity Blu"),
        (True, None, "Device Bla", "Device Bla"),
        (True, "Entity Blu", UNDEFINED, "Entity Blu"),
        (True, "Entity Blu", None, "Mock Title Entity Blu"),
    ],
)
async def test_friendly_name_attr(
    hass: HomeAssistant,
    has_entity_name: bool,
    entity_name: str | None,
    device_name: str | None | UndefinedType,
    expected_friendly_name: str | None,
) -> None:
    """Test friendly name when the entity uses _attr_*."""

    ent = MockEntity(
        unique_id="qwer",
        device_info={
            "identifiers": {("hue", "1234")},
            "connections": {(dr.CONNECTION_NETWORK_MAC, "abcd")},
            "name": device_name,
        },
    )
    ent._attr_has_entity_name = has_entity_name
    ent._attr_name = entity_name
    await _test_friendly_name(
        hass,
        ent,
        expected_friendly_name,
    )


@pytest.mark.parametrize(
    ("has_entity_name", "entity_name", "expected_friendly_name"),
    [
        (False, "Entity Blu", "Entity Blu"),
        (False, None, None),
        (False, UNDEFINED, None),
        (True, "Entity Blu", "Device Bla Entity Blu"),
        (True, None, "Device Bla"),
        (True, UNDEFINED, "Device Bla None"),
    ],
)
async def test_friendly_name_description(
    hass: HomeAssistant,
    has_entity_name: bool,
    entity_name: str | None,
    expected_friendly_name: str | None,
) -> None:
    """Test friendly name when the entity has an entity description."""

    ent = MockEntity(
        unique_id="qwer",
        device_info={
            "identifiers": {("hue", "1234")},
            "connections": {(dr.CONNECTION_NETWORK_MAC, "abcd")},
            "name": "Device Bla",
        },
    )
    ent.entity_description = entity.EntityDescription(
        "test", has_entity_name=has_entity_name, name=entity_name
    )
    await _test_friendly_name(
        hass,
        ent,
        expected_friendly_name,
    )


@pytest.mark.parametrize(
    ("has_entity_name", "entity_name", "expected_friendly_name"),
    [
        (False, "Entity Blu", "Entity Blu"),
        (False, None, None),
        (False, UNDEFINED, None),
        (True, "Entity Blu", "Device Bla Entity Blu"),
        (True, None, "Device Bla"),
        (True, UNDEFINED, "Device Bla English cls"),
    ],
)
async def test_friendly_name_description_device_class_name(
    hass: HomeAssistant,
    has_entity_name: bool,
    entity_name: str | None,
    expected_friendly_name: str | None,
) -> None:
    """Test friendly name when the entity has an entity description."""

    translations = {
        "en": {"component.test_domain.entity_component.test_class.name": "English cls"},
    }

    async def async_get_translations(
        hass: HomeAssistant,
        language: str,
        category: str,
        integrations: Iterable[str] | None = None,
        config_flow: bool | None = None,
    ) -> dict[str, Any]:
        """Return all backend translations."""
        return translations[language]

    class DeviceClassNameMockEntity(MockEntity):
        def _default_to_device_class_name(self) -> bool:
            """Return True if an unnamed entity should be named by its device class."""
            return True

    ent = DeviceClassNameMockEntity(
        unique_id="qwer",
        device_info={
            "identifiers": {("hue", "1234")},
            "connections": {(dr.CONNECTION_NETWORK_MAC, "abcd")},
            "name": "Device Bla",
        },
    )
    ent.entity_description = entity.EntityDescription(
        "test",
        device_class="test_class",
        has_entity_name=has_entity_name,
        name=entity_name,
    )
    with patch(
        "homeassistant.helpers.entity_platform.translation.async_get_translations",
        side_effect=async_get_translations,
    ):
        await _test_friendly_name(
            hass,
            ent,
            expected_friendly_name,
        )


@pytest.mark.parametrize(
    (
        "has_entity_name",
        "translation_key",
        "translations",
        "placeholders",
        "expected_friendly_name",
    ),
    [
        (False, None, None, None, "Entity Blu"),
        (True, None, None, None, "Device Bla Entity Blu"),
        (
            True,
            "test_entity",
            {
                "en": {
                    "component.test.entity.test_domain.test_entity.name": "English ent"
                },
            },
            None,
            "Device Bla English ent",
        ),
        (
            True,
            "test_entity",
            {
                "en": {
                    "component.test.entity.test_domain.test_entity.name": "{placeholder} English ent"
                },
            },
            {"placeholder": "special"},
            "Device Bla special English ent",
        ),
        (
            True,
            "test_entity",
            {
                "en": {
                    "component.test.entity.test_domain.test_entity.name": "English ent {placeholder}"
                },
            },
            {"placeholder": "special"},
            "Device Bla English ent special",
        ),
    ],
)
async def test_entity_name_translation_placeholders(
    hass: HomeAssistant,
    has_entity_name: bool,
    translation_key: str | None,
    translations: dict[str, str] | None,
    placeholders: dict[str, str] | None,
    expected_friendly_name: str | None,
) -> None:
    """Test friendly name when the entity name translation has placeholders."""

    async def async_get_translations(
        hass: HomeAssistant,
        language: str,
        category: str,
        integrations: Iterable[str] | None = None,
        config_flow: bool | None = None,
    ) -> dict[str, Any]:
        """Return all backend translations."""
        return translations[language]

    ent = MockEntity(
        unique_id="qwer",
        device_info={
            "identifiers": {("hue", "1234")},
            "connections": {(dr.CONNECTION_NETWORK_MAC, "abcd")},
            "name": "Device Bla",
        },
    )
    ent.entity_description = entity.EntityDescription(
        "test",
        has_entity_name=has_entity_name,
        translation_key=translation_key,
        name="Entity Blu",
    )
    if placeholders is not None:
        ent._attr_translation_placeholders = placeholders
    with patch(
        "homeassistant.helpers.entity_platform.translation.async_get_translations",
        side_effect=async_get_translations,
    ):
        await _test_friendly_name(hass, ent, expected_friendly_name)


@pytest.mark.parametrize(
    (
        "translation_key",
        "translations",
        "placeholders",
        "release_channel",
        "expected_error",
    ),
    [
        (
            "test_entity",
            {
                "en": {
                    "component.test.entity.test_domain.test_entity.name": "{placeholder} English ent {2ndplaceholder}"
                },
            },
            {"placeholder": "special"},
            ReleaseChannel.STABLE,
            (
                "has translation placeholders '{'placeholder': 'special'}' which do "
                "not match the name '{placeholder} English ent {2ndplaceholder}'"
            ),
        ),
        (
            "test_entity",
            {
                "en": {
                    "component.test.entity.test_domain.test_entity.name": "{placeholder} English ent {2ndplaceholder}"
                },
            },
            {"placeholder": "special"},
            ReleaseChannel.BETA,
            "HomeAssistantError: Missing placeholder '2ndplaceholder'",
        ),
        (
            "test_entity",
            {
                "en": {
                    "component.test.entity.test_domain.test_entity.name": "{placeholder} English ent"
                },
            },
            None,
            ReleaseChannel.STABLE,
            (
                "has translation placeholders '{}' which do "
                "not match the name '{placeholder} English ent'"
            ),
        ),
    ],
)
async def test_entity_name_translation_placeholder_errors(
    hass: HomeAssistant,
    translation_key: str | None,
    translations: dict[str, str] | None,
    placeholders: dict[str, str] | None,
    release_channel: ReleaseChannel,
    expected_error: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test entity name translation has placeholder issues."""

    async def async_get_translations(
        hass: HomeAssistant,
        language: str,
        category: str,
        integrations: Iterable[str] | None = None,
        config_flow: bool | None = None,
    ) -> dict[str, Any]:
        """Return all backend translations."""
        return translations[language]

    async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Mock setup entry method."""
        async_add_entities([ent])

    ent = MockEntity(
        unique_id="qwer",
    )
    ent.entity_description = entity.EntityDescription(
        "test",
        has_entity_name=True,
        translation_key=translation_key,
        name="Entity Blu",
    )
    if placeholders is not None:
        ent._attr_translation_placeholders = placeholders

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry(entry_id="super-mock-id")
    config_entry.add_to_hass(hass)
    entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    caplog.clear()

    with (
        patch(
            "homeassistant.helpers.entity_platform.translation.async_get_translations",
            side_effect=async_get_translations,
        ),
        patch(
            "homeassistant.helpers.entity.get_release_channel",
            return_value=release_channel,
        ),
    ):
        await entity_platform.async_setup_entry(config_entry)

    assert expected_error in caplog.text


@pytest.mark.parametrize(
    ("has_entity_name", "entity_name", "expected_friendly_name"),
    [
        (False, "Entity Blu", "Entity Blu"),
        (False, None, None),
        (False, UNDEFINED, None),
        (True, "Entity Blu", "Device Bla Entity Blu"),
        (True, None, "Device Bla"),
        (True, UNDEFINED, "Device Bla None"),
    ],
)
async def test_friendly_name_property(
    hass: HomeAssistant,
    has_entity_name: bool,
    entity_name: str | None,
    expected_friendly_name: str | None,
) -> None:
    """Test friendly name when the entity has overridden the name property."""

    ent = MockEntity(
        unique_id="qwer",
        device_info={
            "identifiers": {("hue", "1234")},
            "connections": {(dr.CONNECTION_NETWORK_MAC, "abcd")},
            "name": "Device Bla",
        },
        has_entity_name=has_entity_name,
        name=entity_name,
    )
    await _test_friendly_name(
        hass,
        ent,
        expected_friendly_name,
    )


@pytest.mark.parametrize(
    ("has_entity_name", "entity_name", "expected_friendly_name"),
    [
        (False, "Entity Blu", "Entity Blu"),
        (False, None, None),
        (False, UNDEFINED, None),
        (True, "Entity Blu", "Device Bla Entity Blu"),
        (True, None, "Device Bla"),
        # Won't use the device class name because the entity overrides the name property
        (True, UNDEFINED, "Device Bla None"),
    ],
)
async def test_friendly_name_property_device_class_name(
    hass: HomeAssistant,
    has_entity_name: bool,
    entity_name: str | None,
    expected_friendly_name: str | None,
) -> None:
    """Test friendly name when the entity has overridden the name property."""

    translations = {
        "en": {"component.test_domain.entity_component.test_class.name": "English cls"},
    }

    async def async_get_translations(
        hass: HomeAssistant,
        language: str,
        category: str,
        integrations: Iterable[str] | None = None,
        config_flow: bool | None = None,
    ) -> dict[str, Any]:
        """Return all backend translations."""
        return translations[language]

    class DeviceClassNameMockEntity(MockEntity):
        def _default_to_device_class_name(self) -> bool:
            """Return True if an unnamed entity should be named by its device class."""
            return True

    ent = DeviceClassNameMockEntity(
        unique_id="qwer",
        device_class="test_class",
        device_info={
            "identifiers": {("hue", "1234")},
            "connections": {(dr.CONNECTION_NETWORK_MAC, "abcd")},
            "name": "Device Bla",
        },
        has_entity_name=has_entity_name,
        name=entity_name,
    )
    with patch(
        "homeassistant.helpers.entity_platform.translation.async_get_translations",
        side_effect=async_get_translations,
    ):
        await _test_friendly_name(
            hass,
            ent,
            expected_friendly_name,
        )


@pytest.mark.parametrize(
    ("has_entity_name", "expected_friendly_name"),
    [
        (False, None),
        (True, "Device Bla English cls"),
    ],
)
async def test_friendly_name_device_class_name(
    hass: HomeAssistant,
    has_entity_name: bool,
    expected_friendly_name: str | None,
) -> None:
    """Test friendly name when the entity has not set the name in any way."""

    translations = {
        "en": {"component.test_domain.entity_component.test_class.name": "English cls"},
    }

    async def async_get_translations(
        hass: HomeAssistant,
        language: str,
        category: str,
        integrations: Iterable[str] | None = None,
        config_flow: bool | None = None,
    ) -> dict[str, Any]:
        """Return all backend translations."""
        return translations[language]

    class DeviceClassNameMockEntity(MockEntity):
        def _default_to_device_class_name(self) -> bool:
            """Return True if an unnamed entity should be named by its device class."""
            return True

    ent = DeviceClassNameMockEntity(
        unique_id="qwer",
        device_class="test_class",
        device_info={
            "identifiers": {("hue", "1234")},
            "connections": {(dr.CONNECTION_NETWORK_MAC, "abcd")},
            "name": "Device Bla",
        },
        has_entity_name=has_entity_name,
    )
    with patch(
        "homeassistant.helpers.entity_platform.translation.async_get_translations",
        side_effect=async_get_translations,
    ):
        await _test_friendly_name(
            hass,
            ent,
            expected_friendly_name,
        )


@pytest.mark.parametrize(
    (
        "entity_name",
        "expected_friendly_name1",
        "expected_friendly_name2",
        "expected_friendly_name3",
    ),
    [
        (
            "Entity Blu",
            "Device Bla Entity Blu",
            "Device Bla2 Entity Blu",
            "New Device Entity Blu",
        ),
        (
            None,
            "Device Bla",
            "Device Bla2",
            "New Device",
        ),
    ],
)
async def test_friendly_name_updated(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entity_name: str | None,
    expected_friendly_name1: str,
    expected_friendly_name2: str,
    expected_friendly_name3: str,
) -> None:
    """Test friendly name is updated when device or entity registry updates."""

    async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Mock setup entry method."""
        async_add_entities(
            [
                MockEntity(
                    unique_id="qwer",
                    device_info={
                        "identifiers": {("hue", "1234")},
                        "connections": {(dr.CONNECTION_NETWORK_MAC, "abcd")},
                        "name": "Device Bla",
                    },
                    has_entity_name=True,
                    name=entity_name,
                ),
            ]
        )

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry(entry_id="super-mock-id")
    config_entry.add_to_hass(hass)
    entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    assert await entity_platform.async_setup_entry(config_entry)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1
    state = hass.states.async_all()[0]
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == expected_friendly_name1

    device = device_registry.async_get_device(identifiers={("hue", "1234")})
    device_registry.async_update_device(device.id, name_by_user="Device Bla2")
    await hass.async_block_till_done()

    state = hass.states.async_all()[0]
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == expected_friendly_name2

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("hue", "5678")},
        name="New Device",
    )
    entity_registry.async_update_entity(state.entity_id, device_id=device.id)
    await hass.async_block_till_done()

    state = hass.states.async_all()[0]
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == expected_friendly_name3


async def test_translation_key(hass: HomeAssistant) -> None:
    """Test translation key property."""
    mock_entity1 = entity.Entity()
    mock_entity1.hass = hass
    mock_entity1.entity_description = entity.EntityDescription(
        key="abc", translation_key="from_entity_description"
    )
    mock_entity1.entity_id = "hello.world"
    mock_entity1._attr_translation_key = "from_attr"
    assert mock_entity1.translation_key == "from_attr"

    mock_entity2 = entity.Entity()
    mock_entity2.hass = hass
    mock_entity2.entity_description = entity.EntityDescription(
        key="abc", translation_key="from_entity_description"
    )
    mock_entity2.entity_id = "hello.world"
    assert mock_entity2.translation_key == "from_entity_description"


async def test_repr(hass: HomeAssistant) -> None:
    """Test Entity.__repr__."""

    class MyEntity(MockEntity):
        """Mock entity."""

        @property
        def state(self):
            """Return the state."""
            raise ValueError("Boom")

    platform = MockEntityPlatform(hass, domain="hello")
    my_entity = MyEntity(entity_id="test.test", available=False)

    # Not yet added
    assert str(my_entity) == "<entity unknown.unknown=unknown>"

    # Added
    await platform.async_add_entities([my_entity])
    assert str(my_entity) == "<entity test.test=unavailable>"

    # Removed
    await platform.async_remove_entity(my_entity.entity_id)
    assert str(my_entity) == "<entity unknown.unknown=unknown>"


async def test_warn_using_async_update_ha_state(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we warn once when using async_update_ha_state without force_update."""
    ent = entity.Entity()
    ent.hass = hass
    ent.platform = MockEntityPlatform(hass)
    ent.entity_id = "hello.world"
    error_message = "is using self.async_update_ha_state()"

    # When forcing, it should not trigger the warning
    caplog.clear()
    await ent.async_update_ha_state(force_refresh=True)
    assert error_message not in caplog.text

    # When not forcing, it should trigger the warning
    caplog.clear()
    await ent.async_update_ha_state()
    assert error_message in caplog.text

    # When not forcing, it should not trigger the warning again
    caplog.clear()
    await ent.async_update_ha_state()
    assert error_message not in caplog.text


async def test_warn_no_platform(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we warn am entity does not have a platform."""
    ent = entity.Entity()
    ent.hass = hass
    ent.platform = MockEntityPlatform(hass)
    ent.entity_id = "hello.world"
    error_message = "does not have a platform"

    # Without a platform, it should trigger the warning
    ent.platform = None
    caplog.clear()
    ent.async_write_ha_state()
    assert error_message in caplog.text

    # Without a platform, it should not trigger the warning again
    caplog.clear()
    ent.async_write_ha_state()
    assert error_message not in caplog.text

    # No warning if the entity has a platform
    caplog.clear()
    ent.async_write_ha_state()
    assert error_message not in caplog.text


async def test_invalid_state(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the entity helper catches InvalidState and sets state to unknown."""
    ent = entity.Entity()
    ent.entity_id = "test.test"
    ent.hass = hass

    ent._attr_state = "x" * 255
    ent.async_write_ha_state()
    assert hass.states.get("test.test").state == "x" * 255

    caplog.clear()
    ent._attr_state = "x" * 256
    ent.async_write_ha_state()
    assert hass.states.get("test.test").state == STATE_UNKNOWN
    assert (
        "homeassistant.helpers.entity",
        logging.ERROR,
        f"Failed to set state for test.test, fall back to {STATE_UNKNOWN}",
    ) in caplog.record_tuples

    ent._attr_state = "x" * 255
    ent.async_write_ha_state()
    assert hass.states.get("test.test").state == "x" * 255


async def test_suggest_report_issue_built_in(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test _suggest_report_issue for an entity from a built-in integration."""
    mock_entity = entity.Entity()
    mock_entity.entity_id = "comp_test.test_entity"

    suggestion = mock_entity._suggest_report_issue()
    assert suggestion == (
        "create a bug report at https://github.com/home-assistant/core/issues"
        "?q=is%3Aopen+is%3Aissue"
    )

    mock_integration(hass, MockModule(domain="test"), built_in=True)
    platform = MockEntityPlatform(hass, domain="comp_test", platform_name="test")
    await platform.async_add_entities([mock_entity])

    suggestion = mock_entity._suggest_report_issue()
    assert suggestion == (
        "create a bug report at https://github.com/home-assistant/core/issues"
        "?q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+test%22"
    )


async def test_suggest_report_issue_custom_component(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test _suggest_report_issue for an entity from a custom component."""

    class CustomComponentEntity(entity.Entity):
        """Custom component entity."""

        __module__ = "custom_components.bla.sensor"

    mock_entity = CustomComponentEntity()
    mock_entity.entity_id = "comp_test.test_entity"

    suggestion = mock_entity._suggest_report_issue()
    assert suggestion == "report it to the custom integration author"

    mock_integration(
        hass,
        MockModule(
            domain="test", partial_manifest={"issue_tracker": "https://some_url"}
        ),
        built_in=False,
    )
    platform = MockEntityPlatform(hass, domain="comp_test", platform_name="test")
    await platform.async_add_entities([mock_entity])

    suggestion = mock_entity._suggest_report_issue()
    assert suggestion == "create a bug report at https://some_url"


async def test_reuse_entity_object_after_abort(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reuse entity object."""
    platform = MockEntityPlatform(hass, domain="test")
    ent = entity.Entity()
    ent.entity_id = "invalid"
    await platform.async_add_entities([ent])
    assert "Invalid entity ID: invalid" in caplog.text
    await platform.async_add_entities([ent])
    assert (
        "Entity 'invalid' cannot be added a second time to an entity platform"
        in caplog.text
    )


async def test_reuse_entity_object_after_entity_registry_remove(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test reuse entity object."""
    entry = entity_registry.async_get_or_create("test", "test", "5678")
    platform = MockEntityPlatform(hass, domain="test", platform_name="test")
    ent = entity.Entity()
    ent._attr_unique_id = "5678"
    await platform.async_add_entities([ent])
    assert ent.registry_entry is entry
    assert len(hass.states.async_entity_ids()) == 1

    entity_registry.async_remove(entry.entity_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids()) == 0

    await platform.async_add_entities([ent])
    assert "Entity 'test.test_5678' cannot be added a second time" in caplog.text
    assert len(hass.states.async_entity_ids()) == 0


async def test_reuse_entity_object_after_entity_registry_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test reuse entity object."""
    entry = entity_registry.async_get_or_create("test", "test", "5678")
    platform = MockEntityPlatform(hass, domain="test", platform_name="test")
    ent = entity.Entity()
    ent._attr_unique_id = "5678"
    await platform.async_add_entities([ent])
    assert ent.registry_entry is entry
    assert len(hass.states.async_entity_ids()) == 1

    entity_registry.async_update_entity(
        entry.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids()) == 0

    await platform.async_add_entities([ent])
    assert len(hass.states.async_entity_ids()) == 0
    assert "Entity 'test.test_5678' cannot be added a second time" in caplog.text


async def test_change_entity_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test changing entity id."""
    result = []

    entry = entity_registry.async_get_or_create(
        "test", "test_platform", "5678", suggested_object_id="test"
    )
    assert entry.entity_id == "test.test"

    class MockEntity(entity.Entity):
        _attr_unique_id = "5678"

        def __init__(self) -> None:
            self.added_calls = []
            self.remove_calls = []

        async def async_added_to_hass(self):
            self.added_calls.append(None)
            self.async_on_remove(lambda: result.append(1))

        async def async_will_remove_from_hass(self):
            self.remove_calls.append(None)

    platform = MockEntityPlatform(hass, domain="test")
    ent = MockEntity()
    await platform.async_add_entities([ent])
    assert hass.states.get("test.test").state == STATE_UNKNOWN
    assert len(ent.added_calls) == 1

    entry = entity_registry.async_update_entity(
        entry.entity_id, new_entity_id="test.test2"
    )
    await hass.async_block_till_done()

    assert len(result) == 1
    assert len(ent.added_calls) == 2
    assert len(ent.remove_calls) == 1

    entity_registry.async_update_entity(entry.entity_id, new_entity_id="test.test3")
    await hass.async_block_till_done()

    assert len(result) == 2
    assert len(ent.added_calls) == 3
    assert len(ent.remove_calls) == 2


def test_entity_description_as_dataclass(snapshot: SnapshotAssertion) -> None:
    """Test EntityDescription behaves like a dataclass."""

    obj = entity.EntityDescription("blah", device_class="test")
    with pytest.raises(dataclasses.FrozenInstanceError):
        obj.name = "mutate"
    with pytest.raises(dataclasses.FrozenInstanceError):
        delattr(obj, "name")

    assert dataclasses.is_dataclass(obj)
    assert obj == snapshot
    assert obj == entity.EntityDescription("blah", device_class="test")
    assert repr(obj) == snapshot


def test_extending_entity_description(snapshot: SnapshotAssertion) -> None:
    """Test extending entity descriptions."""

    @dataclasses.dataclass(frozen=True)
    class FrozenEntityDescription(entity.EntityDescription):
        extra: str = None

    obj = FrozenEntityDescription("blah", extra="foo", name="name")
    assert obj == snapshot
    assert obj == FrozenEntityDescription("blah", extra="foo", name="name")
    assert repr(obj) == snapshot

    # Try mutating
    with pytest.raises(dataclasses.FrozenInstanceError):
        obj.name = "mutate"
    with pytest.raises(dataclasses.FrozenInstanceError):
        delattr(obj, "name")

    @dataclasses.dataclass
    class ThawedEntityDescription(entity.EntityDescription):
        extra: str = None

    obj = ThawedEntityDescription("blah", extra="foo", name="name")
    assert obj == snapshot
    assert obj == ThawedEntityDescription("blah", extra="foo", name="name")
    assert repr(obj) == snapshot

    # Try mutating
    obj.name = "mutate"
    assert obj.name == "mutate"
    delattr(obj, "key")
    assert not hasattr(obj, "key")

    # Try multiple levels of FrozenOrThawed
    class ExtendedEntityDescription(entity.EntityDescription, frozen_or_thawed=True):
        extension: str = None

    @dataclasses.dataclass(frozen=True)
    class MyExtendedEntityDescription(ExtendedEntityDescription):
        extra: str = None

    obj = MyExtendedEntityDescription("blah", extension="ext", extra="foo", name="name")
    assert obj == snapshot
    assert obj == MyExtendedEntityDescription(
        "blah", extension="ext", extra="foo", name="name"
    )
    assert repr(obj) == snapshot

    # Try multiple direct parents
    @dataclasses.dataclass(frozen=True)
    class MyMixin1:
        mixin: str

    @dataclasses.dataclass
    class MyMixin2:
        mixin: str

    @dataclasses.dataclass(frozen=True)
    class MyMixin3:
        mixin: str = None

    @dataclasses.dataclass
    class MyMixin4:
        mixin: str = None

    @dataclasses.dataclass(frozen=True, kw_only=True)
    class ComplexEntityDescription1A(MyMixin1, entity.EntityDescription):
        extra: str = None

    obj = ComplexEntityDescription1A(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert obj == snapshot
    assert obj == ComplexEntityDescription1A(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert repr(obj) == snapshot

    @dataclasses.dataclass(frozen=True, kw_only=True)
    class ComplexEntityDescription1B(entity.EntityDescription, MyMixin1):
        extra: str = None

    obj = ComplexEntityDescription1B(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert obj == snapshot
    assert obj == ComplexEntityDescription1B(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert repr(obj) == snapshot

    @dataclasses.dataclass(frozen=True)
    class ComplexEntityDescription1C(MyMixin1, entity.EntityDescription):
        extra: str = None

    obj = ComplexEntityDescription1C(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert obj == snapshot
    assert obj == ComplexEntityDescription1C(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert repr(obj) == snapshot

    @dataclasses.dataclass(frozen=True)
    class ComplexEntityDescription1D(entity.EntityDescription, MyMixin1):
        extra: str = None

    obj = ComplexEntityDescription1D(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert obj == snapshot
    assert obj == ComplexEntityDescription1D(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert repr(obj) == snapshot

    @dataclasses.dataclass(kw_only=True)
    class ComplexEntityDescription2A(MyMixin2, entity.EntityDescription):
        extra: str = None

    obj = ComplexEntityDescription2A(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert obj == snapshot
    assert obj == ComplexEntityDescription2A(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert repr(obj) == snapshot

    @dataclasses.dataclass(kw_only=True)
    class ComplexEntityDescription2B(entity.EntityDescription, MyMixin2):
        extra: str = None

    obj = ComplexEntityDescription2B(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert obj == snapshot
    assert obj == ComplexEntityDescription2B(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert repr(obj) == snapshot

    @dataclasses.dataclass
    class ComplexEntityDescription2C(MyMixin2, entity.EntityDescription):
        extra: str = None

    obj = ComplexEntityDescription2C(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert obj == snapshot
    assert obj == ComplexEntityDescription2C(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert repr(obj) == snapshot

    @dataclasses.dataclass
    class ComplexEntityDescription2D(entity.EntityDescription, MyMixin2):
        extra: str = None

    obj = ComplexEntityDescription2D(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert obj == snapshot
    assert obj == ComplexEntityDescription2D(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert repr(obj) == snapshot

    @dataclasses.dataclass(frozen=True, kw_only=True)
    class ComplexEntityDescription3A(MyMixin3, entity.EntityDescription):
        extra: str = None

    obj = ComplexEntityDescription3A(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert obj == snapshot
    assert obj == ComplexEntityDescription3A(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert repr(obj) == snapshot

    @dataclasses.dataclass(frozen=True, kw_only=True)
    class ComplexEntityDescription3B(entity.EntityDescription, MyMixin3):
        extra: str = None

    obj = ComplexEntityDescription3B(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert obj == snapshot
    assert obj == ComplexEntityDescription3B(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert repr(obj) == snapshot

    with pytest.raises(TypeError):

        @dataclasses.dataclass(frozen=True)
        class ComplexEntityDescription3C(MyMixin3, entity.EntityDescription):
            extra: str = None

    with pytest.raises(TypeError):

        @dataclasses.dataclass(frozen=True)
        class ComplexEntityDescription3D(entity.EntityDescription, MyMixin3):
            extra: str = None

    @dataclasses.dataclass(kw_only=True)
    class ComplexEntityDescription4A(MyMixin4, entity.EntityDescription):
        extra: str = None

    obj = ComplexEntityDescription4A(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert obj == snapshot
    assert obj == ComplexEntityDescription4A(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert repr(obj) == snapshot

    @dataclasses.dataclass(kw_only=True)
    class ComplexEntityDescription4B(entity.EntityDescription, MyMixin4):
        extra: str = None

    obj = ComplexEntityDescription4B(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert obj == snapshot
    assert obj == ComplexEntityDescription4B(
        key="blah", extra="foo", mixin="mixin", name="name"
    )
    assert repr(obj) == snapshot

    with pytest.raises(TypeError):

        @dataclasses.dataclass
        class ComplexEntityDescription4C(MyMixin4, entity.EntityDescription):
            extra: str = None

    with pytest.raises(TypeError):

        @dataclasses.dataclass
        class ComplexEntityDescription4D(entity.EntityDescription, MyMixin4):
            extra: str = None

    # Try inheriting with custom init
    @dataclasses.dataclass
    class CustomInitEntityDescription(entity.EntityDescription):
        def __init__(self, extra, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.extra: str = extra

    obj = CustomInitEntityDescription(key="blah", extra="foo", name="name")
    assert obj == snapshot
    assert obj == CustomInitEntityDescription(key="blah", extra="foo", name="name")
    assert repr(obj) == snapshot


async def test_update_capabilities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity capabilities are updated automatically."""
    platform = MockEntityPlatform(hass)

    ent = MockEntity(unique_id="qwer")
    await platform.async_add_entities([ent])

    entry = entity_registry.async_get(ent.entity_id)
    assert entry.capabilities is None
    assert entry.device_class is None
    assert entry.supported_features == 0

    ent._values["capability_attributes"] = {"bla": "blu"}
    ent._values["device_class"] = "some_class"
    ent._values["supported_features"] = 127
    ent.async_write_ha_state()
    entry = entity_registry.async_get(ent.entity_id)
    assert entry.capabilities == {"bla": "blu"}
    assert entry.original_device_class == "some_class"
    assert entry.supported_features == 127

    ent._values["capability_attributes"] = None
    ent._values["device_class"] = None
    ent._values["supported_features"] = None
    ent.async_write_ha_state()
    entry = entity_registry.async_get(ent.entity_id)
    assert entry.capabilities is None
    assert entry.original_device_class is None
    assert entry.supported_features == 0

    # Device class can be overridden by user, make sure that does not break the
    # automatic updating.
    entity_registry.async_update_entity(ent.entity_id, device_class="set_by_user")
    await hass.async_block_till_done()
    entry = entity_registry.async_get(ent.entity_id)
    assert entry.capabilities is None
    assert entry.original_device_class is None
    assert entry.supported_features == 0

    # This will not trigger a state change because the device class is shadowed
    # by the entity registry
    ent._values["device_class"] = "some_class"
    ent.async_write_ha_state()
    entry = entity_registry.async_get(ent.entity_id)
    assert entry.capabilities is None
    assert entry.original_device_class == "some_class"
    assert entry.supported_features == 0


async def test_update_capabilities_no_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity capabilities are updated automatically."""
    platform = MockEntityPlatform(hass)

    ent = MockEntity()
    await platform.async_add_entities([ent])

    assert entity_registry.async_get(ent.entity_id) is None

    ent._values["capability_attributes"] = {"bla": "blu"}
    ent._values["supported_features"] = 127
    ent.async_write_ha_state()
    assert entity_registry.async_get(ent.entity_id) is None


async def test_update_capabilities_too_often(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity capabilities are updated automatically."""
    capabilities_too_often_warning = "is updating its capabilities too often"
    platform = MockEntityPlatform(hass)

    ent = MockEntity(unique_id="qwer")
    await platform.async_add_entities([ent])

    entry = entity_registry.async_get(ent.entity_id)
    assert entry.capabilities is None
    assert entry.device_class is None
    assert entry.supported_features == 0

    for supported_features in range(1, entity.CAPABILITIES_UPDATE_LIMIT + 1):
        ent._values["capability_attributes"] = {"bla": "blu"}
        ent._values["device_class"] = "some_class"
        ent._values["supported_features"] = supported_features
        ent.async_write_ha_state()
        entry = entity_registry.async_get(ent.entity_id)
        assert entry.capabilities == {"bla": "blu"}
        assert entry.original_device_class == "some_class"
        assert entry.supported_features == supported_features

    assert capabilities_too_often_warning not in caplog.text

    ent._values["capability_attributes"] = {"bla": "blu"}
    ent._values["device_class"] = "some_class"
    ent._values["supported_features"] = supported_features + 1
    ent.async_write_ha_state()
    entry = entity_registry.async_get(ent.entity_id)
    assert entry.capabilities == {"bla": "blu"}
    assert entry.original_device_class == "some_class"
    assert entry.supported_features == supported_features + 1

    assert capabilities_too_often_warning in caplog.text


async def test_update_capabilities_too_often_cooldown(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entity capabilities are updated automatically."""
    capabilities_too_often_warning = "is updating its capabilities too often"
    platform = MockEntityPlatform(hass)

    ent = MockEntity(unique_id="qwer")
    await platform.async_add_entities([ent])

    entry = entity_registry.async_get(ent.entity_id)
    assert entry.capabilities is None
    assert entry.device_class is None
    assert entry.supported_features == 0

    for supported_features in range(1, entity.CAPABILITIES_UPDATE_LIMIT + 1):
        ent._values["capability_attributes"] = {"bla": "blu"}
        ent._values["device_class"] = "some_class"
        ent._values["supported_features"] = supported_features
        ent.async_write_ha_state()
        entry = entity_registry.async_get(ent.entity_id)
        assert entry.capabilities == {"bla": "blu"}
        assert entry.original_device_class == "some_class"
        assert entry.supported_features == supported_features

    assert capabilities_too_often_warning not in caplog.text

    freezer.tick(timedelta(minutes=60) + timedelta(seconds=1))

    ent._values["capability_attributes"] = {"bla": "blu"}
    ent._values["device_class"] = "some_class"
    ent._values["supported_features"] = supported_features + 1
    ent.async_write_ha_state()
    entry = entity_registry.async_get(ent.entity_id)
    assert entry.capabilities == {"bla": "blu"}
    assert entry.original_device_class == "some_class"
    assert entry.supported_features == supported_features + 1

    assert capabilities_too_often_warning not in caplog.text


@pytest.mark.parametrize(
    ("property", "default_value", "values"),
    [
        ("attribution", None, ["abcd", "efgh"]),
        ("attribution", None, [True, 1]),
        ("attribution", None, [1.0, 1]),
    ],
)
async def test_cached_entity_properties(
    hass: HomeAssistant, property: str, default_value: Any, values: Any
) -> None:
    """Test entity properties are cached."""
    ent1 = entity.Entity()
    ent2 = entity.Entity()
    assert getattr(ent1, property) == default_value
    assert type(getattr(ent1, property)) is type(default_value)
    assert getattr(ent2, property) == default_value
    assert type(getattr(ent2, property)) is type(default_value)

    # Test set
    setattr(ent1, f"_attr_{property}", values[0])
    assert getattr(ent1, property) == values[0]
    assert type(getattr(ent1, property)) is type(values[0])
    assert getattr(ent2, property) == default_value
    assert type(getattr(ent2, property)) is type(default_value)

    # Test update
    setattr(ent1, f"_attr_{property}", values[1])
    assert getattr(ent1, property) == values[1]
    assert type(getattr(ent1, property)) is type(values[1])
    assert getattr(ent2, property) == default_value
    assert type(getattr(ent2, property)) is type(default_value)

    # Test delete
    delattr(ent1, f"_attr_{property}")
    assert getattr(ent1, property) == default_value
    assert type(getattr(ent1, property)) is type(default_value)
    assert getattr(ent2, property) == default_value
    assert type(getattr(ent2, property)) is type(default_value)


async def test_cached_entity_property_delete_attr(hass: HomeAssistant) -> None:
    """Test deleting an _attr corresponding to a cached property."""
    property_name = "has_entity_name"

    ent = entity.Entity()
    assert not hasattr(ent, f"_attr_{property_name}")
    with pytest.raises(AttributeError):
        delattr(ent, f"_attr_{property_name}")
    assert getattr(ent, property_name) is False

    with pytest.raises(AttributeError):
        delattr(ent, f"_attr_{property_name}")
    assert not hasattr(ent, f"_attr_{property_name}")
    assert getattr(ent, property_name) is False

    setattr(ent, f"_attr_{property_name}", True)
    assert getattr(ent, property_name) is True

    delattr(ent, f"_attr_{property_name}")
    assert not hasattr(ent, f"_attr_{property_name}")
    assert getattr(ent, property_name) is False


async def test_cached_entity_property_class_attribute(hass: HomeAssistant) -> None:
    """Test entity properties on class level work in derived classes."""
    property_name = "attribution"
    values = ["abcd", "efgh"]

    class EntityWithClassAttribute1(entity.Entity):
        """A derived class which overrides an _attr_ from a parent."""

        _attr_attribution = values[0]

    class EntityWithClassAttribute2(entity.Entity, cached_properties={property}):
        """A derived class which overrides an _attr_ from a parent.

        This class also redundantly marks the overridden _attr_ as cached.
        """

        _attr_attribution = values[0]

    class EntityWithClassAttribute3(entity.Entity, cached_properties={property}):
        """A derived class which overrides an _attr_ from a parent.

        This class overrides the attribute property.
        """

        def __init__(self) -> None:
            self._attr_attribution = values[0]

        @cached_property
        def attribution(self) -> str | None:
            """Return the attribution."""
            return self._attr_attribution

    class EntityWithClassAttribute4(entity.Entity, cached_properties={property}):
        """A derived class which overrides an _attr_ from a parent.

        This class overrides the attribute property and the _attr_.
        """

        _attr_attribution = values[0]

        @cached_property
        def attribution(self) -> str | None:
            """Return the attribution."""
            return self._attr_attribution

    classes = (
        EntityWithClassAttribute1,
        EntityWithClassAttribute2,
        EntityWithClassAttribute3,
        EntityWithClassAttribute4,
    )

    entities: list[tuple[entity.Entity, entity.Entity]] = [
        (cls(), cls()) for cls in classes
    ]

    for ent in entities:
        assert getattr(ent[0], property_name) == values[0]
        assert getattr(ent[1], property_name) == values[0]

    # Test update
    for ent in entities:
        setattr(ent[0], f"_attr_{property_name}", values[1])
    for ent in entities:
        assert getattr(ent[0], property_name) == values[1]
        assert getattr(ent[1], property_name) == values[0]


async def test_cached_entity_property_override(hass: HomeAssistant) -> None:
    """Test overriding cached _attr_ raises."""

    class EntityWithClassAttribute1(entity.Entity):
        """A derived class which overrides an _attr_ from a parent."""

        _attr_attribution: str

    class EntityWithClassAttribute2(entity.Entity):
        """A derived class which overrides an _attr_ from a parent."""

        _attr_attribution = "blabla"

    class EntityWithClassAttribute3(entity.Entity):
        """A derived class which overrides an _attr_ from a parent."""

        _attr_attribution: str = "blabla"

    class EntityWithClassAttribute4(entity.Entity):
        @property
        def _attr_not_cached(self):
            return "blabla"

    class EntityWithClassAttribute5(entity.Entity):
        def _attr_not_cached(self):
            return "blabla"

    with pytest.raises(TypeError):

        class EntityWithClassAttribute6(entity.Entity):
            @property
            def _attr_attribution(self):
                return "🤡"

    with pytest.raises(TypeError):

        class EntityWithClassAttribute7(entity.Entity):
            def _attr_attribution(self):
                return "🤡"


async def test_entity_report_deprecated_supported_features_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test reporting deprecated supported feature values only happens once."""
    ent = entity.Entity()

    class MockEntityFeatures(IntFlag):
        VALUE1 = 1
        VALUE2 = 2

    ent._report_deprecated_supported_features_values(MockEntityFeatures(2))
    assert (
        "is using deprecated supported features values which will be removed"
        in caplog.text
    )
    assert "MockEntityFeatures.VALUE2" in caplog.text

    caplog.clear()
    ent._report_deprecated_supported_features_values(MockEntityFeatures(2))
    assert (
        "is using deprecated supported features values which will be removed"
        not in caplog.text
    )


async def test_remove_entity_registry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test removing an entity from the registry."""
    result = []

    entry = entity_registry.async_get_or_create(
        "test", "test_platform", "5678", suggested_object_id="test"
    )
    assert entry.entity_id == "test.test"

    class MockEntity(entity.Entity):
        _attr_unique_id = "5678"

        def __init__(self) -> None:
            self.added_calls = []
            self.remove_calls = []

        async def async_added_to_hass(self):
            self.added_calls.append(None)
            self.async_on_remove(lambda: result.append(1))

        async def async_will_remove_from_hass(self):
            self.remove_calls.append(None)

    platform = MockEntityPlatform(hass, domain="test")
    ent = MockEntity()
    await platform.async_add_entities([ent])
    assert hass.states.get("test.test").state == STATE_UNKNOWN
    assert len(ent.added_calls) == 1

    entry = entity_registry.async_remove(entry.entity_id)
    await hass.async_block_till_done()

    assert len(result) == 1
    assert len(ent.added_calls) == 1
    assert len(ent.remove_calls) == 1

    assert hass.states.get("test.test") is None


async def test_reset_right_after_remove_entity_registry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test resetting the platform right after removing an entity from the registry.

    A reset commonly happens during a reload.
    """
    result = []

    entry = entity_registry.async_get_or_create(
        "test", "test_platform", "5678", suggested_object_id="test"
    )
    assert entry.entity_id == "test.test"

    class MockEntity(entity.Entity):
        _attr_unique_id = "5678"

        def __init__(self) -> None:
            self.added_calls = []
            self.remove_calls = []

        async def async_added_to_hass(self):
            self.added_calls.append(None)
            self.async_on_remove(lambda: result.append(1))

        async def async_will_remove_from_hass(self):
            self.remove_calls.append(None)

    platform = MockEntityPlatform(hass, domain="test")
    ent = MockEntity()
    await platform.async_add_entities([ent])
    assert hass.states.get("test.test").state == STATE_UNKNOWN
    assert len(ent.added_calls) == 1

    entry = entity_registry.async_remove(entry.entity_id)

    # Reset the platform immediately after removing the entity from the registry
    await platform.async_reset()
    await hass.async_block_till_done()

    assert len(result) == 1
    assert len(ent.added_calls) == 1
    assert len(ent.remove_calls) == 1

    assert hass.states.get("test.test") is None


async def test_get_hassjob_type(hass: HomeAssistant) -> None:
    """Test get_hassjob_type."""

    class AsyncEntity(entity.Entity):
        """Test entity."""

        def update(self):
            """Test update Executor."""

        async def async_update(self):
            """Test update Coroutinefunction."""

        @callback
        def update_callback(self):
            """Test update Callback."""

    ent_1 = AsyncEntity()

    assert ent_1.get_hassjob_type("update") is HassJobType.Executor
    assert ent_1.get_hassjob_type("async_update") is HassJobType.Coroutinefunction
    assert ent_1.get_hassjob_type("update_callback") is HassJobType.Callback


async def test_async_write_ha_state_thread_safety(hass: HomeAssistant) -> None:
    """Test async_write_ha_state thread safety."""
    hass.config.debug = True

    ent = entity.Entity()
    ent.entity_id = "test.any"
    ent.hass = hass
    ent.async_write_ha_state()
    assert hass.states.get(ent.entity_id)

    ent2 = entity.Entity()
    ent2.entity_id = "test.any2"
    ent2.hass = hass
    with pytest.raises(
        RuntimeError,
        match="Detected code that calls async_write_ha_state from a thread.",
    ):
        await hass.async_add_executor_job(ent2.async_write_ha_state)
    assert not hass.states.get(ent2.entity_id)


async def test_async_write_ha_state_thread_safety_always(
    hass: HomeAssistant,
) -> None:
    """Test async_write_ha_state thread safe check."""

    ent = entity.Entity()
    ent.entity_id = "test.any"
    ent.hass = hass
    ent.platform = MockEntityPlatform(hass, domain="test")
    ent.async_write_ha_state()
    assert hass.states.get(ent.entity_id)

    ent2 = entity.Entity()
    ent2.entity_id = "test.any2"
    ent2.hass = hass
    ent2.platform = MockEntityPlatform(hass, domain="test")
    with pytest.raises(
        RuntimeError,
        match="Detected code that calls async_write_ha_state from a thread.",
    ):
        await hass.async_add_executor_job(ent2.async_write_ha_state)
    assert not hass.states.get(ent2.entity_id)
