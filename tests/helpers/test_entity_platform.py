"""Tests for the EntityPlatform helper."""
import asyncio
from datetime import timedelta
import logging

import pytest

from homeassistant.const import UNIT_PERCENTAGE
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import entity_platform, entity_registry
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_component import (
    DEFAULT_SCAN_INTERVAL,
    EntityComponent,
)
import homeassistant.util.dt as dt_util

from tests.async_mock import Mock, patch
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


async def test_polling_only_updates_entities_it_should_poll(hass):
    """Test the polling of only updated entities."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, timedelta(seconds=20))

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


async def test_polling_updates_entities_with_exception(hass):
    """Test the updated entities that not break with an exception."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, timedelta(seconds=20))

    update_ok = []
    update_err = []

    def update_mock():
        """Mock normal update."""
        update_ok.append(None)

    def update_mock_err():
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


async def test_update_state_adds_entities(hass):
    """Test if updating poll entities cause an entity to be added works."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    ent1 = MockEntity()
    ent2 = MockEntity(should_poll=True)

    await component.async_add_entities([ent2])
    assert len(hass.states.async_entity_ids()) == 1
    ent2.update = lambda *_: component.add_entities([ent1])

    async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 2


async def test_update_state_adds_entities_with_update_before_add_true(hass):
    """Test if call update before add to state machine."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    ent = MockEntity()
    ent.update = Mock(spec_set=True)

    await component.async_add_entities([ent], True)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1
    assert ent.update.called


async def test_update_state_adds_entities_with_update_before_add_false(hass):
    """Test if not call update before add to state machine."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    ent = MockEntity()
    ent.update = Mock(spec_set=True)

    await component.async_add_entities([ent], False)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1
    assert not ent.update.called


@patch("homeassistant.helpers.entity_platform.async_track_time_interval")
async def test_set_scan_interval_via_platform(mock_track, hass):
    """Test the setting of the scan interval via platform."""

    def platform_setup(hass, config, add_entities, discovery_info=None):
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


async def test_adding_entities_with_generator_and_thread_callback(hass):
    """Test generator in add_entities that calls thread method.

    We should make sure we resolve the generator to a list before passing
    it into an async context.
    """
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    def create_entity(number):
        """Create entity helper."""
        entity = MockEntity(unique_id=f"unique{number}")
        entity.entity_id = async_generate_entity_id(DOMAIN + ".{}", "Number", hass=hass)
        return entity

    await component.async_add_entities(create_entity(i) for i in range(2))


async def test_platform_warn_slow_setup(hass):
    """Warn we log when platform setup takes a long time."""
    platform = MockPlatform()

    mock_entity_platform(hass, "test_domain.platform", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    with patch.object(hass.loop, "call_later") as mock_call:
        await component.async_setup({DOMAIN: {"platform": "platform"}})
        assert mock_call.called

        # mock_calls[0] is the warning message for component setup
        # mock_calls[3] is the warning message for platform setup
        timeout, logger_method = mock_call.mock_calls[3][1][:2]

        assert timeout == entity_platform.SLOW_SETUP_WARNING
        assert logger_method == _LOGGER.warning

        assert mock_call().cancel.called


async def test_platform_error_slow_setup(hass, caplog):
    """Don't block startup more than SLOW_SETUP_MAX_WAIT."""
    with patch.object(entity_platform, "SLOW_SETUP_MAX_WAIT", 0):
        called = []

        async def setup_platform(*args):
            called.append(1)
            await asyncio.sleep(1)

        platform = MockPlatform(async_setup_platform=setup_platform)
        component = EntityComponent(_LOGGER, DOMAIN, hass)
        mock_entity_platform(hass, "test_domain.test_platform", platform)
        await component.async_setup({DOMAIN: {"platform": "test_platform"}})
        assert len(called) == 1
        assert "test_domain.test_platform" not in hass.config.components
        assert "test_platform is taking longer than 0 seconds" in caplog.text


