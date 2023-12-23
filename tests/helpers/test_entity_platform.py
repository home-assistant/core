"""Tests for the EntityPlatform helper."""
import asyncio
from collections.abc import Iterable
from datetime import timedelta
import logging
from typing import Any
from unittest.mock import ANY, Mock, patch

import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, PERCENTAGE
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.helpers import (
    device_registry as dr,
    entity_platform,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.entity import (
    DeviceInfo,
    Entity,
    EntityCategory,
    async_generate_entity_id,
)
from homeassistant.helpers.entity_component import (
    DEFAULT_SCAN_INTERVAL,
    EntityComponent,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry,
    MockEntity,
    MockEntityPlatform,
    MockPlatform,
    async_fire_time_changed,
    mock_entity_platform,
    mock_registry,
)

_LOGGER = logging.getLogger(__name__)
DOMAIN = "test_domain"
PLATFORM = "test_platform"


async def test_polling_only_updates_entities_it_should_poll(
    hass: HomeAssistant,
) -> None:
    """Test the polling of only updated entities."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, timedelta(seconds=20))
    await component.async_setup({})

    no_poll_ent = MockEntity(should_poll=False)
    no_poll_ent.async_update = Mock()
    poll_ent = MockEntity(should_poll=True)
    poll_ent.async_update = Mock()

    await component.async_add_entities([no_poll_ent, poll_ent])

    no_poll_ent.async_update.reset_mock()
    poll_ent.async_update.reset_mock()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()

    assert not no_poll_ent.async_update.called
    assert poll_ent.async_update.called


async def test_polling_disabled_by_config_entry(hass: HomeAssistant) -> None:
    """Test the polling of only updated entities."""
    entity_platform = MockEntityPlatform(hass)
    entity_platform.config_entry = MockConfigEntry(pref_disable_polling=True)

    poll_ent = MockEntity(should_poll=True)

    await entity_platform.async_add_entities([poll_ent])
    assert entity_platform._async_unsub_polling is None


async def test_polling_updates_entities_with_exception(hass: HomeAssistant) -> None:
    """Test the updated entities that not break with an exception."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, timedelta(seconds=20))
    await component.async_setup({})

    update_ok = []
    update_err = []

    def update_mock() -> None:
        """Mock normal update."""
        update_ok.append(None)

    def update_mock_err() -> None:
        """Mock error update."""
        update_err.append(None)
        raise AssertionError("Fake error update")

    ent1 = MockEntity(should_poll=True)
    ent1.update = update_mock_err
    ent2 = MockEntity(should_poll=True)
    ent2.update = update_mock
    ent3 = MockEntity(should_poll=True)
    ent3.update = update_mock
    ent4 = MockEntity(should_poll=True)
    ent4.update = update_mock

    await component.async_add_entities([ent1, ent2, ent3, ent4])

    update_ok.clear()
    update_err.clear()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()

    assert len(update_ok) == 3
    assert len(update_err) == 1


async def test_update_state_adds_entities(hass: HomeAssistant) -> None:
    """Test if updating poll entities cause an entity to be added works."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})

    ent1 = MockEntity()
    ent2 = MockEntity(should_poll=True)

    await component.async_add_entities([ent2])
    assert len(hass.states.async_entity_ids()) == 1
    ent2.update = lambda *_: component.add_entities([ent1])

    async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 2


async def test_update_state_adds_entities_with_update_before_add_true(
    hass: HomeAssistant,
) -> None:
    """Test if call update before add to state machine."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})

    ent = MockEntity()
    ent.update = Mock(spec_set=True)

    await component.async_add_entities([ent], True)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1
    assert ent.update.called


async def test_update_state_adds_entities_with_update_before_add_false(
    hass: HomeAssistant,
) -> None:
    """Test if not call update before add to state machine."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})

    ent = MockEntity()
    ent.update = Mock(spec_set=True)

    await component.async_add_entities([ent], False)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1
    assert not ent.update.called


@patch("homeassistant.helpers.entity_platform.async_track_time_interval")
async def test_set_scan_interval_via_platform(
    mock_track: Mock, hass: HomeAssistant
) -> None:
    """Test the setting of the scan interval via platform."""

    def platform_setup(
        hass: HomeAssistant,
        config: ConfigType,
        add_entities: entity_platform.AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        """Test the platform setup."""
        add_entities([MockEntity(should_poll=True)])

    platform = MockPlatform(platform_setup)
    platform.SCAN_INTERVAL = timedelta(seconds=30)

    mock_entity_platform(hass, "test_domain.platform", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    component.setup({DOMAIN: {"platform": "platform"}})

    await hass.async_block_till_done()
    assert mock_track.called
    assert timedelta(seconds=30) == mock_track.call_args[0][2]


async def test_adding_entities_with_generator_and_thread_callback(
    hass: HomeAssistant,
) -> None:
    """Test generator in add_entities that calls thread method.

    We should make sure we resolve the generator to a list before passing
    it into an async context.
    """
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})

    def create_entity(number: int) -> MockEntity:
        """Create entity helper."""
        entity = MockEntity(unique_id=f"unique{number}")
        entity.entity_id = async_generate_entity_id(DOMAIN + ".{}", "Number", hass=hass)
        return entity

    await component.async_add_entities(create_entity(i) for i in range(2))


async def test_platform_warn_slow_setup(hass: HomeAssistant) -> None:
    """Warn we log when platform setup takes a long time."""
    platform = MockPlatform()

    mock_entity_platform(hass, "test_domain.platform", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    with patch.object(hass.loop, "call_at") as mock_call:
        await component.async_setup({DOMAIN: {"platform": "platform"}})
        await hass.async_block_till_done()
        assert mock_call.called

        # mock_calls[3] is the warning message for component setup
        # mock_calls[10] is the warning message for platform setup
        timeout, logger_method = mock_call.mock_calls[10][1][:2]

        assert timeout - hass.loop.time() == pytest.approx(
            entity_platform.SLOW_SETUP_WARNING, 0.5
        )
        assert logger_method == _LOGGER.warning

        assert mock_call().cancel.called


async def test_platform_error_slow_setup(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Don't block startup more than SLOW_SETUP_MAX_WAIT."""
    with patch.object(entity_platform, "SLOW_SETUP_MAX_WAIT", 0):
        called = []

        async def setup_platform(*args):
            called.append(1)
            await asyncio.sleep(0.1)

        platform = MockPlatform(async_setup_platform=setup_platform)
        component = EntityComponent(_LOGGER, DOMAIN, hass)
        mock_entity_platform(hass, "test_domain.test_platform", platform)
        await component.async_setup({DOMAIN: {"platform": "test_platform"}})
        await hass.async_block_till_done()
        assert len(called) == 1
        assert "test_domain.test_platform" not in hass.config.components
        assert "test_platform is taking longer than 0 seconds" in caplog.text

    # Cleanup lingering (setup_platform) task after test is done
    await asyncio.sleep(0.1)


async def test_updated_state_used_for_entity_id(hass: HomeAssistant) -> None:
    """Test that first update results used for entity ID generation."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})

    class MockEntityNameFetcher(MockEntity):
        """Mock entity that fetches a friendly name."""

        async def async_update(self):
            """Mock update that assigns a name."""
            self._values["name"] = "Living Room"

    await component.async_add_entities([MockEntityNameFetcher()], True)

    entity_ids = hass.states.async_entity_ids()
    assert len(entity_ids) == 1
    assert entity_ids[0] == "test_domain.living_room"


async def test_parallel_updates_async_platform(hass: HomeAssistant) -> None:
    """Test async platform does not have parallel_updates limit by default."""
    platform = MockPlatform()

    mock_entity_platform(hass, "test_domain.platform", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    component._platforms = {}

    await component.async_setup({DOMAIN: {"platform": "platform"}})
    await hass.async_block_till_done()

    handle = list(component._platforms.values())[-1]
    assert handle.parallel_updates is None

    class AsyncEntity(MockEntity):
        """Mock entity that has async_update."""

        async def async_update(self):
            pass

    entity = AsyncEntity()
    await handle.async_add_entities([entity])
    assert entity.parallel_updates is None
    assert handle._update_in_sequence is False


async def test_parallel_updates_async_platform_with_constant(
    hass: HomeAssistant,
) -> None:
    """Test async platform can set parallel_updates limit."""
    platform = MockPlatform()
    platform.PARALLEL_UPDATES = 2

    mock_entity_platform(hass, "test_domain.platform", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    component._platforms = {}

    await component.async_setup({DOMAIN: {"platform": "platform"}})
    await hass.async_block_till_done()

    handle = list(component._platforms.values())[-1]

    class AsyncEntity(MockEntity):
        """Mock entity that has async_update."""

        async def async_update(self):
            pass

    entity = AsyncEntity()
    await handle.async_add_entities([entity])
    assert entity.parallel_updates is not None
    assert entity.parallel_updates._value == 2
    assert handle._update_in_sequence is False


async def test_parallel_updates_sync_platform(hass: HomeAssistant) -> None:
    """Test sync platform parallel_updates default set to 1."""
    platform = MockPlatform()

    mock_entity_platform(hass, "test_domain.platform", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    component._platforms = {}

    await component.async_setup({DOMAIN: {"platform": "platform"}})
    await hass.async_block_till_done()

    handle = list(component._platforms.values())[-1]

    class SyncEntity(MockEntity):
        """Mock entity that has update."""

        async def update(self):
            pass

    entity = SyncEntity()
    await handle.async_add_entities([entity])
    assert entity.parallel_updates is not None
    assert entity.parallel_updates._value == 1


async def test_parallel_updates_no_update_method(hass: HomeAssistant) -> None:
    """Test platform parallel_updates default set to 0."""
    platform = MockPlatform()

    mock_entity_platform(hass, "test_domain.platform", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    component._platforms = {}

    await component.async_setup({DOMAIN: {"platform": "platform"}})
    await hass.async_block_till_done()

    handle = list(component._platforms.values())[-1]

    entity = MockEntity()
    await handle.async_add_entities([entity])
    assert entity.parallel_updates is None


async def test_parallel_updates_sync_platform_with_constant(
    hass: HomeAssistant,
) -> None:
    """Test sync platform can set parallel_updates limit."""
    platform = MockPlatform()
    platform.PARALLEL_UPDATES = 2

    mock_entity_platform(hass, "test_domain.platform", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    component._platforms = {}

    await component.async_setup({DOMAIN: {"platform": "platform"}})
    await hass.async_block_till_done()

    handle = list(component._platforms.values())[-1]

    class SyncEntity(MockEntity):
        """Mock entity that has update."""

        async def update(self):
            pass

    entity = SyncEntity()
    await handle.async_add_entities([entity])
    assert entity.parallel_updates is not None
    assert entity.parallel_updates._value == 2


async def test_parallel_updates_async_platform_updates_in_parallel(
    hass: HomeAssistant,
) -> None:
    """Test an async platform is updated in parallel."""
    platform = MockPlatform()

    mock_entity_platform(hass, "test_domain.async_platform", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    component._platforms = {}

    await component.async_setup({DOMAIN: {"platform": "async_platform"}})
    await hass.async_block_till_done()

    handle = list(component._platforms.values())[-1]
    updating = []
    peak_update_count = 0

    class AsyncEntity(MockEntity):
        """Mock entity that has async_update."""

        async def async_update(self):
            pass

        async def async_update_ha_state(self, *args: Any, **kwargs: Any) -> None:
            nonlocal peak_update_count
            updating.append(self.entity_id)
            await asyncio.sleep(0)
            peak_update_count = max(len(updating), peak_update_count)
            await asyncio.sleep(0)
            updating.remove(self.entity_id)

    entity1 = AsyncEntity()
    entity2 = AsyncEntity()
    entity3 = AsyncEntity()

    await handle.async_add_entities([entity1, entity2, entity3])

    assert entity1.parallel_updates is None
    assert entity2.parallel_updates is None
    assert entity3.parallel_updates is None

    assert handle._update_in_sequence is False

    await handle._update_entity_states(dt_util.utcnow())
    assert peak_update_count > 1


async def test_parallel_updates_sync_platform_updates_in_sequence(
    hass: HomeAssistant,
) -> None:
    """Test a sync platform is updated in sequence."""
    platform = MockPlatform()

    mock_entity_platform(hass, "test_domain.platform", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    component._platforms = {}

    await component.async_setup({DOMAIN: {"platform": "platform"}})
    await hass.async_block_till_done()

    handle = list(component._platforms.values())[-1]
    updating = []
    peak_update_count = 0

    class SyncEntity(MockEntity):
        """Mock entity that has update."""

        def update(self):
            pass

        async def async_update_ha_state(self, *args: Any, **kwargs: Any) -> None:
            nonlocal peak_update_count
            updating.append(self.entity_id)
            await asyncio.sleep(0)
            peak_update_count = max(len(updating), peak_update_count)
            await asyncio.sleep(0)
            updating.remove(self.entity_id)

    entity1 = SyncEntity()
    entity2 = SyncEntity()
    entity3 = SyncEntity()

    await handle.async_add_entities([entity1, entity2, entity3])
    assert entity1.parallel_updates is not None
    assert entity1.parallel_updates._value == 1
    assert entity2.parallel_updates is not None
    assert entity2.parallel_updates._value == 1
    assert entity3.parallel_updates is not None
    assert entity3.parallel_updates._value == 1

    assert handle._update_in_sequence is True

    await handle._update_entity_states(dt_util.utcnow())
    assert peak_update_count == 1


async def test_raise_error_on_update(hass: HomeAssistant) -> None:
    """Test the add entity if they raise an error on update."""
    updates = []
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})
    entity1 = MockEntity(name="test_1")
    entity2 = MockEntity(name="test_2")

    def _raise() -> None:
        """Raise an exception."""
        raise AssertionError

    entity1.update = _raise
    entity2.update = lambda: updates.append(1)

    await component.async_add_entities([entity1, entity2], True)

    assert len(updates) == 1
    assert 1 in updates

    assert entity1.hass is None
    assert entity1.platform is None
    assert entity2.hass is not None
    assert entity2.platform is not None


async def test_async_remove_with_platform(hass: HomeAssistant) -> None:
    """Remove an entity from a platform."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})
    entity1 = MockEntity(name="test_1")
    await component.async_add_entities([entity1])
    assert len(hass.states.async_entity_ids()) == 1
    await entity1.async_remove()
    assert len(hass.states.async_entity_ids()) == 0


async def test_async_remove_with_platform_update_finishes(hass: HomeAssistant) -> None:
    """Remove an entity when an update finishes after its been removed."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})
    entity1 = MockEntity(name="test_1")

    async def _delayed_update(*args, **kwargs):
        await asyncio.sleep(0.01)

    entity1.async_update = _delayed_update

    # Add, remove, add, remove and make sure no updates
    # cause the entity to reappear after removal
    for _ in range(2):
        await component.async_add_entities([entity1])
        assert len(hass.states.async_entity_ids()) == 1
        entity1.async_write_ha_state()
        assert hass.states.get(entity1.entity_id) is not None
        task = asyncio.create_task(entity1.async_update_ha_state(True))
        await entity1.async_remove()
        assert len(hass.states.async_entity_ids()) == 0
        await task
        assert len(hass.states.async_entity_ids()) == 0


async def test_not_adding_duplicate_entities_with_unique_id(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for not adding duplicate entities.

    Also test that the entity registry is not updated for duplicates.
    """
    caplog.set_level(logging.ERROR)
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})

    ent1 = MockEntity(name="test1", unique_id="not_very_unique")
    await component.async_add_entities([ent1])

    assert len(hass.states.async_entity_ids()) == 1
    assert not caplog.text

    ent2 = MockEntity(name="test2", unique_id="not_very_unique")
    await component.async_add_entities([ent2])
    assert "test1" in caplog.text
    assert DOMAIN in caplog.text

    ent3 = MockEntity(
        name="test2", entity_id="test_domain.test3", unique_id="not_very_unique"
    )
    await component.async_add_entities([ent3])
    assert "test1" in caplog.text
    assert "test3" in caplog.text
    assert DOMAIN in caplog.text

    assert ent2.hass is None
    assert ent2.platform is None
    assert len(hass.states.async_entity_ids()) == 1

    registry = er.async_get(hass)
    # test the entity name was not updated
    entry = registry.async_get_or_create(DOMAIN, DOMAIN, "not_very_unique")
    assert entry.original_name == "test1"


