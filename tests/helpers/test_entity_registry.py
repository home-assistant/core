"""Tests for the Entity Registry."""
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_START, STATE_UNAVAILABLE
from homeassistant.core import CoreState, callback, valid_entity_id
from homeassistant.exceptions import MaxLengthExceeded
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from tests.common import (
    MockConfigEntry,
    flush_store,
    mock_device_registry,
    mock_registry,
)

YAML__OPEN_PATH = "homeassistant.util.yaml.loader.open"


@pytest.fixture
def registry(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture
def update_events(hass):
    """Capture update events."""
    events = []

    @callback
    def async_capture(event):
        events.append(event.data)

    hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, async_capture)

    return events


async def test_get_or_create_returns_same_entry(hass, registry, update_events):
    """Make sure we do not duplicate entries."""
    entry = registry.async_get_or_create("light", "hue", "1234")
    entry2 = registry.async_get_or_create("light", "hue", "1234")

    await hass.async_block_till_done()

    assert len(registry.entities) == 1
    assert entry is entry2
    assert entry.entity_id == "light.hue_1234"
    assert len(update_events) == 1
    assert update_events[0]["action"] == "create"
    assert update_events[0]["entity_id"] == entry.entity_id


def test_get_or_create_suggested_object_id(registry):
    """Test that suggested_object_id works."""
    entry = registry.async_get_or_create(
        "light", "hue", "1234", suggested_object_id="beer"
    )

    assert entry.entity_id == "light.beer"


def test_get_or_create_updates_data(registry):
    """Test that we update data in get_or_create."""
    orig_config_entry = MockConfigEntry(domain="light")

    orig_entry = registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        area_id="mock-area-id",
        capabilities={"max": 100},
        config_entry=orig_config_entry,
        device_id="mock-dev-id",
        disabled_by=er.RegistryEntryDisabler.HASS,
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
        hidden_by=er.RegistryEntryHider.INTEGRATION,
        original_device_class="mock-device-class",
        original_icon="initial-original_icon",
        original_name="initial-original_name",
        supported_features=5,
        unit_of_measurement="initial-unit_of_measurement",
    )

    assert orig_entry == er.RegistryEntry(
        "light.hue_5678",
        "5678",
        "hue",
        area_id="mock-area-id",
        capabilities={"max": 100},
        config_entry_id=orig_config_entry.entry_id,
        device_class=None,
        device_id="mock-dev-id",
        disabled_by=er.RegistryEntryDisabler.HASS,
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
        hidden_by=er.RegistryEntryHider.INTEGRATION,
        icon=None,
        id=orig_entry.id,
        name=None,
        original_device_class="mock-device-class",
        original_icon="initial-original_icon",
        original_name="initial-original_name",
        supported_features=5,
        unit_of_measurement="initial-unit_of_measurement",
    )

    new_config_entry = MockConfigEntry(domain="light")

    new_entry = registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        area_id="new-mock-area-id",
        capabilities={"new-max": 100},
        config_entry=new_config_entry,
        device_id="new-mock-dev-id",
        disabled_by=er.RegistryEntryDisabler.USER,
        entity_category=EntityCategory.DIAGNOSTIC,
        has_entity_name=False,
        hidden_by=er.RegistryEntryHider.USER,
        original_device_class="new-mock-device-class",
        original_icon="updated-original_icon",
        original_name="updated-original_name",
        supported_features=10,
        unit_of_measurement="updated-unit_of_measurement",
    )

    assert new_entry == er.RegistryEntry(
        "light.hue_5678",
        "5678",
        "hue",
        area_id="new-mock-area-id",
        capabilities={"new-max": 100},
        config_entry_id=new_config_entry.entry_id,
        device_class=None,
        device_id="new-mock-dev-id",
        disabled_by=er.RegistryEntryDisabler.HASS,  # Should not be updated
        entity_category=EntityCategory.DIAGNOSTIC,
        has_entity_name=False,
        hidden_by=er.RegistryEntryHider.INTEGRATION,  # Should not be updated
        icon=None,
        id=orig_entry.id,
        name=None,
        original_device_class="new-mock-device-class",
        original_icon="updated-original_icon",
        original_name="updated-original_name",
        supported_features=10,
        unit_of_measurement="updated-unit_of_measurement",
    )

    new_entry = registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        area_id=None,
        capabilities=None,
        config_entry=None,
        device_id=None,
        disabled_by=None,
        entity_category=None,
        has_entity_name=None,
        hidden_by=None,
        original_device_class=None,
        original_icon=None,
        original_name=None,
        supported_features=None,
        unit_of_measurement=None,
    )

    assert new_entry == er.RegistryEntry(
        "light.hue_5678",
        "5678",
        "hue",
        area_id=None,
        capabilities=None,
        config_entry_id=None,
        device_class=None,
        device_id=None,
        disabled_by=er.RegistryEntryDisabler.HASS,  # Should not be updated
        entity_category=None,
        has_entity_name=None,
        hidden_by=er.RegistryEntryHider.INTEGRATION,  # Should not be updated
        icon=None,
        id=orig_entry.id,
        name=None,
        original_device_class=None,
        original_icon=None,
        original_name=None,
        supported_features=0,  # supported_features is stored as an int
        unit_of_measurement=None,
    )