async def test_updated_state_used_for_entity_id(hass):
    """Test that first update results used for entity ID generation."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    class MockEntityNameFetcher(MockEntity):
        """Mock entity that fetches a friendly name."""

        async def async_update(self):
            """Mock update that assigns a name."""
            self._values["name"] = "Living Room"

    await component.async_add_entities([MockEntityNameFetcher()], True)

    entity_ids = hass.states.async_entity_ids()
    assert len(entity_ids) == 1
    assert entity_ids[0] == "test_domain.living_room"


async def test_parallel_updates_async_platform(hass):
    """Test async platform does not have parallel_updates limit by default."""
    platform = MockPlatform()

    mock_entity_platform(hass, "test_domain.platform", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    component._platforms = {}

    await component.async_setup({DOMAIN: {"platform": "platform"}})

    handle = list(component._platforms.values())[-1]
    assert handle.parallel_updates is None

    class AsyncEntity(MockEntity):
        """Mock entity that has async_update."""

        async def async_update(self):
            pass

    entity = AsyncEntity()
    await handle.async_add_entities([entity])
    assert entity.parallel_updates is None


async def test_parallel_updates_async_platform_with_constant(hass):
    """Test async platform can set parallel_updates limit."""
    platform = MockPlatform()
    platform.PARALLEL_UPDATES = 2

    mock_entity_platform(hass, "test_domain.platform", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    component._platforms = {}

    await component.async_setup({DOMAIN: {"platform": "platform"}})

    handle = list(component._platforms.values())[-1]

    class AsyncEntity(MockEntity):
        """Mock entity that has async_update."""

        async def async_update(self):
            pass

    entity = AsyncEntity()
    await handle.async_add_entities([entity])
    assert entity.parallel_updates is not None
    assert entity.parallel_updates._value == 2


async def test_parallel_updates_sync_platform(hass):
    """Test sync platform parallel_updates default set to 1."""
    platform = MockPlatform()

    mock_entity_platform(hass, "test_domain.platform", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    component._platforms = {}

    await component.async_setup({DOMAIN: {"platform": "platform"}})

    handle = list(component._platforms.values())[-1]

    class SyncEntity(MockEntity):
        """Mock entity that has update."""

        async def update(self):
            pass

    entity = SyncEntity()
    await handle.async_add_entities([entity])
    assert entity.parallel_updates is not None
    assert entity.parallel_updates._value == 1


async def test_parallel_updates_sync_platform_with_constant(hass):
    """Test sync platform can set parallel_updates limit."""
    platform = MockPlatform()
    platform.PARALLEL_UPDATES = 2

    mock_entity_platform(hass, "test_domain.platform", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    component._platforms = {}

    await component.async_setup({DOMAIN: {"platform": "platform"}})

    handle = list(component._platforms.values())[-1]

    class SyncEntity(MockEntity):
        """Mock entity that has update."""

        async def update(self):
            pass

    entity = SyncEntity()
    await handle.async_add_entities([entity])
    assert entity.parallel_updates is not None
    assert entity.parallel_updates._value == 2


async def test_raise_error_on_update(hass):
    """Test the add entity if they raise an error on update."""
    updates = []
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entity1 = MockEntity(name="test_1")
    entity2 = MockEntity(name="test_2")

    def _raise():
        """Raise an exception."""
        raise AssertionError

    entity1.update = _raise
    entity2.update = lambda: updates.append(1)

    await component.async_add_entities([entity1, entity2], True)

    assert len(updates) == 1
    assert 1 in updates


async def test_async_remove_with_platform(hass):
    """Remove an entity from a platform."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entity1 = MockEntity(name="test_1")
    await component.async_add_entities([entity1])
    assert len(hass.states.async_entity_ids()) == 1
    await entity1.async_remove()
    assert len(hass.states.async_entity_ids()) == 0


async def test_not_adding_duplicate_entities_with_unique_id(hass):
    """Test for not adding duplicate entities."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    await component.async_add_entities(
        [MockEntity(name="test1", unique_id="not_very_unique")]
    )

    assert len(hass.states.async_entity_ids()) == 1

    await component.async_add_entities(
        [MockEntity(name="test2", unique_id="not_very_unique")]
    )

    assert len(hass.states.async_entity_ids()) == 1


async def test_using_prescribed_entity_id(hass):
    """Test for using predefined entity ID."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_add_entities(
        [MockEntity(name="bla", entity_id="hello.world")]
    )
    assert "hello.world" in hass.states.async_entity_ids()