async def test_using_prescribed_entity_id(hass: HomeAssistant) -> None:
    """Test for using predefined entity ID."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})
    await component.async_add_entities(
        [MockEntity(name="bla", entity_id="hello.world")]
    )
    assert "hello.world" in hass.states.async_entity_ids()


async def test_using_prescribed_entity_id_with_unique_id(hass: HomeAssistant) -> None:
    """Test for amending predefined entity ID because currently exists."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})

    await component.async_add_entities([MockEntity(entity_id="test_domain.world")])
    await component.async_add_entities(
        [MockEntity(entity_id="test_domain.world", unique_id="bla")]
    )

    assert "test_domain.world_2" in hass.states.async_entity_ids()


async def test_using_prescribed_entity_id_which_is_registered(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test not allowing predefined entity ID that already registered."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})
    # Register test_domain.world
    entity_registry.async_get_or_create(
        DOMAIN, "test", "1234", suggested_object_id="world"
    )

    # This entity_id will be rewritten
    await component.async_add_entities([MockEntity(entity_id="test_domain.world")])

    assert "test_domain.world_2" in hass.states.async_entity_ids()


async def test_name_which_conflict_with_registered(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test not generating conflicting entity ID based on name."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})

    # Register test_domain.world
    entity_registry.async_get_or_create(
        DOMAIN, "test", "1234", suggested_object_id="world"
    )

    await component.async_add_entities([MockEntity(name="world")])

    assert "test_domain.world_2" in hass.states.async_entity_ids()


async def test_entity_with_name_and_entity_id_getting_registered(
    hass: HomeAssistant,
) -> None:
    """Ensure that entity ID is used for registration."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})
    await component.async_add_entities(
        [MockEntity(unique_id="1234", name="bla", entity_id="test_domain.world")]
    )
    assert "test_domain.world" in hass.states.async_entity_ids()


async def test_overriding_name_from_registry(hass: HomeAssistant) -> None:
    """Test that we can override a name via the Entity Registry."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})
    mock_registry(
        hass,
        {
            "test_domain.world": er.RegistryEntry(
                entity_id="test_domain.world",
                unique_id="1234",
                # Using component.async_add_entities is equal to platform "domain"
                platform="test_domain",
                name="Overridden",
            )
        },
    )
    await component.async_add_entities(
        [MockEntity(unique_id="1234", name="Device Name")]
    )

    state = hass.states.get("test_domain.world")
    assert state is not None
    assert state.name == "Overridden"


async def test_registry_respect_entity_namespace(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that the registry respects entity namespace."""
    platform = MockEntityPlatform(hass, entity_namespace="ns")
    entity = MockEntity(unique_id="1234", name="Device Name")
    await platform.async_add_entities([entity])
    assert entity.entity_id == "test_domain.ns_device_name"


async def test_registry_respect_entity_disabled(hass: HomeAssistant) -> None:
    """Test that the registry respects entity disabled."""
    mock_registry(
        hass,
        {
            "test_domain.world": er.RegistryEntry(
                entity_id="test_domain.world",
                unique_id="1234",
                # Using component.async_add_entities is equal to platform "domain"
                platform="test_platform",
                disabled_by=er.RegistryEntryDisabler.USER,
            )
        },
    )
    platform = MockEntityPlatform(hass)
    entity = MockEntity(unique_id="1234")
    await platform.async_add_entities([entity])
    assert entity.entity_id == "test_domain.world"
    assert hass.states.async_entity_ids() == []


async def test_unique_id_conflict_has_priority_over_disabled_entity(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an entity that is not unique has priority over a disabled entity."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})
    entity1 = MockEntity(
        name="test1", unique_id="not_very_unique", enabled_by_default=False
    )
    entity2 = MockEntity(
        name="test2", unique_id="not_very_unique", enabled_by_default=False
    )
    await component.async_add_entities([entity1])
    await component.async_add_entities([entity2])

    assert len(hass.states.async_entity_ids()) == 1
    assert "Platform test_domain does not generate unique IDs." in caplog.text
    assert entity1.registry_entry is not None
    assert entity2.registry_entry is None
    registry = er.async_get(hass)
    # test the entity name was not updated
    entry = registry.async_get_or_create(DOMAIN, DOMAIN, "not_very_unique")
    assert entry.original_name == "test1"


async def test_entity_registry_updates_name(hass: HomeAssistant) -> None:
    """Test that updates on the entity registry update platform entities."""
    registry = mock_registry(
        hass,
        {
            "test_domain.world": er.RegistryEntry(
                entity_id="test_domain.world",
                unique_id="1234",
                # Using component.async_add_entities is equal to platform "domain"
                platform="test_platform",
                name="before update",
            )
        },
    )
    platform = MockEntityPlatform(hass)
    entity = MockEntity(unique_id="1234")
    await platform.async_add_entities([entity])

    state = hass.states.get("test_domain.world")
    assert state is not None
    assert state.name == "before update"

    registry.async_update_entity("test_domain.world", name="after update")
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get("test_domain.world")
    assert state.name == "after update"


async def test_setup_entry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test we can setup an entry."""

    async def async_setup_entry(hass, config_entry, async_add_entities):
        """Mock setup entry method."""
        async_add_entities([MockEntity(name="test1", unique_id="unique")])
        return True

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry(entry_id="super-mock-id")
    entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    assert await entity_platform.async_setup_entry(config_entry)
    await hass.async_block_till_done()
    full_name = f"{entity_platform.domain}.{config_entry.domain}"
    assert full_name in hass.config.components
    assert len(hass.states.async_entity_ids()) == 1
    assert len(entity_registry.entities) == 1
    assert (
        entity_registry.entities["test_domain.test1"].config_entry_id == "super-mock-id"
    )


async def test_setup_entry_platform_not_ready(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test when an entry is not ready yet."""
    async_setup_entry = Mock(side_effect=PlatformNotReady)
    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry()
    ent_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    with patch.object(entity_platform, "async_call_later") as mock_call_later:
        assert not await ent_platform.async_setup_entry(config_entry)

    full_name = f"{ent_platform.domain}.{config_entry.domain}"
    assert full_name not in hass.config.components
    assert len(async_setup_entry.mock_calls) == 1
    assert "Platform test not ready yet" in caplog.text
    assert len(mock_call_later.mock_calls) == 1


async def test_setup_entry_platform_not_ready_with_message(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test when an entry is not ready yet that includes a message."""
    async_setup_entry = Mock(side_effect=PlatformNotReady("lp0 on fire"))
    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry()
    ent_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    with patch.object(entity_platform, "async_call_later") as mock_call_later:
        assert not await ent_platform.async_setup_entry(config_entry)

    full_name = f"{ent_platform.domain}.{config_entry.domain}"
    assert full_name not in hass.config.components
    assert len(async_setup_entry.mock_calls) == 1

    assert "Platform test not ready yet" in caplog.text
    assert "lp0 on fire" in caplog.text
    assert len(mock_call_later.mock_calls) == 1


async def test_setup_entry_platform_not_ready_from_exception(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test when an entry is not ready yet that includes the causing exception string."""
    original_exception = HomeAssistantError("The device dropped the connection")
    platform_exception = PlatformNotReady()
    platform_exception.__cause__ = original_exception

    async_setup_entry = Mock(side_effect=platform_exception)
    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry()
    ent_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    with patch.object(entity_platform, "async_call_later") as mock_call_later:
        assert not await ent_platform.async_setup_entry(config_entry)

    full_name = f"{ent_platform.domain}.{config_entry.domain}"
    assert full_name not in hass.config.components
    assert len(async_setup_entry.mock_calls) == 1

    assert "Platform test not ready yet" in caplog.text
    assert "The device dropped the connection" in caplog.text
    assert len(mock_call_later.mock_calls) == 1


async def test_reset_cancels_retry_setup(hass: HomeAssistant) -> None:
    """Test that resetting a platform will cancel scheduled a setup retry."""
    async_setup_entry = Mock(side_effect=PlatformNotReady)
    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry()
    ent_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    with patch.object(entity_platform, "async_call_later") as mock_call_later:
        assert not await ent_platform.async_setup_entry(config_entry)

    assert len(mock_call_later.mock_calls) == 1
    assert len(mock_call_later.return_value.mock_calls) == 0
    assert ent_platform._async_cancel_retry_setup is not None

    await ent_platform.async_reset()

    assert len(mock_call_later.return_value.mock_calls) == 1
    assert ent_platform._async_cancel_retry_setup is None


async def test_reset_cancels_retry_setup_when_not_started(hass: HomeAssistant) -> None:
    """Test that resetting a platform will cancel scheduled a setup retry when not yet started."""
    hass.state = CoreState.starting
    async_setup_entry = Mock(side_effect=PlatformNotReady)
    initial_listeners = hass.bus.async_listeners()[EVENT_HOMEASSISTANT_STARTED]

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry()
    ent_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    assert not await ent_platform.async_setup_entry(config_entry)
    await hass.async_block_till_done()
    assert (
        hass.bus.async_listeners()[EVENT_HOMEASSISTANT_STARTED] == initial_listeners + 1
    )
    assert ent_platform._async_cancel_retry_setup is not None

    await ent_platform.async_reset()
    await hass.async_block_till_done()
    assert hass.bus.async_listeners()[EVENT_HOMEASSISTANT_STARTED] == initial_listeners
    assert ent_platform._async_cancel_retry_setup is None


async def test_stop_shutdown_cancels_retry_setup_and_interval_listener(
    hass: HomeAssistant,
) -> None:
    """Test that shutdown will cancel scheduled a setup retry and interval listener."""
    async_setup_entry = Mock(side_effect=PlatformNotReady)
    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry()
    ent_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    with patch.object(entity_platform, "async_call_later") as mock_call_later:
        assert not await ent_platform.async_setup_entry(config_entry)

    assert len(mock_call_later.mock_calls) == 1
    assert len(mock_call_later.return_value.mock_calls) == 0
    assert ent_platform._async_cancel_retry_setup is not None

    await ent_platform.async_shutdown()

    assert len(mock_call_later.return_value.mock_calls) == 1
    assert ent_platform._async_unsub_polling is None
    assert ent_platform._async_cancel_retry_setup is None


async def test_not_fails_with_adding_empty_entities_(hass: HomeAssistant) -> None:
    """Test for not fails on empty entities list."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    await component.async_add_entities([])

    assert len(hass.states.async_entity_ids()) == 0


async def test_entity_registry_updates_entity_id(hass: HomeAssistant) -> None:
    """Test that updates on the entity registry update platform entities."""
    registry = mock_registry(
        hass,
        {
            "test_domain.world": er.RegistryEntry(
                entity_id="test_domain.world",
                unique_id="1234",
                # Using component.async_add_entities is equal to platform "domain"
                platform="test_platform",
                name="Some name",
            )
        },
    )
    platform = MockEntityPlatform(hass)
    entity = MockEntity(unique_id="1234")
    await platform.async_add_entities([entity])

    state = hass.states.get("test_domain.world")
    assert state is not None
    assert state.name == "Some name"

    registry.async_update_entity(
        "test_domain.world", new_entity_id="test_domain.planet"
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert hass.states.get("test_domain.world") is None
    assert hass.states.get("test_domain.planet") is not None


async def test_entity_registry_updates_invalid_entity_id(hass: HomeAssistant) -> None:
    """Test that we can't update to an invalid entity id."""
    registry = mock_registry(
        hass,
        {
            "test_domain.world": er.RegistryEntry(
                entity_id="test_domain.world",
                unique_id="1234",
                # Using component.async_add_entities is equal to platform "domain"
                platform="test_platform",
                name="Some name",
            ),
            "test_domain.existing": er.RegistryEntry(
                entity_id="test_domain.existing",
                unique_id="5678",
                platform="test_platform",
            ),
        },
    )
    platform = MockEntityPlatform(hass)
    entity = MockEntity(unique_id="1234")
    await platform.async_add_entities([entity])

    state = hass.states.get("test_domain.world")
    assert state is not None
    assert state.name == "Some name"

    with pytest.raises(ValueError):
        registry.async_update_entity(
            "test_domain.world", new_entity_id="test_domain.existing"
        )

    with pytest.raises(ValueError):
        registry.async_update_entity(
            "test_domain.world", new_entity_id="invalid_entity_id"
        )

    with pytest.raises(ValueError):
        registry.async_update_entity(
            "test_domain.world", new_entity_id="diff_domain.world"
        )

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert hass.states.get("test_domain.world") is not None
    assert hass.states.get("invalid_entity_id") is None
    assert hass.states.get("diff_domain.world") is None


async def test_device_info_called(hass: HomeAssistant) -> None:
    """Test device info is forwarded correctly."""
    registry = dr.async_get(hass)
    config_entry = MockConfigEntry(entry_id="super-mock-id")
    config_entry.add_to_hass(hass)
    via = registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections=set(),
        identifiers={("hue", "via-id")},
        manufacturer="manufacturer",
        model="via",
    )

    async def async_setup_entry(hass, config_entry, async_add_entities):
        """Mock setup entry method."""
        async_add_entities(
            [
                # Invalid device info
                MockEntity(unique_id="abcd", device_info={}),
                # Valid device info
                MockEntity(
                    unique_id="qwer",
                    device_info={
                        "identifiers": {("hue", "1234")},
                        "configuration_url": "http://192.168.0.100/config",
                        "connections": {(dr.CONNECTION_NETWORK_MAC, "abcd")},
                        "manufacturer": "test-manuf",
                        "model": "test-model",
                        "name": "test-name",
                        "sw_version": "test-sw",
                        "hw_version": "test-hw",
                        "suggested_area": "Heliport",
                        "entry_type": dr.DeviceEntryType.SERVICE,
                        "via_device": ("hue", "via-id"),
                    },
                ),
            ]
        )
        return True

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    assert await entity_platform.async_setup_entry(config_entry)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 2

    device = registry.async_get_device(identifiers={("hue", "1234")})
    assert device is not None
    assert device.identifiers == {("hue", "1234")}
    assert device.configuration_url == "http://192.168.0.100/config"
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, "abcd")}
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.manufacturer == "test-manuf"
    assert device.model == "test-model"
    assert device.name == "test-name"
    assert device.suggested_area == "Heliport"
    assert device.sw_version == "test-sw"
    assert device.hw_version == "test-hw"
    assert device.via_device_id == via.id


async def test_device_info_not_overrides(hass: HomeAssistant) -> None:
    """Test device info is forwarded correctly."""
    registry = dr.async_get(hass)
    config_entry = MockConfigEntry(entry_id="super-mock-id")
    config_entry.add_to_hass(hass)
    device = registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "abcd")},
        manufacturer="test-manufacturer",
        model="test-model",
    )

    assert device.manufacturer == "test-manufacturer"
    assert device.model == "test-model"

    async def async_setup_entry(hass, config_entry, async_add_entities):
        """Mock setup entry method."""
        async_add_entities(
            [
                MockEntity(
                    unique_id="qwer",
                    device_info={
                        "connections": {(dr.CONNECTION_NETWORK_MAC, "abcd")},
                        "default_name": "default name 1",
                        "default_model": "default model 1",
                        "default_manufacturer": "default manufacturer 1",
                    },
                )
            ]
        )
        return True

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    assert await entity_platform.async_setup_entry(config_entry)
    await hass.async_block_till_done()

    device2 = registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, "abcd")}
    )
    assert device2 is not None
    assert device.id == device2.id
    assert device2.manufacturer == "test-manufacturer"
    assert device2.model == "test-model"


