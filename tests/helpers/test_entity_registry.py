"""Tests for the Entity Registry."""
from datetime import timedelta
from typing import Any
from unittest.mock import patch

import attr
import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.exceptions import MaxLengthExceeded
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, flush_store

YAML__OPEN_PATH = "homeassistant.util.yaml.loader.open"


@pytest.fixture
def update_events(hass):
    """Capture update events."""
    events = []

    @callback
    def async_capture(event):
        events.append(event.data)

    hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, async_capture)

    return events


async def test_get(hass: HomeAssistant, entity_registry: er.EntityRegistry):
    """Test we can get an item."""
    entry = entity_registry.async_get_or_create("light", "hue", "1234")

    assert entity_registry.async_get(entry.entity_id) is entry
    assert entity_registry.async_get(entry.id) is entry
    assert entity_registry.async_get("blah") is None
    assert entity_registry.async_get("blah.blah") is None


async def test_get_or_create_returns_same_entry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, update_events
) -> None:
    """Make sure we do not duplicate entries."""
    entry = entity_registry.async_get_or_create("light", "hue", "1234")
    entry2 = entity_registry.async_get_or_create("light", "hue", "1234")

    await hass.async_block_till_done()

    assert len(entity_registry.entities) == 1
    assert entry is entry2
    assert entry.entity_id == "light.hue_1234"
    assert len(update_events) == 1
    assert update_events[0]["action"] == "create"
    assert update_events[0]["entity_id"] == entry.entity_id


def test_get_or_create_suggested_object_id(entity_registry: er.EntityRegistry) -> None:
    """Test that suggested_object_id works."""
    entry = entity_registry.async_get_or_create(
        "light", "hue", "1234", suggested_object_id="beer"
    )

    assert entry.entity_id == "light.beer"


def test_get_or_create_updates_data(entity_registry: er.EntityRegistry) -> None:
    """Test that we update data in get_or_create."""
    orig_config_entry = MockConfigEntry(domain="light")

    orig_entry = entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
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
        translation_key="initial-translation_key",
        unit_of_measurement="initial-unit_of_measurement",
    )

    assert orig_entry == er.RegistryEntry(
        "light.hue_5678",
        "5678",
        "hue",
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
        translation_key="initial-translation_key",
        unit_of_measurement="initial-unit_of_measurement",
    )

    new_config_entry = MockConfigEntry(domain="light")

    new_entry = entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        capabilities={"new-max": 150},
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
        translation_key="updated-translation_key",
        unit_of_measurement="updated-unit_of_measurement",
    )

    assert new_entry == er.RegistryEntry(
        "light.hue_5678",
        "5678",
        "hue",
        aliases=set(),
        area_id=None,
        capabilities={"new-max": 150},
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
        translation_key="updated-translation_key",
        unit_of_measurement="updated-unit_of_measurement",
    )

    new_entry = entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
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
        translation_key=None,
        unit_of_measurement=None,
    )

    assert new_entry == er.RegistryEntry(
        "light.hue_5678",
        "5678",
        "hue",
        aliases=set(),
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
        translation_key=None,
        unit_of_measurement=None,
    )