def test_get_or_create_suggested_object_id_conflict_register(registry):
    """Test that we don't generate an entity id that is already registered."""
    entry = registry.async_get_or_create(
        "light", "hue", "1234", suggested_object_id="beer"
    )
    entry2 = registry.async_get_or_create(
        "light", "hue", "5678", suggested_object_id="beer"
    )

    assert entry.entity_id == "light.beer"
    assert entry2.entity_id == "light.beer_2"


def test_get_or_create_suggested_object_id_conflict_existing(hass, registry):
    """Test that we don't generate an entity id that currently exists."""
    hass.states.async_set("light.hue_1234", "on")
    entry = registry.async_get_or_create("light", "hue", "1234")
    assert entry.entity_id == "light.hue_1234_2"


def test_create_triggers_save(hass, registry):
    """Test that registering entry triggers a save."""
    with patch.object(registry, "async_schedule_save") as mock_schedule_save:
        registry.async_get_or_create("light", "hue", "1234")

    assert len(mock_schedule_save.mock_calls) == 1


async def test_loading_saving_data(hass, registry):
    """Test that we load/save data correctly."""
    mock_config = MockConfigEntry(domain="light")

    orig_entry1 = registry.async_get_or_create("light", "hue", "1234")
    orig_entry2 = registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        area_id="mock-area-id",
        capabilities={"max": 100},
        config_entry=mock_config,
        device_id="mock-dev-id",
        disabled_by=er.RegistryEntryDisabler.HASS,
        entity_category=EntityCategory.CONFIG,
        hidden_by=er.RegistryEntryHider.INTEGRATION,
        has_entity_name=True,
        original_device_class="mock-device-class",
        original_icon="hass:original-icon",
        original_name="Original Name",
        supported_features=5,
        unit_of_measurement="initial-unit_of_measurement",
    )
    registry.async_update_entity(
        orig_entry2.entity_id,
        device_class="user-class",
        name="User Name",
        icon="hass:user-icon",
    )
    registry.async_update_entity_options(
        orig_entry2.entity_id, "light", {"minimum_brightness": 20}
    )
    orig_entry2 = registry.async_get(orig_entry2.entity_id)

    assert len(registry.entities) == 2

    # Now load written data in new registry
    registry2 = er.EntityRegistry(hass)
    await flush_store(registry._store)
    await registry2.async_load()

    # Ensure same order
    assert list(registry.entities) == list(registry2.entities)
    new_entry1 = registry.async_get_or_create("light", "hue", "1234")
    new_entry2 = registry.async_get_or_create("light", "hue", "5678")

    assert orig_entry1 == new_entry1
    assert orig_entry2 == new_entry2

    assert new_entry2.area_id == "mock-area-id"
    assert new_entry2.capabilities == {"max": 100}
    assert new_entry2.config_entry_id == mock_config.entry_id
    assert new_entry2.device_class == "user-class"
    assert new_entry2.device_id == "mock-dev-id"
    assert new_entry2.disabled_by is er.RegistryEntryDisabler.HASS
    assert new_entry2.entity_category == "config"
    assert new_entry2.icon == "hass:user-icon"
    assert new_entry2.hidden_by == er.RegistryEntryHider.INTEGRATION
    assert new_entry2.has_entity_name is True
    assert new_entry2.name == "User Name"
    assert new_entry2.options == {"light": {"minimum_brightness": 20}}
    assert new_entry2.original_device_class == "mock-device-class"
    assert new_entry2.original_icon == "hass:original-icon"
    assert new_entry2.original_name == "Original Name"
    assert new_entry2.supported_features == 5
    assert new_entry2.unit_of_measurement == "initial-unit_of_measurement"


def test_generate_entity_considers_registered_entities(registry):
    """Test that we don't create entity id that are already registered."""
    entry = registry.async_get_or_create("light", "hue", "1234")
    assert entry.entity_id == "light.hue_1234"
    assert registry.async_generate_entity_id("light", "hue_1234") == "light.hue_1234_2"


def test_generate_entity_considers_existing_entities(hass, registry):
    """Test that we don't create entity id that currently exists."""
    hass.states.async_set("light.kitchen", "on")
    assert registry.async_generate_entity_id("light", "kitchen") == "light.kitchen_2"


def test_is_registered(registry):
    """Test that is_registered works."""
    entry = registry.async_get_or_create("light", "hue", "1234")
    assert registry.async_is_registered(entry.entity_id)
    assert not registry.async_is_registered("light.non_existing")