async def test_device_info_homeassistant_url(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test device info with homeassistant URL."""
    registry = dr.async_get(hass)
    config_entry = MockConfigEntry(entry_id="super-mock-id")
    config_entry.add_to_hass(hass)
    registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections=set(),
        identifiers={("mqtt", "via-id")},
        manufacturer="manufacturer",
        model="via",
    )

    async def async_setup_entry(hass, config_entry, async_add_entities):
        """Mock setup entry method."""
        async_add_entities(
            [
                # Valid device info, with homeassistant url
                MockEntity(
                    unique_id="qwer",
                    device_info={
                        "identifiers": {("mqtt", "1234")},
                        "configuration_url": "homeassistant://config/mqtt",
                    },
                ),
            ]
        )
        return True

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    assert await entity_platform.async_setup_entry(config_entry)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1

    device = registry.async_get_device(identifiers={("mqtt", "1234")})
    assert device is not None
    assert device.identifiers == {("mqtt", "1234")}
    assert device.configuration_url == "homeassistant://config/mqtt"


async def test_device_info_change_to_no_url(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test device info changes to no URL."""
    registry = dr.async_get(hass)
    config_entry = MockConfigEntry(entry_id="super-mock-id")
    config_entry.add_to_hass(hass)
    registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections=set(),
        identifiers={("mqtt", "via-id")},
        manufacturer="manufacturer",
        model="via",
        configuration_url="homeassistant://config/mqtt",
    )

    async def async_setup_entry(hass, config_entry, async_add_entities):
        """Mock setup entry method."""
        async_add_entities(
            [
                # Valid device info, with homeassistant url
                MockEntity(
                    unique_id="qwer",
                    device_info={
                        "identifiers": {("mqtt", "1234")},
                        "configuration_url": None,
                    },
                ),
            ]
        )
        return True

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    assert await entity_platform.async_setup_entry(config_entry)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1

    device = registry.async_get_device(identifiers={("mqtt", "1234")})
    assert device is not None
    assert device.identifiers == {("mqtt", "1234")}
    assert device.configuration_url is None