async def test_using_prescribed_entity_id_with_unique_id(hass):
    """Test for amending predefined entity ID because currently exists."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    await component.async_add_entities([MockEntity(entity_id="test_domain.world")])
    await component.async_add_entities(
        [MockEntity(entity_id="test_domain.world", unique_id="bla")]
    )

    assert "test_domain.world_2" in hass.states.async_entity_ids()


async def test_using_prescribed_entity_id_which_is_registered(hass):
    """Test not allowing predefined entity ID that already registered."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    registry = mock_registry(hass)
    # Register test_domain.world
    registry.async_get_or_create(DOMAIN, "test", "1234", suggested_object_id="world")

    # This entity_id will be rewritten
    await component.async_add_entities([MockEntity(entity_id="test_domain.world")])

    assert "test_domain.world_2" in hass.states.async_entity_ids()


async def test_name_which_conflict_with_registered(hass):
    """Test not generating conflicting entity ID based on name."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    registry = mock_registry(hass)

    # Register test_domain.world
    registry.async_get_or_create(DOMAIN, "test", "1234", suggested_object_id="world")

    await component.async_add_entities([MockEntity(name="world")])

    assert "test_domain.world_2" in hass.states.async_entity_ids()


async def test_entity_with_name_and_entity_id_getting_registered(hass):
    """Ensure that entity ID is used for registration."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_add_entities(
        [MockEntity(unique_id="1234", name="bla", entity_id="test_domain.world")]
    )
    assert "test_domain.world" in hass.states.async_entity_ids()


async def test_overriding_name_from_registry(hass):
    """Test that we can override a name via the Entity Registry."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    mock_registry(
        hass,
        {
            "test_domain.world": entity_registry.RegistryEntry(
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


async def test_registry_respect_entity_namespace(hass):
    """Test that the registry respects entity namespace."""
    mock_registry(hass)
    platform = MockEntityPlatform(hass, entity_namespace="ns")
    entity = MockEntity(unique_id="1234", name="Device Name")
    await platform.async_add_entities([entity])
    assert entity.entity_id == "test_domain.ns_device_name"


async def test_registry_respect_entity_disabled(hass):
    """Test that the registry respects entity disabled."""
    mock_registry(
        hass,
        {
            "test_domain.world": entity_registry.RegistryEntry(
                entity_id="test_domain.world",
                unique_id="1234",
                # Using component.async_add_entities is equal to platform "domain"
                platform="test_platform",
                disabled_by=entity_registry.DISABLED_USER,
            )
        },
    )
    platform = MockEntityPlatform(hass)
    entity = MockEntity(unique_id="1234")
    await platform.async_add_entities([entity])
    assert entity.entity_id == "test_domain.world"
    assert hass.states.async_entity_ids() == []


async def test_entity_registry_updates_name(hass):
    """Test that updates on the entity registry update platform entities."""
    registry = mock_registry(
        hass,
        {
            "test_domain.world": entity_registry.RegistryEntry(
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


async def test_setup_entry(hass):
    """Test we can setup an entry."""
    registry = mock_registry(hass)

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
    assert len(registry.entities) == 1
    assert registry.entities["test_domain.test1"].config_entry_id == "super-mock-id"


async def test_setup_entry_platform_not_ready(hass, caplog):
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


async def test_reset_cancels_retry_setup(hass):
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


async def test_not_fails_with_adding_empty_entities_(hass):
    """Test for not fails on empty entities list."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    await component.async_add_entities([])

    assert len(hass.states.async_entity_ids()) == 0


