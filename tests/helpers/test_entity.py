"""Test the entity helper."""
import asyncio
import dataclasses
from datetime import timedelta
import threading
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import voluptuous as vol

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, HomeAssistant, HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity, entity_registry as er

from tests.common import (
    MockConfigEntry,
    MockEntity,
    MockEntityPlatform,
    MockPlatform,
    get_test_home_assistant,
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

    ent.async_update = async_update_func

    await ent.async_update_ha_state(True)

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


async def test_async_parallel_updates_with_zero(hass: HomeAssistant) -> None:
    """Test parallel updates with 0 (disabled)."""
    updates = []
    test_lock = asyncio.Event()

    class AsyncEntity(entity.Entity):
        """Test entity."""

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


async def test_async_parallel_updates_with_zero_on_sync_update(
    hass: HomeAssistant,
) -> None:
    """Test parallel updates with 0 (disabled)."""
    updates = []
    test_lock = threading.Event()

    class AsyncEntity(entity.Entity):
        """Test entity."""

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


async def test_async_parallel_updates_with_one(hass: HomeAssistant) -> None:
    """Test parallel updates with 1 (sequential)."""
    updates = []
    test_lock = asyncio.Lock()
    test_semaphore = asyncio.Semaphore(1)

    class AsyncEntity(entity.Entity):
        """Test entity."""

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


async def test_async_parallel_updates_with_two(hass: HomeAssistant) -> None:
    """Test parallel updates with 2 (parallel)."""
    updates = []
    test_lock = asyncio.Lock()
    test_semaphore = asyncio.Semaphore(2)

    class AsyncEntity(entity.Entity):
        """Test entity."""

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


async def test_async_remove_no_platform(hass: HomeAssistant) -> None:
    """Test async_remove method when no platform set."""
    ent = entity.Entity()
    ent.hass = hass
    ent.entity_id = "test.test"
    await ent.async_update_ha_state()
    assert len(hass.states.async_entity_ids()) == 1
    await ent.async_remove()
    assert len(hass.states.async_entity_ids()) == 0


async def test_async_remove_runs_callbacks(hass: HomeAssistant) -> None:
    """Test async_remove method when no platform set."""
    result = []

    ent = entity.Entity()
    ent.hass = hass
    ent.entity_id = "test.test"
    ent.async_on_remove(lambda: result.append(1))
    await ent.async_remove()
    assert len(result) == 1


async def test_async_remove_ignores_in_flight_polling(hass: HomeAssistant) -> None:
    """Test in flight polling is ignored after removing."""
    result = []

    ent = entity.Entity()
    ent.hass = hass
    ent.entity_id = "test.test"
    ent.async_on_remove(lambda: result.append(1))
    ent.async_write_ha_state()
    assert hass.states.get("test.test").state == STATE_UNKNOWN
    await ent.async_remove()
    assert len(result) == 1
    assert hass.states.get("test.test") is None
    ent.async_write_ha_state()


async def test_set_context(hass: HomeAssistant) -> None:
    """Test setting context."""
    context = Context()
    ent = entity.Entity()
    ent.hass = hass
    ent.entity_id = "hello.world"
    ent.async_set_context(context)
    await ent.async_update_ha_state()
    assert hass.states.get("hello.world").context == context


async def test_set_context_expired(hass: HomeAssistant) -> None:
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
        "Updating state for comp_test.test_entity "
        "(<class 'custom_components.bla.sensor.test_warn_slow_write_state_custom_component.<locals>.CustomComponentEntity'>) "
        "took 10.000 seconds. Please report it to the custom integration author."
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
            "source": entity.SOURCE_PLATFORM_CONFIG,
        },
        "test_domain.config_entry_source": {
            "config_entry": platform.config_entry.entry_id,
            "custom_component": False,
            "domain": "test_platform",
            "source": entity.SOURCE_CONFIG_ENTRY,
        },
    }

    await platform.async_reset()

    assert entity.entity_sources(hass) == {}


async def test_removing_entity_unavailable(hass: HomeAssistant) -> None:
    """Test removing an entity that is still registered creates an unavailable state."""
    entry = er.RegistryEntry(
        entity_id="hello.world",
        unique_id="test-unique-id",
        platform="test-platform",
        disabled_by=None,
    )

    ent = entity.Entity()
    ent.hass = hass
    ent.entity_id = "hello.world"
    ent.registry_entry = entry
    ent.async_write_ha_state()

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
    mock_entity1._attr_entity_category = entity.EntityCategory.CONFIG
    assert mock_entity1.entity_category == "config"

    mock_entity2 = entity.Entity()
    mock_entity2.hass = hass
    mock_entity2.entity_description = entity.EntityDescription(
        key="abc", entity_category=entity.EntityCategory.CONFIG
    )
    mock_entity2.entity_id = "hello.world"
    assert mock_entity2.entity_category == "config"


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("config", entity.EntityCategory.CONFIG),
        ("diagnostic", entity.EntityCategory.DIAGNOSTIC),
    ),
)
def test_entity_category_schema(value, expected) -> None:
    """Test entity category schema."""
    schema = vol.Schema(entity.ENTITY_CATEGORIES_SCHEMA)
    result = schema(value)
    assert result == expected
    assert isinstance(result, entity.EntityCategory)


@pytest.mark.parametrize("value", (None, "non_existing"))
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

    for field in dataclasses.fields(entity.EntityDescription):
        if field.name == "key":
            continue

        assert getattr(ent, field.name) == getattr(ent_with_description, field.name)


@pytest.mark.parametrize(
    ("has_entity_name", "entity_name", "expected_friendly_name"),
    (
        (False, "Entity Blu", "Entity Blu"),
        (False, None, None),
        (True, "Entity Blu", "Device Bla Entity Blu"),
        (True, None, "Device Bla"),
    ),
)
async def test_friendly_name(
    hass: HomeAssistant, has_entity_name, entity_name, expected_friendly_name
) -> None:
    """Test entity_id is influenced by entity name."""

    async def async_setup_entry(hass, config_entry, async_add_entities):
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
                    has_entity_name=has_entity_name,
                    name=entity_name,
                ),
            ]
        )
        return True

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry(entry_id="super-mock-id")
    entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    assert await entity_platform.async_setup_entry(config_entry)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1
    state = hass.states.async_all()[0]
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == expected_friendly_name


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


async def test_repr_using_stringify_state() -> None:
    """Test that repr uses stringify state."""

    class MyEntity(MockEntity):
        """Mock entity."""

        @property
        def state(self):
            """Return the state."""
            raise ValueError("Boom")

    entity = MyEntity(entity_id="test.test", available=False)
    assert str(entity) == "<entity test.test=unavailable>"