async def test_entity_disabled_by_integration(hass: HomeAssistant) -> None:
    """Test entity disabled by integration."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, timedelta(seconds=20))
    await component.async_setup({})

    entity_default = MockEntity(unique_id="default")
    entity_disabled = MockEntity(
        unique_id="disabled", entity_registry_enabled_default=False
    )

    await component.async_add_entities([entity_default, entity_disabled])

    assert entity_default.hass is not None
    assert entity_default.platform is not None
    assert entity_disabled.hass is None
    assert entity_disabled.platform is None

    registry = er.async_get(hass)

    entry_default = registry.async_get_or_create(DOMAIN, DOMAIN, "default")
    assert entry_default.disabled_by is None
    entry_disabled = registry.async_get_or_create(DOMAIN, DOMAIN, "disabled")
    assert entry_disabled.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_entity_disabled_by_device(hass: HomeAssistant) -> None:
    """Test entity disabled by device."""

    connections = {(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")}
    entity_disabled = MockEntity(
        unique_id="disabled", device_info=DeviceInfo(connections=connections)
    )

    async def async_setup_entry(hass, config_entry, async_add_entities):
        """Mock setup entry method."""
        async_add_entities([entity_disabled])
        return True

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry(entry_id="super-mock-id", domain=DOMAIN)
    config_entry.add_to_hass(hass)
    entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections=connections,
        disabled_by=dr.DeviceEntryDisabler.USER,
    )

    assert await entity_platform.async_setup_entry(config_entry)
    await hass.async_block_till_done()

    assert entity_disabled.hass is None
    assert entity_disabled.platform is None

    registry = er.async_get(hass)

    entry_disabled = registry.async_get_or_create(DOMAIN, DOMAIN, "disabled")
    assert entry_disabled.disabled_by is er.RegistryEntryDisabler.DEVICE


async def test_entity_hidden_by_integration(hass: HomeAssistant) -> None:
    """Test entity hidden by integration."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, timedelta(seconds=20))
    await component.async_setup({})

    entity_default = MockEntity(unique_id="default")
    entity_hidden = MockEntity(
        unique_id="hidden", entity_registry_visible_default=False
    )

    await component.async_add_entities([entity_default, entity_hidden])

    registry = er.async_get(hass)

    entry_default = registry.async_get_or_create(DOMAIN, DOMAIN, "default")
    assert entry_default.hidden_by is None
    entry_hidden = registry.async_get_or_create(DOMAIN, DOMAIN, "hidden")
    assert entry_hidden.hidden_by is er.RegistryEntryHider.INTEGRATION