async def test_entity_registry_updates_entity_id(hass):
    """Test that updates on the entity registry update platform entities."""
    registry = mock_registry(
        hass,
        {
            "test_domain.world": entity_registry.RegistryEntry(
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


async def test_entity_registry_updates_invalid_entity_id(hass):
    """Test that we can't update to an invalid entity id."""
    registry = mock_registry(
        hass,
        {
            "test_domain.world": entity_registry.RegistryEntry(
                entity_id="test_domain.world",
                unique_id="1234",
                # Using component.async_add_entities is equal to platform "domain"
                platform="test_platform",
                name="Some name",
            ),
            "test_domain.existing": entity_registry.RegistryEntry(
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


async def test_device_info_called(hass):
    """Test device info is forwarded correctly."""
    registry = await hass.helpers.device_registry.async_get_registry()
    via = registry.async_get_or_create(
        config_entry_id="123",
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
                        "connections": {("mac", "abcd")},
                        "manufacturer": "test-manuf",
                        "model": "test-model",
                        "name": "test-name",
                        "sw_version": "test-sw",
                        "via_device": ("hue", "via-id"),
                    },
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

    assert len(hass.states.async_entity_ids()) == 2

    device = registry.async_get_device({("hue", "1234")}, set())
    assert device is not None
    assert device.identifiers == {("hue", "1234")}
    assert device.connections == {("mac", "abcd")}
    assert device.manufacturer == "test-manuf"
    assert device.model == "test-model"
    assert device.name == "test-name"
    assert device.sw_version == "test-sw"
    assert device.via_device_id == via.id


async def test_device_info_not_overrides(hass):
    """Test device info is forwarded correctly."""
    registry = await hass.helpers.device_registry.async_get_registry()
    device = registry.async_get_or_create(
        config_entry_id="bla",
        connections={("mac", "abcd")},
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
                    unique_id="qwer", device_info={"connections": {("mac", "abcd")}}
                )
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

    device2 = registry.async_get_device(set(), {("mac", "abcd")})
    assert device2 is not None
    assert device.id == device2.id
    assert device2.manufacturer == "test-manufacturer"
    assert device2.model == "test-model"


async def test_entity_disabled_by_integration(hass):
    """Test entity disabled by integration."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, timedelta(seconds=20))

    entity_default = MockEntity(unique_id="default")
    entity_disabled = MockEntity(
        unique_id="disabled", entity_registry_enabled_default=False
    )

    await component.async_add_entities([entity_default, entity_disabled])

    registry = await hass.helpers.entity_registry.async_get_registry()

    entry_default = registry.async_get_or_create(DOMAIN, DOMAIN, "default")
    assert entry_default.disabled_by is None
    entry_disabled = registry.async_get_or_create(DOMAIN, DOMAIN, "disabled")
    assert entry_disabled.disabled_by == "integration"


async def test_entity_info_added_to_entity_registry(hass):
    """Test entity info is written to entity registry."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, timedelta(seconds=20))

    entity_default = MockEntity(
        unique_id="default",
        capability_attributes={"max": 100},
        supported_features=5,
        device_class="mock-device-class",
        unit_of_measurement=UNIT_PERCENTAGE,
    )

    await component.async_add_entities([entity_default])

    registry = await hass.helpers.entity_registry.async_get_registry()

    entry_default = registry.async_get_or_create(DOMAIN, DOMAIN, "default")
    print(entry_default)
    assert entry_default.capabilities == {"max": 100}
    assert entry_default.supported_features == 5
    assert entry_default.device_class == "mock-device-class"
    assert entry_default.unit_of_measurement == UNIT_PERCENTAGE


async def test_override_restored_entities(hass):
    """Test that we allow overriding restored entities."""
    registry = mock_registry(hass)
    registry.async_get_or_create(
        "test_domain", "test_domain", "1234", suggested_object_id="world"
    )

    hass.states.async_set("test_domain.world", "unavailable", {"restored": True})

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    await component.async_add_entities(
        [MockEntity(unique_id="1234", state="on", entity_id="test_domain.world")], True
    )

    state = hass.states.get("test_domain.world")
    assert state.state == "on"


async def test_platform_with_no_setup(hass, caplog):
    """Test setting up a platform that does not support setup."""
    entity_platform = MockEntityPlatform(
        hass, domain="mock-integration", platform_name="mock-platform", platform=None
    )

    await entity_platform.async_setup(None)

    assert (
        "The mock-platform platform for the mock-integration integration does not support platform setup."
        in caplog.text
    )


async def test_platforms_sharing_services(hass):
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