@pytest.mark.parametrize("load_registries", [False])
async def test_filter_on_load(hass, hass_storage):
    """Test we transform some data when loading from storage."""
    hass_storage[er.STORAGE_KEY] = {
        "version": er.STORAGE_VERSION_MAJOR,
        "minor_version": 1,
        "data": {
            "entities": [
                {
                    "entity_id": "test.named",
                    "platform": "super_platform",
                    "unique_id": "with-name",
                    "name": "registry override",
                },
                # This entity's name should be None
                {
                    "entity_id": "test.no_name",
                    "platform": "super_platform",
                    "unique_id": "without-name",
                },
                {
                    "entity_id": "test.disabled_user",
                    "platform": "super_platform",
                    "unique_id": "disabled-user",
                    "disabled_by": "user",  # We store the string representation
                },
                {
                    "entity_id": "test.disabled_hass",
                    "platform": "super_platform",
                    "unique_id": "disabled-hass",
                    "disabled_by": "hass",  # We store the string representation
                },
                # This entry should not be loaded because the entity_id is invalid
                {
                    "entity_id": "test.invalid__entity",
                    "platform": "super_platform",
                    "unique_id": "invalid-hass",
                    "disabled_by": "hass",  # We store the string representation
                },
                # This entry should have the entity_category reset to None
                {
                    "entity_id": "test.system_entity",
                    "platform": "super_platform",
                    "unique_id": "system-entity",
                    "entity_category": "system",
                },
            ]
        },
    }

    await er.async_load(hass)
    registry = er.async_get(hass)

    assert len(registry.entities) == 5
    assert set(registry.entities.keys()) == {
        "test.disabled_hass",
        "test.disabled_user",
        "test.named",
        "test.no_name",
        "test.system_entity",
    }

    entry_with_name = registry.async_get_or_create(
        "test", "super_platform", "with-name"
    )
    entry_without_name = registry.async_get_or_create(
        "test", "super_platform", "without-name"
    )
    assert entry_with_name.name == "registry override"
    assert entry_without_name.name is None
    assert not entry_with_name.disabled

    entry_disabled_hass = registry.async_get_or_create(
        "test", "super_platform", "disabled-hass"
    )
    entry_disabled_user = registry.async_get_or_create(
        "test", "super_platform", "disabled-user"
    )
    assert entry_disabled_hass.disabled
    assert entry_disabled_hass.disabled_by is er.RegistryEntryDisabler.HASS
    assert entry_disabled_user.disabled
    assert entry_disabled_user.disabled_by is er.RegistryEntryDisabler.USER

    entry_system_category = registry.async_get_or_create(
        "test", "system_entity", "system-entity"
    )
    assert entry_system_category.entity_category is None


def test_async_get_entity_id(registry):
    """Test that entity_id is returned."""
    entry = registry.async_get_or_create("light", "hue", "1234")
    assert entry.entity_id == "light.hue_1234"
    assert registry.async_get_entity_id("light", "hue", "1234") == "light.hue_1234"
    assert registry.async_get_entity_id("light", "hue", "123") is None


async def test_updating_config_entry_id(hass, registry, update_events):
    """Test that we update config entry id in registry."""
    mock_config_1 = MockConfigEntry(domain="light", entry_id="mock-id-1")
    entry = registry.async_get_or_create(
        "light", "hue", "5678", config_entry=mock_config_1
    )

    mock_config_2 = MockConfigEntry(domain="light", entry_id="mock-id-2")
    entry2 = registry.async_get_or_create(
        "light", "hue", "5678", config_entry=mock_config_2
    )
    assert entry.entity_id == entry2.entity_id
    assert entry2.config_entry_id == "mock-id-2"

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0]["action"] == "create"
    assert update_events[0]["entity_id"] == entry.entity_id
    assert update_events[1]["action"] == "update"
    assert update_events[1]["entity_id"] == entry.entity_id
    assert update_events[1]["changes"] == {"config_entry_id": "mock-id-1"}


async def test_removing_config_entry_id(hass, registry, update_events):
    """Test that we update config entry id in registry."""
    mock_config = MockConfigEntry(domain="light", entry_id="mock-id-1")

    entry = registry.async_get_or_create(
        "light", "hue", "5678", config_entry=mock_config
    )
    assert entry.config_entry_id == "mock-id-1"
    registry.async_clear_config_entry("mock-id-1")

    assert not registry.entities

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0]["action"] == "create"
    assert update_events[0]["entity_id"] == entry.entity_id
    assert update_events[1]["action"] == "remove"
    assert update_events[1]["entity_id"] == entry.entity_id