async def test_entity_info_added_to_entity_registry(hass: HomeAssistant) -> None:
    """Test entity info is written to entity registry."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, timedelta(seconds=20))
    await component.async_setup({})

    entity_default = MockEntity(
        capability_attributes={"max": 100},
        device_class="mock-device-class",
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
        icon="nice:icon",
        name="best name",
        supported_features=5,
        translation_key="my_translation_key",
        unique_id="default",
        unit_of_measurement=PERCENTAGE,
    )

    await component.async_add_entities([entity_default])

    registry = er.async_get(hass)

    entry_default = registry.async_get_or_create(DOMAIN, DOMAIN, "default")
    assert entry_default == er.RegistryEntry(
        "test_domain.best_name",
        "default",
        "test_domain",
        capabilities={"max": 100},
        device_class=None,
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
        icon=None,
        id=ANY,
        name=None,
        original_device_class="mock-device-class",
        original_icon="nice:icon",
        original_name="best name",
        supported_features=5,
        translation_key="my_translation_key",
        unit_of_measurement=PERCENTAGE,
    )


async def test_override_restored_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that we allow overriding restored entities."""
    entity_registry.async_get_or_create(
        "test_domain", "test_domain", "1234", suggested_object_id="world"
    )

    hass.states.async_set("test_domain.world", "unavailable", {"restored": True})

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_setup({})

    await component.async_add_entities(
        [MockEntity(unique_id="1234", state="on", entity_id="test_domain.world")], True
    )

    state = hass.states.get("test_domain.world")
    assert state.state == "on"