def test_get_or_create_suggested_object_id_conflict_register(
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that we don't generate an entity id that is already registered."""
    entry = entity_registry.async_get_or_create(
        "light", "hue", "1234", suggested_object_id="beer"
    )
    entry2 = entity_registry.async_get_or_create(
        "light", "hue", "5678", suggested_object_id="beer"
    )

    assert entry.entity_id == "light.beer"
    assert entry2.entity_id == "light.beer_2"


def test_get_or_create_suggested_object_id_conflict_existing(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that we don't generate an entity id that currently exists."""
    hass.states.async_set("light.hue_1234", "on")
    entry = entity_registry.async_get_or_create("light", "hue", "1234")
    assert entry.entity_id == "light.hue_1234_2"


def test_create_triggers_save(entity_registry: er.EntityRegistry) -> None:
    """Test that registering entry triggers a save."""
    with patch.object(entity_registry, "async_schedule_save") as mock_schedule_save:
        entity_registry.async_get_or_create("light", "hue", "1234")

    assert len(mock_schedule_save.mock_calls) == 1


async def test_loading_saving_data(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that we load/save data correctly."""
    mock_config = MockConfigEntry(domain="light")

    orig_entry1 = entity_registry.async_get_or_create("light", "hue", "1234")
    orig_entry2 = entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
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
        translation_key="initial-translation_key",
        unit_of_measurement="initial-unit_of_measurement",
    )
    entity_registry.async_update_entity(
        orig_entry2.entity_id,
        aliases={"initial_alias_1", "initial_alias_2"},
        area_id="mock-area-id",
        device_class="user-class",
        name="User Name",
        icon="hass:user-icon",
    )
    entity_registry.async_update_entity_options(
        orig_entry2.entity_id, "light", {"minimum_brightness": 20}
    )
    orig_entry2 = entity_registry.async_get(orig_entry2.entity_id)
    orig_entry3 = entity_registry.async_get_or_create("light", "hue", "ABCD")
    orig_entry4 = entity_registry.async_get_or_create("light", "hue", "EFGH")
    entity_registry.async_remove(orig_entry3.entity_id)
    entity_registry.async_remove(orig_entry4.entity_id)

    assert len(entity_registry.entities) == 2
    assert len(entity_registry.deleted_entities) == 2

    # Now load written data in new registry
    registry2 = er.EntityRegistry(hass)
    await flush_store(entity_registry._store)
    await registry2.async_load()

    # Ensure same order
    assert list(entity_registry.entities) == list(registry2.entities)
    assert list(entity_registry.deleted_entities) == list(registry2.deleted_entities)
    new_entry1 = entity_registry.async_get_or_create("light", "hue", "1234")
    new_entry2 = entity_registry.async_get_or_create("light", "hue", "5678")
    new_entry3 = entity_registry.async_get_or_create("light", "hue", "ABCD")
    new_entry4 = entity_registry.async_get_or_create("light", "hue", "EFGH")

    assert orig_entry1 == new_entry1
    assert orig_entry2 == new_entry2
    assert orig_entry3 == new_entry3
    assert orig_entry4 == new_entry4

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
    assert new_entry2.translation_key == "initial-translation_key"
    assert new_entry2.unit_of_measurement == "initial-unit_of_measurement"


def test_generate_entity_considers_registered_entities(
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that we don't create entity id that are already registered."""
    entry = entity_registry.async_get_or_create("light", "hue", "1234")
    assert entry.entity_id == "light.hue_1234"
    assert (
        entity_registry.async_generate_entity_id("light", "hue_1234")
        == "light.hue_1234_2"
    )


def test_generate_entity_considers_existing_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that we don't create entity id that currently exists."""
    hass.states.async_set("light.kitchen", "on")
    assert (
        entity_registry.async_generate_entity_id("light", "kitchen")
        == "light.kitchen_2"
    )


def test_is_registered(entity_registry: er.EntityRegistry) -> None:
    """Test that is_registered works."""
    entry = entity_registry.async_get_or_create("light", "hue", "1234")
    assert entity_registry.async_is_registered(entry.entity_id)
    assert not entity_registry.async_is_registered("light.non_existing")


@pytest.mark.parametrize("load_registries", [False])
async def test_filter_on_load(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
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


def test_async_get_entity_id(entity_registry: er.EntityRegistry) -> None:
    """Test that entity_id is returned."""
    entry = entity_registry.async_get_or_create("light", "hue", "1234")
    assert entry.entity_id == "light.hue_1234"
    assert (
        entity_registry.async_get_entity_id("light", "hue", "1234") == "light.hue_1234"
    )
    assert entity_registry.async_get_entity_id("light", "hue", "123") is None


async def test_updating_config_entry_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, update_events
) -> None:
    """Test that we update config entry id in registry."""
    mock_config_1 = MockConfigEntry(domain="light", entry_id="mock-id-1")
    entry = entity_registry.async_get_or_create(
        "light", "hue", "5678", config_entry=mock_config_1
    )

    mock_config_2 = MockConfigEntry(domain="light", entry_id="mock-id-2")
    entry2 = entity_registry.async_get_or_create(
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


async def test_removing_config_entry_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, update_events
) -> None:
    """Test that we update config entry id in registry."""
    mock_config = MockConfigEntry(domain="light", entry_id="mock-id-1")

    entry = entity_registry.async_get_or_create(
        "light", "hue", "5678", config_entry=mock_config
    )
    assert entry.config_entry_id == "mock-id-1"
    entity_registry.async_clear_config_entry("mock-id-1")

    assert not entity_registry.entities

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0]["action"] == "create"
    assert update_events[0]["entity_id"] == entry.entity_id
    assert update_events[1]["action"] == "remove"
    assert update_events[1]["entity_id"] == entry.entity_id


async def test_deleted_entity_removing_config_entry_id(
    hass, entity_registry: er.EntityRegistry
):
    """Test that we update config entry id in registry on deleted entity."""
    mock_config = MockConfigEntry(domain="light", entry_id="mock-id-1")

    entry = entity_registry.async_get_or_create(
        "light", "hue", "5678", config_entry=mock_config
    )
    assert entry.config_entry_id == "mock-id-1"
    entity_registry.async_remove(entry.entity_id)

    assert len(entity_registry.entities) == 0
    assert len(entity_registry.deleted_entities) == 1
    assert (
        entity_registry.deleted_entities[("light", "hue", "5678")].config_entry_id
        == "mock-id-1"
    )
    assert (
        entity_registry.deleted_entities[("light", "hue", "5678")].orphaned_timestamp
        is None
    )

    entity_registry.async_clear_config_entry("mock-id-1")
    assert len(entity_registry.entities) == 0
    assert len(entity_registry.deleted_entities) == 1
    assert (
        entity_registry.deleted_entities[("light", "hue", "5678")].config_entry_id
        is None
    )
    assert (
        entity_registry.deleted_entities[("light", "hue", "5678")].orphaned_timestamp
        is not None
    )


async def test_removing_area_id(entity_registry: er.EntityRegistry) -> None:
    """Make sure we can clear area id."""
    entry = entity_registry.async_get_or_create("light", "hue", "5678")

    entry_w_area = entity_registry.async_update_entity(
        entry.entity_id, area_id="12345A"
    )

    entity_registry.async_clear_area_id("12345A")
    entry_wo_area = entity_registry.async_get(entry.entity_id)

    assert not entry_wo_area.area_id
    assert entry_w_area != entry_wo_area


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_1_1(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
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
async def test_migration_1_7(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
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


async def test_update_entity_unique_id(entity_registry: er.EntityRegistry) -> None:
    """Test entity's unique_id is updated."""
    mock_config = MockConfigEntry(domain="light", entry_id="mock-id-1")

    entry = entity_registry.async_get_or_create(
        "light", "hue", "5678", config_entry=mock_config
    )
    assert (
        entity_registry.async_get_entity_id("light", "hue", "5678") == entry.entity_id
    )

    new_unique_id = "1234"
    with patch.object(entity_registry, "async_schedule_save") as mock_schedule_save:
        updated_entry = entity_registry.async_update_entity(
            entry.entity_id, new_unique_id=new_unique_id
        )
    assert updated_entry != entry
    assert updated_entry.unique_id == new_unique_id
    assert updated_entry.previous_unique_id == "5678"
    assert mock_schedule_save.call_count == 1

    assert entity_registry.async_get_entity_id("light", "hue", "5678") is None
    assert (
        entity_registry.async_get_entity_id("light", "hue", "1234") == entry.entity_id
    )


async def test_update_entity_unique_id_conflict(
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration raises when unique_id already in use."""
    mock_config = MockConfigEntry(domain="light", entry_id="mock-id-1")
    entry = entity_registry.async_get_or_create(
        "light", "hue", "5678", config_entry=mock_config
    )
    entry2 = entity_registry.async_get_or_create(
        "light", "hue", "1234", config_entry=mock_config
    )
    with patch.object(
        entity_registry, "async_schedule_save"
    ) as mock_schedule_save, pytest.raises(ValueError):
        entity_registry.async_update_entity(
            entry.entity_id, new_unique_id=entry2.unique_id
        )
    assert mock_schedule_save.call_count == 0
    assert (
        entity_registry.async_get_entity_id("light", "hue", "5678") == entry.entity_id
    )
    assert (
        entity_registry.async_get_entity_id("light", "hue", "1234") == entry2.entity_id
    )


async def test_update_entity_entity_id(entity_registry: er.EntityRegistry) -> None:
    """Test entity's entity_id is updated."""
    entry = entity_registry.async_get_or_create("light", "hue", "5678")
    assert (
        entity_registry.async_get_entity_id("light", "hue", "5678") == entry.entity_id
    )

    new_entity_id = "light.blah"
    assert new_entity_id != entry.entity_id
    with patch.object(entity_registry, "async_schedule_save") as mock_schedule_save:
        updated_entry = entity_registry.async_update_entity(
            entry.entity_id, new_entity_id=new_entity_id
        )
    assert updated_entry != entry
    assert updated_entry.entity_id == new_entity_id
    assert mock_schedule_save.call_count == 1

    assert entity_registry.async_get(entry.entity_id) is None
    assert entity_registry.async_get(new_entity_id) is not None


async def test_update_entity_entity_id_entity_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test update raises when entity_id already in use."""
    entry = entity_registry.async_get_or_create("light", "hue", "5678")
    entry2 = entity_registry.async_get_or_create("light", "hue", "1234")
    state_entity_id = "light.blah"
    hass.states.async_set(state_entity_id, "on")
    assert entry.entity_id != state_entity_id
    assert entry2.entity_id != state_entity_id

    # Try updating to a registered entity_id
    with patch.object(
        entity_registry, "async_schedule_save"
    ) as mock_schedule_save, pytest.raises(ValueError):
        entity_registry.async_update_entity(
            entry.entity_id, new_entity_id=entry2.entity_id
        )
    assert mock_schedule_save.call_count == 0
    assert (
        entity_registry.async_get_entity_id("light", "hue", "5678") == entry.entity_id
    )
    assert entity_registry.async_get(entry.entity_id) is entry
    assert (
        entity_registry.async_get_entity_id("light", "hue", "1234") == entry2.entity_id
    )
    assert entity_registry.async_get(entry2.entity_id) is entry2

    # Try updating to an entity_id which is in the state machine
    with patch.object(
        entity_registry, "async_schedule_save"
    ) as mock_schedule_save, pytest.raises(ValueError):
        entity_registry.async_update_entity(
            entry.entity_id, new_entity_id=state_entity_id
        )
    assert mock_schedule_save.call_count == 0
    assert (
        entity_registry.async_get_entity_id("light", "hue", "5678") == entry.entity_id
    )
    assert entity_registry.async_get(entry.entity_id) is entry
    assert entity_registry.async_get(state_entity_id) is None


async def test_update_entity(entity_registry: er.EntityRegistry) -> None:
    """Test updating entity."""
    mock_config = MockConfigEntry(domain="light", entry_id="mock-id-1")
    entry = entity_registry.async_get_or_create(
        "light", "hue", "5678", config_entry=mock_config
    )

    for attr_name, new_value in (
        ("aliases", {"alias_1", "alias_2"}),
        ("disabled_by", er.RegistryEntryDisabler.USER),
        ("icon", "new icon"),
        ("name", "new name"),
    ):
        changes = {attr_name: new_value}
        updated_entry = entity_registry.async_update_entity(entry.entity_id, **changes)

        assert updated_entry != entry
        assert getattr(updated_entry, attr_name) == new_value
        assert getattr(updated_entry, attr_name) != getattr(entry, attr_name)

        assert (
            entity_registry.async_get_entity_id("light", "hue", "5678")
            == updated_entry.entity_id
        )
        entry = updated_entry


async def test_update_entity_options(entity_registry: er.EntityRegistry) -> None:
    """Test updating entity."""
    mock_config = MockConfigEntry(domain="light", entry_id="mock-id-1")
    entry = entity_registry.async_get_or_create(
        "light", "hue", "5678", config_entry=mock_config
    )

    entity_registry.async_update_entity_options(
        entry.entity_id, "light", {"minimum_brightness": 20}
    )
    new_entry_1 = entity_registry.async_get(entry.entity_id)

    assert entry.options == {}
    assert new_entry_1.options == {"light": {"minimum_brightness": 20}}

    # Test it's not possible to modify the options
    with pytest.raises(RuntimeError):
        new_entry_1.options["blah"] = {}
    with pytest.raises(RuntimeError):
        new_entry_1.options["light"] = {}
    with pytest.raises(RuntimeError):
        new_entry_1.options["light"]["blah"] = 123
    with pytest.raises(RuntimeError):
        new_entry_1.options["light"]["minimum_brightness"] = 123

    entity_registry.async_update_entity_options(
        entry.entity_id, "light", {"minimum_brightness": 30}
    )
    new_entry_2 = entity_registry.async_get(entry.entity_id)

    assert entry.options == {}
    assert new_entry_1.options == {"light": {"minimum_brightness": 20}}
    assert new_entry_2.options == {"light": {"minimum_brightness": 30}}


async def test_disabled_by(entity_registry: er.EntityRegistry) -> None:
    """Test that we can disable an entry when we create it."""
    entry = entity_registry.async_get_or_create(
        "light", "hue", "5678", disabled_by=er.RegistryEntryDisabler.HASS
    )
    assert entry.disabled_by is er.RegistryEntryDisabler.HASS

    entry = entity_registry.async_get_or_create(
        "light", "hue", "5678", disabled_by=er.RegistryEntryDisabler.INTEGRATION
    )
    assert entry.disabled_by is er.RegistryEntryDisabler.HASS

    entry2 = entity_registry.async_get_or_create("light", "hue", "1234")
    assert entry2.disabled_by is None


async def test_disabled_by_config_entry_pref(
    entity_registry: er.EntityRegistry,
) -> None:
    """Test config entry preference setting disabled_by."""
    mock_config = MockConfigEntry(
        domain="light",
        entry_id="mock-id-1",
        pref_disable_new_entities=True,
    )
    entry = entity_registry.async_get_or_create(
        "light", "hue", "AAAA", config_entry=mock_config
    )
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    entry2 = entity_registry.async_get_or_create(
        "light",
        "hue",
        "BBBB",
        config_entry=mock_config,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    assert entry2.disabled_by is er.RegistryEntryDisabler.USER


async def test_restore_states(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test restoring states."""
    hass.set_state(CoreState.not_running)

    entity_registry.async_get_or_create(
        "light",
        "hue",
        "1234",
        suggested_object_id="simple",
    )
    # Should not be created
    entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        suggested_object_id="disabled",
        disabled_by=er.RegistryEntryDisabler.HASS,
    )
    entity_registry.async_get_or_create(
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

    entity_registry.async_remove("light.disabled")
    entity_registry.async_remove("light.simple")
    entity_registry.async_remove("light.all_info_set")

    await hass.async_block_till_done()

    assert hass.states.get("light.simple") is None
    assert hass.states.get("light.disabled") is None
    assert hass.states.get("light.all_info_set") is None


async def test_async_get_device_class_lookup(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test registry device class lookup."""
    hass.set_state(CoreState.not_running)

    entity_registry.async_get_or_create(
        "binary_sensor",
        "light",
        "battery_charging",
        device_id="light_device_entry_id",
        original_device_class="battery_charging",
    )
    entity_registry.async_get_or_create(
        "sensor",
        "light",
        "battery",
        device_id="light_device_entry_id",
        original_device_class="battery",
    )
    entity_registry.async_get_or_create(
        "light", "light", "demo", device_id="light_device_entry_id"
    )
    entity_registry.async_get_or_create(
        "binary_sensor",
        "vacuum",
        "battery_charging",
        device_id="vacuum_device_entry_id",
        original_device_class="battery_charging",
    )
    entity_registry.async_get_or_create(
        "sensor",
        "vacuum",
        "battery",
        device_id="vacuum_device_entry_id",
        original_device_class="battery",
    )
    entity_registry.async_get_or_create(
        "vacuum", "vacuum", "demo", device_id="vacuum_device_entry_id"
    )
    entity_registry.async_get_or_create(
        "binary_sensor",
        "remote",
        "battery_charging",
        device_id="remote_device_entry_id",
        original_device_class="battery_charging",
    )
    entity_registry.async_get_or_create(
        "remote", "remote", "demo", device_id="remote_device_entry_id"
    )

    device_lookup = entity_registry.async_get_device_class_lookup(
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


async def test_remove_device_removes_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that we remove entities tied to a device."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    entry = entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
        device_id=device_entry.id,
    )

    assert entity_registry.async_is_registered(entry.entity_id)

    device_registry.async_remove_device(device_entry.id)
    await hass.async_block_till_done()

    assert not entity_registry.async_is_registered(entry.entity_id)


async def test_remove_config_entry_from_device_removes_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that we remove entities tied to a device when config entry is removed."""
    config_entry_1 = MockConfigEntry(domain="hue")
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry(domain="device_tracker")
    config_entry_2.add_to_hass(hass)

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
    entry_1 = entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry_1,
        device_id=device_entry.id,
    )

    entry_2 = entity_registry.async_get_or_create(
        "sensor",
        "device_tracker",
        "6789",
        config_entry=config_entry_2,
        device_id=device_entry.id,
    )

    assert entity_registry.async_is_registered(entry_1.entity_id)
    assert entity_registry.async_is_registered(entry_2.entity_id)

    # Remove the first config entry from the device, the entity associated with it
    # should be removed
    device_registry.async_update_device(
        device_entry.id, remove_config_entry_id=config_entry_1.entry_id
    )
    await hass.async_block_till_done()

    assert device_registry.async_get(device_entry.id)
    assert not entity_registry.async_is_registered(entry_1.entity_id)
    assert entity_registry.async_is_registered(entry_2.entity_id)

    # Remove the second config entry from the device, the entity associated with it
    # (and the device itself) should be removed
    device_registry.async_update_device(
        device_entry.id, remove_config_entry_id=config_entry_2.entry_id
    )
    await hass.async_block_till_done()

    assert not device_registry.async_get(device_entry.id)
    assert not entity_registry.async_is_registered(entry_1.entity_id)
    assert not entity_registry.async_is_registered(entry_2.entity_id)


async def test_remove_config_entry_from_device_removes_entities_2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that we don't remove entities with no config entry when device is modified."""
    config_entry_1 = MockConfigEntry(domain="hue")
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry(domain="device_tracker")
    config_entry_2.add_to_hass(hass)

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
    entry_1 = entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        device_id=device_entry.id,
    )

    assert entity_registry.async_is_registered(entry_1.entity_id)

    # Remove the first config entry from the device
    device_registry.async_update_device(
        device_entry.id, remove_config_entry_id=config_entry_1.entry_id
    )
    await hass.async_block_till_done()

    assert device_registry.async_get(device_entry.id)
    assert entity_registry.async_is_registered(entry_1.entity_id)


async def test_update_device_race(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test race when a device is created, updated and removed."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)

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
    entry = entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
        device_id=device_entry.id,
    )

    assert entity_registry.async_is_registered(entry.entity_id)

    device_registry.async_remove_device(device_entry.id)
    await hass.async_block_till_done()

    assert not entity_registry.async_is_registered(entry.entity_id)


async def test_disable_device_disables_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that we disable entities tied to a device."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    entry1 = entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
        device_id=device_entry.id,
    )
    entry2 = entity_registry.async_get_or_create(
        "light",
        "hue",
        "ABCD",
        config_entry=config_entry,
        device_id=device_entry.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    entry3 = entity_registry.async_get_or_create(
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

    entry1 = entity_registry.async_get(entry1.entity_id)
    assert entry1.disabled
    assert entry1.disabled_by is er.RegistryEntryDisabler.DEVICE
    entry2 = entity_registry.async_get(entry2.entity_id)
    assert entry2.disabled
    assert entry2.disabled_by is er.RegistryEntryDisabler.USER
    entry3 = entity_registry.async_get(entry3.entity_id)
    assert entry3.disabled
    assert entry3.disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY

    device_registry.async_update_device(device_entry.id, disabled_by=None)
    await hass.async_block_till_done()

    entry1 = entity_registry.async_get(entry1.entity_id)
    assert not entry1.disabled
    entry2 = entity_registry.async_get(entry2.entity_id)
    assert entry2.disabled
    assert entry2.disabled_by is er.RegistryEntryDisabler.USER
    entry3 = entity_registry.async_get(entry3.entity_id)
    assert entry3.disabled
    assert entry3.disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY


async def test_disable_config_entry_disables_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that we disable entities tied to a config entry."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    entry1 = entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
        device_id=device_entry.id,
    )
    entry2 = entity_registry.async_get_or_create(
        "light",
        "hue",
        "ABCD",
        config_entry=config_entry,
        device_id=device_entry.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    entry3 = entity_registry.async_get_or_create(
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

    entry1 = entity_registry.async_get(entry1.entity_id)
    assert entry1.disabled
    assert entry1.disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY
    entry2 = entity_registry.async_get(entry2.entity_id)
    assert entry2.disabled
    assert entry2.disabled_by is er.RegistryEntryDisabler.USER
    entry3 = entity_registry.async_get(entry3.entity_id)
    assert entry3.disabled
    assert entry3.disabled_by is er.RegistryEntryDisabler.DEVICE

    await hass.config_entries.async_set_disabled_by(config_entry.entry_id, None)
    await hass.async_block_till_done()

    entry1 = entity_registry.async_get(entry1.entity_id)
    assert not entry1.disabled
    entry2 = entity_registry.async_get(entry2.entity_id)
    assert entry2.disabled
    assert entry2.disabled_by is er.RegistryEntryDisabler.USER
    # The device was re-enabled, so entity disabled by the device will be re-enabled too
    entry3 = entity_registry.async_get(entry3.entity_id)
    assert not entry3.disabled_by


async def test_disabled_entities_excluded_from_entity_list(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that disabled entities are excluded from async_entries_for_device."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    entry1 = entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
        device_id=device_entry.id,
    )

    entry2 = entity_registry.async_get_or_create(
        "light",
        "hue",
        "ABCD",
        config_entry=config_entry,
        device_id=device_entry.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    assert entries == [entry1]

    entries = er.async_entries_for_device(
        entity_registry, device_entry.id, include_disabled_entities=True
    )
    assert entries == [entry1, entry2]

    ent_reg = er.async_get(hass)
    assert ent_reg.entities.get_entries_for_device_id(device_entry.id) == [entry1]

    assert ent_reg.entities.get_entries_for_device_id(
        device_entry.id, include_disabled_entities=True
    ) == [entry1, entry2]


async def test_entity_max_length_exceeded(entity_registry: er.EntityRegistry) -> None:
    """Test that an exception is raised when the max character length is exceeded."""

    long_domain_name = (
        "1234567890123456789012345678901234567890123456789012345678901234567890"
        "1234567890123456789012345678901234567890123456789012345678901234567890"
        "1234567890123456789012345678901234567890123456789012345678901234567890"
        "1234567890123456789012345678901234567890123456789012345678901234567890"
    )

    with pytest.raises(MaxLengthExceeded) as exc_info:
        entity_registry.async_generate_entity_id(long_domain_name, "sensor")

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
    new_id = entity_registry.async_generate_entity_id(
        "sensor", long_entity_id_name, known
    )
    assert new_id == "sensor." + long_entity_id_name[: 255 - 7]
    known.append(new_id)
    new_id = entity_registry.async_generate_entity_id(
        "sensor", long_entity_id_name, known
    )
    assert new_id == "sensor." + long_entity_id_name[: 255 - 7 - 2] + "_2"
    known.append(new_id)
    new_id = entity_registry.async_generate_entity_id(
        "sensor", long_entity_id_name, known
    )
    assert new_id == "sensor." + long_entity_id_name[: 255 - 7 - 2] + "_3"


async def test_resolve_entity_ids(entity_registry: er.EntityRegistry) -> None:
    """Test resolving entity IDs."""

    entry1 = entity_registry.async_get_or_create(
        "light", "hue", "1234", suggested_object_id="beer"
    )
    assert entry1.entity_id == "light.beer"

    entry2 = entity_registry.async_get_or_create(
        "light", "hue", "2345", suggested_object_id="milk"
    )
    assert entry2.entity_id == "light.milk"

    expected = ["light.beer", "light.milk"]
    assert (
        er.async_validate_entity_ids(entity_registry, [entry1.id, entry2.id])
        == expected
    )

    expected = ["light.beer", "light.milk"]
    assert (
        er.async_validate_entity_ids(entity_registry, ["light.beer", entry2.id])
        == expected
    )

    with pytest.raises(vol.Invalid):
        er.async_validate_entity_ids(entity_registry, ["light.beer", "bad_uuid"])

    expected = ["light.unknown"]
    assert er.async_validate_entity_ids(entity_registry, ["light.unknown"]) == expected

    with pytest.raises(vol.Invalid):
        er.async_validate_entity_ids(entity_registry, ["unknown_uuid"])


def test_entity_registry_items() -> None:
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


async def test_disabled_by_str_not_allowed(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test we need to pass disabled by type."""
    with pytest.raises(ValueError):
        entity_registry.async_get_or_create(
            "light", "hue", "1234", disabled_by=er.RegistryEntryDisabler.USER.value
        )

    entity_id = entity_registry.async_get_or_create("light", "hue", "1234").entity_id
    with pytest.raises(ValueError):
        entity_registry.async_update_entity(
            entity_id, disabled_by=er.RegistryEntryDisabler.USER.value
        )


async def test_entity_category_str_not_allowed(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test we need to pass entity category type."""
    with pytest.raises(ValueError):
        entity_registry.async_get_or_create(
            "light", "hue", "1234", entity_category=EntityCategory.DIAGNOSTIC.value
        )

    entity_id = entity_registry.async_get_or_create("light", "hue", "1234").entity_id
    with pytest.raises(ValueError):
        entity_registry.async_update_entity(
            entity_id, entity_category=EntityCategory.DIAGNOSTIC.value
        )


async def test_hidden_by_str_not_allowed(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test we need to pass hidden by type."""
    with pytest.raises(ValueError):
        entity_registry.async_get_or_create(
            "light", "hue", "1234", hidden_by=er.RegistryEntryHider.USER.value
        )

    entity_id = entity_registry.async_get_or_create("light", "hue", "1234").entity_id
    with pytest.raises(ValueError):
        entity_registry.async_update_entity(
            entity_id, hidden_by=er.RegistryEntryHider.USER.value
        )


def test_migrate_entity_to_new_platform(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test migrate_entity_to_new_platform."""
    orig_config_entry = MockConfigEntry(domain="light")
    orig_unique_id = "5678"

    orig_entry = entity_registry.async_get_or_create(
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
    assert entity_registry.async_get("light.light") is orig_entry
    entity_registry.async_update_entity(
        "light.light",
        name="new_name",
        icon="new_icon",
    )

    new_config_entry = MockConfigEntry(domain="light")
    new_unique_id = "1234"

    assert entity_registry.async_update_entity_platform(
        "light.light",
        "hue2",
        new_unique_id=new_unique_id,
        new_config_entry_id=new_config_entry.entry_id,
    )

    assert not entity_registry.async_get_entity_id("light", "hue", orig_unique_id)

    assert (new_entry := entity_registry.async_get("light.light")) is not orig_entry

    assert new_entry.config_entry_id == new_config_entry.entry_id
    assert new_entry.unique_id == new_unique_id
    assert new_entry.name == "new_name"
    assert new_entry.icon == "new_icon"
    assert new_entry.platform == "hue2"

    # Test nonexisting entity
    with pytest.raises(KeyError):
        entity_registry.async_update_entity_platform(
            "light.not_a_real_light",
            "hue2",
            new_unique_id=new_unique_id,
            new_config_entry_id=new_config_entry.entry_id,
        )

    # Test migrate entity without new config entry ID
    with pytest.raises(ValueError):
        entity_registry.async_update_entity_platform(
            "light.light",
            "hue3",
        )

    # Test entity with a state
    hass.states.async_set("light.light", "on")
    with pytest.raises(ValueError):
        entity_registry.async_update_entity_platform(
            "light.light",
            "hue2",
            new_unique_id=new_unique_id,
            new_config_entry_id=new_config_entry.entry_id,
        )


async def test_restore_entity(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, update_events, freezer
):
    """Make sure entity registry id is stable and entity_id is reused if possible."""
    config_entry = MockConfigEntry(domain="light")
    entry1 = entity_registry.async_get_or_create(
        "light", "hue", "1234", config_entry=config_entry
    )
    entry2 = entity_registry.async_get_or_create(
        "light", "hue", "5678", config_entry=config_entry
    )

    entry1 = entity_registry.async_update_entity(
        entry1.entity_id, new_entity_id="light.custom_1"
    )

    entity_registry.async_remove(entry1.entity_id)
    entity_registry.async_remove(entry2.entity_id)
    assert len(entity_registry.entities) == 0
    assert len(entity_registry.deleted_entities) == 2

    # Re-add entities
    entry1_restored = entity_registry.async_get_or_create(
        "light", "hue", "1234", config_entry=config_entry
    )
    entry2_restored = entity_registry.async_get_or_create("light", "hue", "5678")

    assert len(entity_registry.entities) == 2
    assert len(entity_registry.deleted_entities) == 0
    assert entry1 != entry1_restored
    # entity_id is not restored
    assert attr.evolve(entry1, entity_id="light.hue_1234") == entry1_restored
    assert entry2 != entry2_restored
    # Config entry is not restored
    assert attr.evolve(entry2, config_entry_id=None) == entry2_restored

    # Remove two of the entities again, then bump time
    entity_registry.async_remove(entry1_restored.entity_id)
    entity_registry.async_remove(entry2.entity_id)
    assert len(entity_registry.entities) == 0
    assert len(entity_registry.deleted_entities) == 2
    freezer.tick(timedelta(seconds=er.ORPHANED_ENTITY_KEEP_SECONDS + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Re-add two entities, expect to get a new id after the purge for entity w/o config entry
    entry1_restored = entity_registry.async_get_or_create(
        "light", "hue", "1234", config_entry=config_entry
    )
    entry2_restored = entity_registry.async_get_or_create("light", "hue", "5678")
    assert len(entity_registry.entities) == 2
    assert len(entity_registry.deleted_entities) == 0
    assert entry1.id == entry1_restored.id
    assert entry2.id != entry2_restored.id

    # Remove the first entity, then its config entry, finally bump time
    entity_registry.async_remove(entry1_restored.entity_id)
    assert len(entity_registry.entities) == 1
    assert len(entity_registry.deleted_entities) == 1
    entity_registry.async_clear_config_entry(config_entry.entry_id)
    freezer.tick(timedelta(seconds=er.ORPHANED_ENTITY_KEEP_SECONDS + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Re-add the entity, expect to get a new id after the purge
    entry1_restored = entity_registry.async_get_or_create(
        "light", "hue", "1234", config_entry=config_entry
    )
    assert len(entity_registry.entities) == 2
    assert len(entity_registry.deleted_entities) == 0
    assert entry1.id != entry1_restored.id

    # Check the events
    await hass.async_block_till_done()
    assert len(update_events) == 13
    assert update_events[0] == {"action": "create", "entity_id": "light.hue_1234"}
    assert update_events[1] == {"action": "create", "entity_id": "light.hue_5678"}
    assert update_events[2]["action"] == "update"
    assert update_events[3] == {"action": "remove", "entity_id": "light.custom_1"}
    assert update_events[4] == {"action": "remove", "entity_id": "light.hue_5678"}
    # Restore entities the 1st time
    assert update_events[5] == {"action": "create", "entity_id": "light.hue_1234"}
    assert update_events[6] == {"action": "create", "entity_id": "light.hue_5678"}
    assert update_events[7] == {"action": "remove", "entity_id": "light.hue_1234"}
    assert update_events[8] == {"action": "remove", "entity_id": "light.hue_5678"}
    # Restore entities the 2nd time
    assert update_events[9] == {"action": "create", "entity_id": "light.hue_1234"}
    assert update_events[10] == {"action": "create", "entity_id": "light.hue_5678"}
    assert update_events[11] == {"action": "remove", "entity_id": "light.hue_1234"}
    # Restore entities the 3rd time
    assert update_events[12] == {"action": "create", "entity_id": "light.hue_1234"}


async def test_async_migrate_entry_delete_self(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
):
    """Test async_migrate_entry."""
    config_entry1 = MockConfigEntry(domain="test1")
    config_entry2 = MockConfigEntry(domain="test2")
    entry1 = entity_registry.async_get_or_create(
        "light", "hue", "1234", config_entry=config_entry1, original_name="Entry 1"
    )
    entry2 = entity_registry.async_get_or_create(
        "light", "hue", "5678", config_entry=config_entry1, original_name="Entry 2"
    )
    entry3 = entity_registry.async_get_or_create(
        "light", "hue", "90AB", config_entry=config_entry2, original_name="Entry 3"
    )

    @callback
    def _async_migrator(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:
        entries.add(entity_entry.entity_id)
        if entity_entry == entry1:
            entity_registry.async_remove(entry1.entity_id)
            return None
        if entity_entry == entry2:
            return {"original_name": "Entry 2 renamed"}
        return None

    entries = set()
    await er.async_migrate_entries(hass, config_entry1.entry_id, _async_migrator)
    assert entries == {entry1.entity_id, entry2.entity_id}
    assert not entity_registry.async_is_registered(entry1.entity_id)
    entry2 = entity_registry.async_get(entry2.entity_id)
    assert entry2.original_name == "Entry 2 renamed"
    assert entity_registry.async_get(entry3.entity_id) is entry3


async def test_async_migrate_entry_delete_other(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
):
    """Test async_migrate_entry."""
    config_entry1 = MockConfigEntry(domain="test1")
    config_entry2 = MockConfigEntry(domain="test2")
    entry1 = entity_registry.async_get_or_create(
        "light", "hue", "1234", config_entry=config_entry1, original_name="Entry 1"
    )
    entry2 = entity_registry.async_get_or_create(
        "light", "hue", "5678", config_entry=config_entry1, original_name="Entry 2"
    )
    entity_registry.async_get_or_create(
        "light", "hue", "90AB", config_entry=config_entry2, original_name="Entry 3"
    )

    @callback
    def _async_migrator(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:
        entries.add(entity_entry.entity_id)
        if entity_entry == entry1:
            entity_registry.async_remove(entry2.entity_id)
            return None
        if entity_entry == entry2:
            # We should not get here
            pytest.fail()
        return None

    entries = set()
    await er.async_migrate_entries(hass, config_entry1.entry_id, _async_migrator)
    assert entries == {entry1.entity_id}
    assert not entity_registry.async_is_registered(entry2.entity_id)