async def test_removing_area_id(registry):
    """Make sure we can clear area id."""
    entry = registry.async_get_or_create("light", "hue", "5678")

    entry_w_area = registry.async_update_entity(entry.entity_id, area_id="12345A")

    registry.async_clear_area_id("12345A")
    entry_wo_area = registry.async_get(entry.entity_id)

    assert not entry_wo_area.area_id
    assert entry_w_area != entry_wo_area


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_yaml_to_json(hass):
    """Test migration from old (yaml) data to new."""
    mock_config = MockConfigEntry(domain="test-platform", entry_id="test-config-id")

    old_conf = {
        "light.kitchen": {
            "config_entry_id": "test-config-id",
            "unique_id": "test-unique",
            "platform": "test-platform",
            "name": "Test Name",
            "disabled_by": er.RegistryEntryDisabler.HASS,
        }
    }
    with patch("os.path.isfile", return_value=True), patch("os.remove"), patch(
        "homeassistant.helpers.entity_registry.load_yaml", return_value=old_conf
    ):
        await er.async_load(hass)
        registry = er.async_get(hass)

    assert registry.async_is_registered("light.kitchen")
    entry = registry.async_get_or_create(
        domain="light",
        platform="test-platform",
        unique_id="test-unique",
        config_entry=mock_config,
    )
    assert entry.name == "Test Name"
    assert entry.disabled_by is er.RegistryEntryDisabler.HASS
    assert entry.config_entry_id == "test-config-id"


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_1_1(hass, hass_storage):
    """Test migration from version 1.1."""
    hass_storage[er.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "data": {
            "entities": [
                {
                    "device_class": "best_class",
                    "entity_id": "test.entity",
                    "platform": "super_platform",
                    "unique_id": "very_unique",
                },
            ]
        },
    }

    await er.async_load(hass)
    registry = er.async_get(hass)

    entry = registry.async_get_or_create("test", "super_platform", "very_unique")

    assert entry.device_class is None
    assert entry.original_device_class == "best_class"


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_1_7(hass, hass_storage):
    """Test migration from version 1.7.

    This tests cleanup after frontend bug which incorrectly updated device_class
    """
    entity_dict = {
        "area_id": None,
        "capabilities": {},
        "config_entry_id": None,
        "device_id": None,
        "disabled_by": None,
        "entity_category": None,
        "has_entity_name": False,
        "hidden_by": None,
        "icon": None,
        "id": "12345",
        "name": None,
        "options": None,
        "original_icon": None,
        "original_name": None,
        "platform": "super_platform",
        "supported_features": 0,
        "unique_id": "very_unique",
        "unit_of_measurement": None,
    }

    hass_storage[er.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 7,
        "data": {
            "entities": [
                {
                    **entity_dict,
                    "device_class": "original_class_by_integration",
                    "entity_id": "test.entity",
                    "original_device_class": "new_class_by_integration",
                },
                {
                    **entity_dict,
                    "device_class": "class_by_user",
                    "entity_id": "binary_sensor.entity",
                    "original_device_class": "class_by_integration",
                },
                {
                    **entity_dict,
                    "device_class": "class_by_user",
                    "entity_id": "cover.entity",
                    "original_device_class": "class_by_integration",
                },
            ]
        },
    }

    await er.async_load(hass)
    registry = er.async_get(hass)

    entry = registry.async_get_or_create("test", "super_platform", "very_unique")
    assert entry.device_class is None
    assert entry.original_device_class == "new_class_by_integration"

    entry = registry.async_get_or_create(
        "binary_sensor", "super_platform", "very_unique"
    )
    assert entry.device_class == "class_by_user"
    assert entry.original_device_class == "class_by_integration"

    entry = registry.async_get_or_create("cover", "super_platform", "very_unique")
    assert entry.device_class == "class_by_user"
    assert entry.original_device_class == "class_by_integration"


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_invalid_entity_id(hass, hass_storage):
    """Test we skip entities with invalid entity IDs."""
    hass_storage[er.STORAGE_KEY] = {
        "version": er.STORAGE_VERSION_MAJOR,
        "minor_version": er.STORAGE_VERSION_MINOR,
        "data": {
            "entities": [
                {
                    "entity_id": "test.invalid__middle",
                    "platform": "super_platform",
                    "unique_id": "id-invalid-middle",
                    "name": "registry override 1",
                },
                {
                    "entity_id": "test.invalid_end_",
                    "platform": "super_platform",
                    "unique_id": "id-invalid-end",
                    "name": "registry override 2",
                },
                {
                    "entity_id": "test._invalid_start",
                    "platform": "super_platform",
                    "unique_id": "id-invalid-start",
                    "name": "registry override 3",
                },
            ]
        },
    }

    await er.async_load(hass)
    registry = er.async_get(hass)
    assert len(registry.entities) == 0

    entity_invalid_middle = registry.async_get_or_create(
        "test", "super_platform", "id-invalid-middle"
    )

    assert valid_entity_id(entity_invalid_middle.entity_id)
    # Check name to make sure we created a new entity
    assert entity_invalid_middle.name is None

    entity_invalid_end = registry.async_get_or_create(
        "test", "super_platform", "id-invalid-end"
    )

    assert valid_entity_id(entity_invalid_end.entity_id)
    assert entity_invalid_end.name is None

    entity_invalid_start = registry.async_get_or_create(
        "test", "super_platform", "id-invalid-start"
    )

    assert valid_entity_id(entity_invalid_start.entity_id)
    assert entity_invalid_start.name is None


async def test_update_entity_unique_id(registry):
    """Test entity's unique_id is updated."""
    mock_config = MockConfigEntry(domain="light", entry_id="mock-id-1")

    entry = registry.async_get_or_create(
        "light", "hue", "5678", config_entry=mock_config
    )
    assert registry.async_get_entity_id("light", "hue", "5678") == entry.entity_id

    new_unique_id = "1234"
    with patch.object(registry, "async_schedule_save") as mock_schedule_save:
        updated_entry = registry.async_update_entity(
            entry.entity_id, new_unique_id=new_unique_id
        )
    assert updated_entry != entry
    assert updated_entry.unique_id == new_unique_id
    assert mock_schedule_save.call_count == 1

    assert registry.async_get_entity_id("light", "hue", "5678") is None
    assert registry.async_get_entity_id("light", "hue", "1234") == entry.entity_id


async def test_update_entity_unique_id_conflict(registry):
    """Test migration raises when unique_id already in use."""
    mock_config = MockConfigEntry(domain="light", entry_id="mock-id-1")
    entry = registry.async_get_or_create(
        "light", "hue", "5678", config_entry=mock_config
    )
    entry2 = registry.async_get_or_create(
        "light", "hue", "1234", config_entry=mock_config
    )
    with patch.object(
        registry, "async_schedule_save"
    ) as mock_schedule_save, pytest.raises(ValueError):
        registry.async_update_entity(entry.entity_id, new_unique_id=entry2.unique_id)
    assert mock_schedule_save.call_count == 0
    assert registry.async_get_entity_id("light", "hue", "5678") == entry.entity_id
    assert registry.async_get_entity_id("light", "hue", "1234") == entry2.entity_id