async def test_platform_with_no_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test setting up a platform that does not support setup."""
    entity_platform = MockEntityPlatform(
        hass, domain="mock-integration", platform_name="mock-platform", platform=None
    )

    await entity_platform.async_setup(None)

    assert (
        "The mock-platform platform for the mock-integration integration does not support platform setup."
        in caplog.text
    )
    issue = issue_registry.async_get_issue(
        domain="homeassistant",
        issue_id="platform_integration_no_support_mock-integration_mock-platform",
    )
    assert issue
    assert issue.issue_domain == "mock-platform"
    assert issue.learn_more_url is None
    assert issue.translation_key == "no_platform_setup"
    assert issue.translation_placeholders == {
        "domain": "mock-integration",
        "platform": "mock-platform",
        "platform_key": "platform: mock-platform",
        "yaml_example": "```yaml\nmock-integration:\n  - platform: mock-platform\n```",
    }


async def test_platforms_sharing_services(hass: HomeAssistant) -> None:
    """Test platforms share services."""
    entity_platform1 = MockEntityPlatform(
        hass, domain="mock_integration", platform_name="mock_platform", platform=None
    )
    entity1 = MockEntity(entity_id="mock_integration.entity_1")
    await entity_platform1.async_add_entities([entity1])

    entity_platform2 = MockEntityPlatform(
        hass, domain="mock_integration", platform_name="mock_platform", platform=None
    )
    entity2 = MockEntity(entity_id="mock_integration.entity_2")
    await entity_platform2.async_add_entities([entity2])

    entity_platform3 = MockEntityPlatform(
        hass,
        domain="different_integration",
        platform_name="mock_platform",
        platform=None,
    )
    entity3 = MockEntity(entity_id="different_integration.entity_3")
    await entity_platform3.async_add_entities([entity3])

    entities = []

    @callback
    def handle_service(entity, data):
        entities.append(entity)

    entity_platform1.async_register_entity_service("hello", {}, handle_service)
    entity_platform2.async_register_entity_service(
        "hello", {}, Mock(side_effect=AssertionError("Should not be called"))
    )

    await hass.services.async_call(
        "mock_platform", "hello", {"entity_id": "all"}, blocking=True
    )

    assert len(entities) == 2
    assert entity1 in entities
    assert entity2 in entities


async def test_invalid_entity_id(hass: HomeAssistant) -> None:
    """Test specifying an invalid entity id."""
    platform = MockEntityPlatform(hass)
    entity = MockEntity(entity_id="invalid_entity_id")
    with pytest.raises(HomeAssistantError):
        await platform.async_add_entities([entity])
    assert entity.hass is None
    assert entity.platform is None


class MockBlockingEntity(MockEntity):
    """Class to mock an entity that will block adding entities."""

    async def async_added_to_hass(self):
        """Block for a long time."""
        await asyncio.sleep(1000)


async def test_setup_entry_with_entities_that_block_forever(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we cancel adding entities when we reach the timeout."""

    async def async_setup_entry(hass, config_entry, async_add_entities):
        """Mock setup entry method."""
        async_add_entities([MockBlockingEntity(name="test1", unique_id="unique")])
        return True

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry(entry_id="super-mock-id")
    mock_entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    with patch.object(entity_platform, "SLOW_ADD_ENTITY_MAX_WAIT", 0.01), patch.object(
        entity_platform, "SLOW_ADD_MIN_TIMEOUT", 0.01
    ):
        assert await mock_entity_platform.async_setup_entry(config_entry)
        await hass.async_block_till_done()
    full_name = f"{mock_entity_platform.domain}.{config_entry.domain}"
    assert full_name in hass.config.components
    assert len(hass.states.async_entity_ids()) == 0
    assert len(entity_registry.entities) == 1
    assert "Timed out adding entities" in caplog.text
    assert "test_domain.test1" in caplog.text
    assert "test_domain" in caplog.text
    assert "test" in caplog.text


async def test_two_platforms_add_same_entity(hass: HomeAssistant) -> None:
    """Test two platforms in the same domain adding an entity with the same name."""
    entity_platform1 = MockEntityPlatform(
        hass, domain="mock_integration", platform_name="mock_platform", platform=None
    )
    entity1 = SlowEntity(name="entity_1")

    entity_platform2 = MockEntityPlatform(
        hass, domain="mock_integration", platform_name="mock_platform", platform=None
    )
    entity2 = SlowEntity(name="entity_1")

    await asyncio.gather(
        entity_platform1.async_add_entities([entity1]),
        entity_platform2.async_add_entities([entity2]),
    )

    entities = []

    @callback
    def handle_service(entity, *_):
        entities.append(entity)

    entity_platform1.async_register_entity_service("hello", {}, handle_service)
    await hass.services.async_call(
        "mock_platform", "hello", {"entity_id": "all"}, blocking=True
    )

    assert len(entities) == 2
    assert {entity1.entity_id, entity2.entity_id} == {
        "mock_integration.entity_1",
        "mock_integration.entity_1_2",
    }
    assert entity1 in entities
    assert entity2 in entities


class SlowEntity(MockEntity):
    """An entity that will sleep during add."""

    async def async_added_to_hass(self):
        """Make sure control is returned to the event loop on add."""
        await asyncio.sleep(0.1)
        await super().async_added_to_hass()


@pytest.mark.parametrize(
    ("has_entity_name", "entity_name", "expected_entity_id"),
    (
        (False, "Entity Blu", "test_domain.entity_blu"),
        (False, None, "test_domain.test_qwer"),  # Set to <platform>_<unique_id>
        (True, "Entity Blu", "test_domain.device_bla_entity_blu"),
        (True, None, "test_domain.device_bla"),
    ),
)
async def test_entity_name_influences_entity_id(
    hass: HomeAssistant,
    has_entity_name: bool,
    entity_name: str | None,
    expected_entity_id: str,
) -> None:
    """Test entity_id is influenced by entity name."""
    registry = er.async_get(hass)

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
    config_entry.add_to_hass(hass)
    entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    assert await entity_platform.async_setup_entry(config_entry)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1
    assert registry.async_get(expected_entity_id) is not None


@pytest.mark.parametrize(
    ("language", "has_entity_name", "expected_entity_id"),
    (
        ("en", False, "test_domain.test_qwer"),  # Set to <platform>_<unique_id>
        ("en", True, "test_domain.device_bla_english_name"),
        ("sv", True, "test_domain.device_bla_swedish_name"),
        # Chinese uses english for entity_id
        ("cn", True, "test_domain.device_bla_english_name"),
    ),
)
async def test_translated_entity_name_influences_entity_id(
    hass: HomeAssistant,
    language: str,
    has_entity_name: bool,
    expected_entity_id: str,
) -> None:
    """Test entity_id is influenced by translated entity name."""

    class TranslatedEntity(Entity):
        _attr_unique_id = "qwer"
        _attr_device_info = {
            "identifiers": {("hue", "1234")},
            "connections": {(dr.CONNECTION_NETWORK_MAC, "abcd")},
            "name": "Device Bla",
        }

        _attr_translation_key = "test"

        def __init__(self, has_entity_name: bool) -> None:
            """Initialize."""
            self._attr_has_entity_name = has_entity_name

    registry = er.async_get(hass)

    translations = {
        "en": {"component.test.entity.test_domain.test.name": "English name"},
        "sv": {"component.test.entity.test_domain.test.name": "Swedish name"},
        "cn": {"component.test.entity.test_domain.test.name": "Chinese name"},
    }
    hass.config.language = language

    async def async_get_translations(
        hass: HomeAssistant,
        language: str,
        category: str,
        integrations: Iterable[str] | None = None,
        config_flow: bool | None = None,
    ) -> dict[str, Any]:
        """Return all backend translations."""
        return translations[language]

    async def async_setup_entry(hass, config_entry, async_add_entities):
        """Mock setup entry method."""
        async_add_entities([TranslatedEntity(has_entity_name)])
        return True

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry(entry_id="super-mock-id")
    config_entry.add_to_hass(hass)
    entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    with patch(
        "homeassistant.helpers.entity_platform.translation.async_get_translations",
        side_effect=async_get_translations,
    ):
        assert await entity_platform.async_setup_entry(config_entry)
        await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1
    assert registry.async_get(expected_entity_id) is not None