async def test_update_entity(registry):
    """Test updating entity."""
    mock_config = MockConfigEntry(domain="light", entry_id="mock-id-1")
    entry = registry.async_get_or_create(
        "light", "hue", "5678", config_entry=mock_config
    )

    for attr_name, new_value in (
        ("name", "new name"),
        ("icon", "new icon"),
        ("disabled_by", er.RegistryEntryDisabler.USER),
    ):
        changes = {attr_name: new_value}
        updated_entry = registry.async_update_entity(entry.entity_id, **changes)

        assert updated_entry != entry
        assert getattr(updated_entry, attr_name) == new_value
        assert getattr(updated_entry, attr_name) != getattr(entry, attr_name)

        assert (
            registry.async_get_entity_id("light", "hue", "5678")
            == updated_entry.entity_id
        )
        entry = updated_entry


async def test_update_entity_options(registry):
    """Test updating entity."""
    mock_config = MockConfigEntry(domain="light", entry_id="mock-id-1")
    entry = registry.async_get_or_create(
        "light", "hue", "5678", config_entry=mock_config
    )

    registry.async_update_entity_options(
        entry.entity_id, "light", {"minimum_brightness": 20}
    )
    new_entry_1 = registry.async_get(entry.entity_id)

    assert entry.options == {}
    assert new_entry_1.options == {"light": {"minimum_brightness": 20}}

    registry.async_update_entity_options(
        entry.entity_id, "light", {"minimum_brightness": 30}
    )
    new_entry_2 = registry.async_get(entry.entity_id)

    assert entry.options == {}
    assert new_entry_1.options == {"light": {"minimum_brightness": 20}}
    assert new_entry_2.options == {"light": {"minimum_brightness": 30}}


async def test_disabled_by(registry):
    """Test that we can disable an entry when we create it."""
    entry = registry.async_get_or_create(
        "light", "hue", "5678", disabled_by=er.RegistryEntryDisabler.HASS
    )
    assert entry.disabled_by is er.RegistryEntryDisabler.HASS

    entry = registry.async_get_or_create(
        "light", "hue", "5678", disabled_by=er.RegistryEntryDisabler.INTEGRATION
    )
    assert entry.disabled_by is er.RegistryEntryDisabler.HASS

    entry2 = registry.async_get_or_create("light", "hue", "1234")
    assert entry2.disabled_by is None


async def test_disabled_by_config_entry_pref(registry):
    """Test config entry preference setting disabled_by."""
    mock_config = MockConfigEntry(
        domain="light",
        entry_id="mock-id-1",
        pref_disable_new_entities=True,
    )
    entry = registry.async_get_or_create(
        "light", "hue", "AAAA", config_entry=mock_config
    )
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    entry2 = registry.async_get_or_create(
        "light",
        "hue",
        "BBBB",
        config_entry=mock_config,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    assert entry2.disabled_by is er.RegistryEntryDisabler.USER


async def test_restore_states(hass):
    """Test restoring states."""
    hass.state = CoreState.not_running

    registry = er.async_get(hass)

    registry.async_get_or_create(
        "light",
        "hue",
        "1234",
        suggested_object_id="simple",
    )
    # Should not be created
    registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        suggested_object_id="disabled",
        disabled_by=er.RegistryEntryDisabler.HASS,
    )
    registry.async_get_or_create(
        "light",
        "hue",
        "9012",
        suggested_object_id="all_info_set",
        capabilities={"max": 100},
        supported_features=5,
        original_device_class="mock-device-class",
        original_name="Mock Original Name",
        original_icon="hass:original-icon",
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START, {})
    await hass.async_block_till_done()

    simple = hass.states.get("light.simple")
    assert simple is not None
    assert simple.state == STATE_UNAVAILABLE
    assert simple.attributes == {"restored": True, "supported_features": 0}

    disabled = hass.states.get("light.disabled")
    assert disabled is None

    all_info_set = hass.states.get("light.all_info_set")
    assert all_info_set is not None
    assert all_info_set.state == STATE_UNAVAILABLE
    assert all_info_set.attributes == {
        "max": 100,
        "supported_features": 5,
        "device_class": "mock-device-class",
        "restored": True,
        "friendly_name": "Mock Original Name",
        "icon": "hass:original-icon",
    }

    registry.async_remove("light.disabled")
    registry.async_remove("light.simple")
    registry.async_remove("light.all_info_set")

    await hass.async_block_till_done()

    assert hass.states.get("light.simple") is None
    assert hass.states.get("light.disabled") is None
    assert hass.states.get("light.all_info_set") is None


async def test_async_get_device_class_lookup(hass):
    """Test registry device class lookup."""
    hass.state = CoreState.not_running

    ent_reg = er.async_get(hass)

    ent_reg.async_get_or_create(
        "binary_sensor",
        "light",
        "battery_charging",
        device_id="light_device_entry_id",
        original_device_class="battery_charging",
    )
    ent_reg.async_get_or_create(
        "sensor",
        "light",
        "battery",
        device_id="light_device_entry_id",
        original_device_class="battery",
    )
    ent_reg.async_get_or_create(
        "light", "light", "demo", device_id="light_device_entry_id"
    )
    ent_reg.async_get_or_create(
        "binary_sensor",
        "vacuum",
        "battery_charging",
        device_id="vacuum_device_entry_id",
        original_device_class="battery_charging",
    )
    ent_reg.async_get_or_create(
        "sensor",
        "vacuum",
        "battery",
        device_id="vacuum_device_entry_id",
        original_device_class="battery",
    )
    ent_reg.async_get_or_create(
        "vacuum", "vacuum", "demo", device_id="vacuum_device_entry_id"
    )
    ent_reg.async_get_or_create(
        "binary_sensor",
        "remote",
        "battery_charging",
        device_id="remote_device_entry_id",
        original_device_class="battery_charging",
    )
    ent_reg.async_get_or_create(
        "remote", "remote", "demo", device_id="remote_device_entry_id"
    )

    device_lookup = ent_reg.async_get_device_class_lookup(
        {("binary_sensor", "battery_charging"), ("sensor", "battery")}
    )

    assert device_lookup == {
        "remote_device_entry_id": {
            (
                "binary_sensor",
                "battery_charging",
            ): "binary_sensor.remote_battery_charging"
        },
        "light_device_entry_id": {
            (
                "binary_sensor",
                "battery_charging",
            ): "binary_sensor.light_battery_charging",
            ("sensor", "battery"): "sensor.light_battery",
        },
        "vacuum_device_entry_id": {
            (
                "binary_sensor",
                "battery_charging",
            ): "binary_sensor.vacuum_battery_charging",
            ("sensor", "battery"): "sensor.vacuum_battery",
        },
    }