@pytest.mark.parametrize(
    ("language", "has_entity_name", "device_class", "expected_entity_id"),
    (
        ("en", False, None, "test_domain.test_qwer"),  # Set to <platform>_<unique_id>
        (
            "en",
            False,
            "test_class",
            "test_domain.test_qwer",
        ),  # Set to <platform>_<unique_id>
        ("en", True, "test_class", "test_domain.device_bla_english_cls"),
        ("sv", True, "test_class", "test_domain.device_bla_swedish_cls"),
        # Chinese uses english for entity_id
        ("cn", True, "test_class", "test_domain.device_bla_english_cls"),
    ),
)
async def test_translated_device_class_name_influences_entity_id(
    hass: HomeAssistant,
    language: str,
    has_entity_name: bool,
    device_class: str | None,
    expected_entity_id: str,
) -> None:
    """Test entity_id is influenced by translated entity name."""

    class TranslatedDeviceClassEntity(Entity):
        _attr_unique_id = "qwer"
        _attr_device_info = {
            "identifiers": {("hue", "1234")},
            "connections": {(dr.CONNECTION_NETWORK_MAC, "abcd")},
            "name": "Device Bla",
        }

        def __init__(self, device_class: str | None, has_entity_name: bool) -> None:
            """Initialize."""
            self._attr_device_class = device_class
            self._attr_has_entity_name = has_entity_name

        def _default_to_device_class_name(self) -> bool:
            """Return True if an unnamed entity should be named by its device class."""
            return self.device_class is not None

    registry = er.async_get(hass)

    translations = {
        "en": {"component.test_domain.entity_component.test_class.name": "English cls"},
        "sv": {"component.test_domain.entity_component.test_class.name": "Swedish cls"},
        "cn": {"component.test_domain.entity_component.test_class.name": "Chinese cls"},
    }
    hass.config.language = language

    async def async_get_translations(
        hass: HomeAssistant,
        language: str,
        category: str,
        integrations: Iterable[str] | None = None,
        config_flow: bool | None = None,
    ) -> dict[str, Any]:
        """Return all backend translations."""
        return translations[language]

    async def async_setup_entry(hass, config_entry, async_add_entities):
        """Mock setup entry method."""
        async_add_entities([TranslatedDeviceClassEntity(device_class, has_entity_name)])
        return True

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry(entry_id="super-mock-id")
    config_entry.add_to_hass(hass)
    entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    with patch(
        "homeassistant.helpers.entity_platform.translation.async_get_translations",
        side_effect=async_get_translations,
    ):
        assert await entity_platform.async_setup_entry(config_entry)
        await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1
    assert registry.async_get(expected_entity_id) is not None


@pytest.mark.parametrize(
    (
        "config_entry_title",
        "entity_device_name",
        "entity_device_default_name",
        "expected_device_name",
    ),
    [
        ("Mock Config Entry Title", None, None, "Mock Config Entry Title"),
        ("Mock Config Entry Title", "", None, "Mock Config Entry Title"),
        ("Mock Config Entry Title", None, "Hello", "Hello"),
        ("Mock Config Entry Title", "Mock Device Name", None, "Mock Device Name"),
    ],
)
async def test_device_name_defaulting_config_entry(
    hass: HomeAssistant,
    config_entry_title: str,
    entity_device_name: str,
    entity_device_default_name: str,
    expected_device_name: str,
) -> None:
    """Test setting the device name based on input info."""
    device_info = {
        "connections": {(dr.CONNECTION_NETWORK_MAC, "1234")},
    }

    if entity_device_default_name:
        device_info["default_name"] = entity_device_default_name
    else:
        device_info["name"] = entity_device_name

    class DeviceNameEntity(Entity):
        _attr_unique_id = "qwer"
        _attr_device_info = device_info

    async def async_setup_entry(hass, config_entry, async_add_entities):
        """Mock setup entry method."""
        async_add_entities([DeviceNameEntity()])
        return True

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry(title=config_entry_title, entry_id="super-mock-id")
    config_entry.add_to_hass(hass)
    entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    assert await entity_platform.async_setup_entry(config_entry)
    await hass.async_block_till_done()

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(connections={(dr.CONNECTION_NETWORK_MAC, "1234")})
    assert device is not None
    assert device.name == expected_device_name


@pytest.mark.parametrize(
    ("device_info", "number_of_entities"),
    [
        # No identifiers
        ({}, 1),  # Empty device info does not prevent the entity from being created
        ({"name": "bla"}, 0),
        ({"default_name": "bla"}, 0),
        # Match multiple types
        (
            {
                "identifiers": {("hue", "1234")},
                "name": "bla",
                "default_name": "yo",
            },
            0,
        ),
    ],
)
async def test_device_type_error_checking(
    hass: HomeAssistant,
    device_info: dict,
    number_of_entities: int,
) -> None:
    """Test catching invalid device info."""

    class DeviceNameEntity(Entity):
        _attr_unique_id = "qwer"
        _attr_device_info = device_info

    async def async_setup_entry(hass, config_entry, async_add_entities):
        """Mock setup entry method."""
        async_add_entities([DeviceNameEntity()])
        return True

    platform = MockPlatform(async_setup_entry=async_setup_entry)
    config_entry = MockConfigEntry(
        title="Mock Config Entry Title", entry_id="super-mock-id"
    )
    config_entry.add_to_hass(hass)
    entity_platform = MockEntityPlatform(
        hass, platform_name=config_entry.domain, platform=platform
    )

    assert await entity_platform.async_setup_entry(config_entry)

    dev_reg = dr.async_get(hass)
    assert len(dev_reg.devices) == 0
    ent_reg = er.async_get(hass)
    assert len(ent_reg.entities) == number_of_entities
    assert len(hass.states.async_all()) == number_of_entities