async def test_remove_device_removes_entities(hass, registry):
    """Test that we remove entities tied to a device."""
    device_registry = mock_device_registry(hass)
    config_entry = MockConfigEntry(domain="light")

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    entry = registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
        device_id=device_entry.id,
    )

    assert registry.async_is_registered(entry.entity_id)

    device_registry.async_remove_device(device_entry.id)
    await hass.async_block_till_done()

    assert not registry.async_is_registered(entry.entity_id)


async def test_remove_config_entry_from_device_removes_entities(hass, registry):
    """Test that we remove entities tied to a device when config entry is removed."""
    device_registry = mock_device_registry(hass)
    config_entry_1 = MockConfigEntry(domain="hue")
    config_entry_2 = MockConfigEntry(domain="device_tracker")

    # Create device with two config entries
    device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert device_entry.config_entries == {
        config_entry_1.entry_id,
        config_entry_2.entry_id,
    }

    # Create one entity for each config entry
    entry_1 = registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry_1,
        device_id=device_entry.id,
    )

    entry_2 = registry.async_get_or_create(
        "sensor",
        "device_tracker",
        "6789",
        config_entry=config_entry_2,
        device_id=device_entry.id,
    )

    assert registry.async_is_registered(entry_1.entity_id)
    assert registry.async_is_registered(entry_2.entity_id)

    # Remove the first config entry from the device, the entity associated with it
    # should be removed
    device_registry.async_update_device(
        device_entry.id, remove_config_entry_id=config_entry_1.entry_id
    )
    await hass.async_block_till_done()

    assert device_registry.async_get(device_entry.id)
    assert not registry.async_is_registered(entry_1.entity_id)
    assert registry.async_is_registered(entry_2.entity_id)

    # Remove the second config entry from the device, the entity associated with it
    # (and the device itself) should be removed
    device_registry.async_update_device(
        device_entry.id, remove_config_entry_id=config_entry_2.entry_id
    )
    await hass.async_block_till_done()

    assert not device_registry.async_get(device_entry.id)
    assert not registry.async_is_registered(entry_1.entity_id)
    assert not registry.async_is_registered(entry_2.entity_id)


async def test_remove_config_entry_from_device_removes_entities_2(hass, registry):
    """Test that we don't remove entities with no config entry when device is modified."""
    device_registry = mock_device_registry(hass)
    config_entry_1 = MockConfigEntry(domain="hue")
    config_entry_2 = MockConfigEntry(domain="device_tracker")

    # Create device with two config entries
    device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert device_entry.config_entries == {
        config_entry_1.entry_id,
        config_entry_2.entry_id,
    }

    # Create one entity for each config entry
    entry_1 = registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        device_id=device_entry.id,
    )

    assert registry.async_is_registered(entry_1.entity_id)

    # Remove the first config entry from the device
    device_registry.async_update_device(
        device_entry.id, remove_config_entry_id=config_entry_1.entry_id
    )
    await hass.async_block_till_done()

    assert device_registry.async_get(device_entry.id)
    assert registry.async_is_registered(entry_1.entity_id)


async def test_update_device_race(hass, registry):
    """Test race when a device is created, updated and removed."""
    device_registry = mock_device_registry(hass)
    config_entry = MockConfigEntry(domain="light")

    # Create device
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    # Update it
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("bridgeid", "0123")},
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    # Add entity to the device
    entry = registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
        device_id=device_entry.id,
    )

    assert registry.async_is_registered(entry.entity_id)

    device_registry.async_remove_device(device_entry.id)
    await hass.async_block_till_done()

    assert not registry.async_is_registered(entry.entity_id)


async def test_disable_device_disables_entities(hass, registry):
    """Test that we disable entities tied to a device."""
    device_registry = mock_device_registry(hass)
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    entry1 = registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
        device_id=device_entry.id,
    )
    entry2 = registry.async_get_or_create(
        "light",
        "hue",
        "ABCD",
        config_entry=config_entry,
        device_id=device_entry.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    entry3 = registry.async_get_or_create(
        "light",
        "hue",
        "EFGH",
        config_entry=config_entry,
        device_id=device_entry.id,
        disabled_by=er.RegistryEntryDisabler.CONFIG_ENTRY,
    )

    assert not entry1.disabled
    assert entry2.disabled
    assert entry3.disabled

    device_registry.async_update_device(
        device_entry.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    await hass.async_block_till_done()

    entry1 = registry.async_get(entry1.entity_id)
    assert entry1.disabled
    assert entry1.disabled_by is er.RegistryEntryDisabler.DEVICE
    entry2 = registry.async_get(entry2.entity_id)
    assert entry2.disabled
    assert entry2.disabled_by is er.RegistryEntryDisabler.USER
    entry3 = registry.async_get(entry3.entity_id)
    assert entry3.disabled
    assert entry3.disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY

    device_registry.async_update_device(device_entry.id, disabled_by=None)
    await hass.async_block_till_done()

    entry1 = registry.async_get(entry1.entity_id)
    assert not entry1.disabled
    entry2 = registry.async_get(entry2.entity_id)
    assert entry2.disabled
    assert entry2.disabled_by is er.RegistryEntryDisabler.USER
    entry3 = registry.async_get(entry3.entity_id)
    assert entry3.disabled
    assert entry3.disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY


async def test_disable_config_entry_disables_entities(hass, registry):
    """Test that we disable entities tied to a config entry."""
    device_registry = mock_device_registry(hass)
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    entry1 = registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
        device_id=device_entry.id,
    )
    entry2 = registry.async_get_or_create(
        "light",
        "hue",
        "ABCD",
        config_entry=config_entry,
        device_id=device_entry.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    entry3 = registry.async_get_or_create(
        "light",
        "hue",
        "EFGH",
        config_entry=config_entry,
        device_id=device_entry.id,
        disabled_by=er.RegistryEntryDisabler.DEVICE,
    )

    assert not entry1.disabled
    assert entry2.disabled
    assert entry3.disabled

    await hass.config_entries.async_set_disabled_by(
        config_entry.entry_id, config_entries.ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()

    entry1 = registry.async_get(entry1.entity_id)
    assert entry1.disabled
    assert entry1.disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY
    entry2 = registry.async_get(entry2.entity_id)
    assert entry2.disabled
    assert entry2.disabled_by is er.RegistryEntryDisabler.USER
    entry3 = registry.async_get(entry3.entity_id)
    assert entry3.disabled
    assert entry3.disabled_by is er.RegistryEntryDisabler.DEVICE

    await hass.config_entries.async_set_disabled_by(config_entry.entry_id, None)
    await hass.async_block_till_done()

    entry1 = registry.async_get(entry1.entity_id)
    assert not entry1.disabled
    entry2 = registry.async_get(entry2.entity_id)
    assert entry2.disabled
    assert entry2.disabled_by is er.RegistryEntryDisabler.USER
    # The device was re-enabled, so entity disabled by the device will be re-enabled too
    entry3 = registry.async_get(entry3.entity_id)
    assert not entry3.disabled_by


async def test_disabled_entities_excluded_from_entity_list(hass, registry):
    """Test that disabled entities are excluded from async_entries_for_device."""
    device_registry = mock_device_registry(hass)
    config_entry = MockConfigEntry(domain="light")

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    entry1 = registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
        device_id=device_entry.id,
    )

    entry2 = registry.async_get_or_create(
        "light",
        "hue",
        "ABCD",
        config_entry=config_entry,
        device_id=device_entry.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    entries = er.async_entries_for_device(registry, device_entry.id)
    assert entries == [entry1]

    entries = er.async_entries_for_device(
        registry, device_entry.id, include_disabled_entities=True
    )
    assert entries == [entry1, entry2]


async def test_entity_max_length_exceeded(hass, registry):
    """Test that an exception is raised when the max character length is exceeded."""

    long_domain_name = (
        "1234567890123456789012345678901234567890123456789012345678901234567890"
        "1234567890123456789012345678901234567890123456789012345678901234567890"
        "1234567890123456789012345678901234567890123456789012345678901234567890"
        "1234567890123456789012345678901234567890123456789012345678901234567890"
    )

    with pytest.raises(MaxLengthExceeded) as exc_info:
        registry.async_generate_entity_id(long_domain_name, "sensor")

    assert exc_info.value.property_name == "domain"
    assert exc_info.value.max_length == 64
    assert exc_info.value.value == long_domain_name

    # Try again but force a number to get added to the entity ID
    long_entity_id_name = (
        "1234567890123456789012345678901234567890123456789012345678901234567890"
        "1234567890123456789012345678901234567890123456789012345678901234567890"
        "1234567890123456789012345678901234567890123456789012345678901234567890"
        "1234567890123456789012345678901234567"
    )

    known = []
    new_id = registry.async_generate_entity_id("sensor", long_entity_id_name, known)
    assert new_id == "sensor." + long_entity_id_name[: 255 - 7]
    known.append(new_id)
    new_id = registry.async_generate_entity_id("sensor", long_entity_id_name, known)
    assert new_id == "sensor." + long_entity_id_name[: 255 - 7 - 2] + "_2"
    known.append(new_id)
    new_id = registry.async_generate_entity_id("sensor", long_entity_id_name, known)
    assert new_id == "sensor." + long_entity_id_name[: 255 - 7 - 2] + "_3"


async def test_resolve_entity_ids(hass, registry):
    """Test resolving entity IDs."""

    entry1 = registry.async_get_or_create(
        "light", "hue", "1234", suggested_object_id="beer"
    )
    assert entry1.entity_id == "light.beer"

    entry2 = registry.async_get_or_create(
        "light", "hue", "2345", suggested_object_id="milk"
    )
    assert entry2.entity_id == "light.milk"

    expected = ["light.beer", "light.milk"]
    assert er.async_validate_entity_ids(registry, [entry1.id, entry2.id]) == expected

    expected = ["light.beer", "light.milk"]
    assert er.async_validate_entity_ids(registry, ["light.beer", entry2.id]) == expected

    with pytest.raises(vol.Invalid):
        er.async_validate_entity_ids(registry, ["light.beer", "bad_uuid"])

    expected = ["light.unknown"]
    assert er.async_validate_entity_ids(registry, ["light.unknown"]) == expected

    with pytest.raises(vol.Invalid):
        er.async_validate_entity_ids(registry, ["unknown_uuid"])


def test_entity_registry_items():
    """Test the EntityRegistryItems container."""
    entities = er.EntityRegistryItems()
    assert entities.get_entity_id(("a", "b", "c")) is None
    assert entities.get_entry("abc") is None

    entry1 = er.RegistryEntry("test.entity1", "1234", "hue")
    entry2 = er.RegistryEntry("test.entity2", "2345", "hue")
    entities["test.entity1"] = entry1
    entities["test.entity2"] = entry2

    assert entities["test.entity1"] is entry1
    assert entities["test.entity2"] is entry2

    assert entities.get_entity_id(("test", "hue", "1234")) is entry1.entity_id
    assert entities.get_entry(entry1.id) is entry1
    assert entities.get_entity_id(("test", "hue", "2345")) is entry2.entity_id
    assert entities.get_entry(entry2.id) is entry2

    entities.pop("test.entity1")
    del entities["test.entity2"]

    assert entities.get_entity_id(("test", "hue", "1234")) is None
    assert entities.get_entry(entry1.id) is None
    assert entities.get_entity_id(("test", "hue", "2345")) is None
    assert entities.get_entry(entry2.id) is None


async def test_disabled_by_str_not_allowed(hass):
    """Test we need to pass disabled by type."""
    reg = er.async_get(hass)

    with pytest.raises(ValueError):
        reg.async_get_or_create(
            "light", "hue", "1234", disabled_by=er.RegistryEntryDisabler.USER.value
        )

    entity_id = reg.async_get_or_create("light", "hue", "1234").entity_id
    with pytest.raises(ValueError):
        reg.async_update_entity(
            entity_id, disabled_by=er.RegistryEntryDisabler.USER.value
        )


async def test_entity_category_str_not_allowed(hass):
    """Test we need to pass entity category type."""
    reg = er.async_get(hass)

    with pytest.raises(ValueError):
        reg.async_get_or_create(
            "light", "hue", "1234", entity_category=EntityCategory.DIAGNOSTIC.value
        )

    entity_id = reg.async_get_or_create("light", "hue", "1234").entity_id
    with pytest.raises(ValueError):
        reg.async_update_entity(
            entity_id, entity_category=EntityCategory.DIAGNOSTIC.value
        )


async def test_hidden_by_str_not_allowed(hass):
    """Test we need to pass hidden by type."""
    reg = er.async_get(hass)

    with pytest.raises(ValueError):
        reg.async_get_or_create(
            "light", "hue", "1234", hidden_by=er.RegistryEntryHider.USER.value
        )

    entity_id = reg.async_get_or_create("light", "hue", "1234").entity_id
    with pytest.raises(ValueError):
        reg.async_update_entity(entity_id, hidden_by=er.RegistryEntryHider.USER.value)


def test_migrate_entity_to_new_platform(hass, registry):
    """Test migrate_entity_to_new_platform."""
    orig_config_entry = MockConfigEntry(domain="light")
    orig_unique_id = "5678"

    orig_entry = registry.async_get_or_create(
        "light",
        "hue",
        orig_unique_id,
        suggested_object_id="light",
        config_entry=orig_config_entry,
        disabled_by=er.RegistryEntryDisabler.USER,
        entity_category=EntityCategory.CONFIG,
        original_device_class="mock-device-class",
        original_icon="initial-original_icon",
        original_name="initial-original_name",
    )
    assert registry.async_get("light.light") is orig_entry
    registry.async_update_entity(
        "light.light",
        name="new_name",
        icon="new_icon",
    )

    new_config_entry = MockConfigEntry(domain="light")
    new_unique_id = "1234"

    assert registry.async_update_entity_platform(
        "light.light",
        "hue2",
        new_unique_id=new_unique_id,
        new_config_entry_id=new_config_entry.entry_id,
    )

    assert not registry.async_get_entity_id("light", "hue", orig_unique_id)

    assert (new_entry := registry.async_get("light.light")) is not orig_entry

    assert new_entry.config_entry_id == new_config_entry.entry_id
    assert new_entry.unique_id == new_unique_id
    assert new_entry.name == "new_name"
    assert new_entry.icon == "new_icon"
    assert new_entry.platform == "hue2"

    # Test nonexisting entity
    with pytest.raises(KeyError):
        registry.async_update_entity_platform(
            "light.not_a_real_light",
            "hue2",
            new_unique_id=new_unique_id,
            new_config_entry_id=new_config_entry.entry_id,
        )

    # Test migrate entity without new config entry ID
    with pytest.raises(ValueError):
        registry.async_update_entity_platform(
            "light.light",
            "hue3",
        )

    # Test entity with a state
    hass.states.async_set("light.light", "on")
    with pytest.raises(ValueError):
        registry.async_update_entity_platform(
            "light.light",
            "hue2",
            new_unique_id=new_unique_id,
            new_config_entry_id=new_config_entry.entry_id,
        )
