"""Tests for the Label Registry."""

from datetime import datetime
from functools import partial
import re
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
)
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_capture_events, flush_store


async def test_list_labels(label_registry: lr.LabelRegistry) -> None:
    """Make sure that we can read label."""
    labels = label_registry.async_list_labels()
    assert len(list(labels)) == len(label_registry.labels)


@pytest.mark.usefixtures("freezer")
async def test_create_label(
    hass: HomeAssistant, label_registry: lr.LabelRegistry
) -> None:
    """Make sure that we can create labels."""
    update_events = async_capture_events(hass, lr.EVENT_LABEL_REGISTRY_UPDATED)
    label = label_registry.async_create(
        name="My Label",
        color="#FF0000",
        icon="mdi:test",
        description="This label is for testing",
    )

    assert label == lr.LabelEntry(
        label_id="my_label",
        name="My Label",
        color="#FF0000",
        icon="mdi:test",
        description="This label is for testing",
        created_at=utcnow(),
        modified_at=utcnow(),
    )

    assert len(label_registry.labels) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 1
    assert update_events[0].data == {
        "action": "create",
        "label_id": label.label_id,
    }


async def test_create_label_with_name_already_in_use(
    hass: HomeAssistant, label_registry: lr.LabelRegistry
) -> None:
    """Make sure that we can't create a label with a ID already in use."""
    update_events = async_capture_events(hass, lr.EVENT_LABEL_REGISTRY_UPDATED)
    label_registry.async_create("mock")

    with pytest.raises(
        ValueError, match=re.escape("The name mock (mock) is already in use")
    ):
        label_registry.async_create("mock")

    await hass.async_block_till_done()

    assert len(label_registry.labels) == 1
    assert len(update_events) == 1


async def test_create_label_with_id_already_in_use(
    label_registry: lr.LabelRegistry,
) -> None:
    """Make sure that we can't create a label with a name already in use."""
    label = label_registry.async_create("Label")

    updated_label = label_registry.async_update(label.label_id, name="Renamed Label")
    assert updated_label.label_id == label.label_id

    second_label = label_registry.async_create("Label")
    assert label.label_id != second_label.label_id
    assert second_label.label_id == "label_2"


async def test_delete_label(
    hass: HomeAssistant, label_registry: lr.LabelRegistry
) -> None:
    """Make sure that we can delete a label."""
    update_events = async_capture_events(hass, lr.EVENT_LABEL_REGISTRY_UPDATED)
    label = label_registry.async_create("Label")
    assert len(label_registry.labels) == 1

    label_registry.async_delete(label.label_id)

    assert not label_registry.labels

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0].data == {
        "action": "create",
        "label_id": label.label_id,
    }
    assert update_events[1].data == {
        "action": "remove",
        "label_id": label.label_id,
    }


async def test_delete_non_existing_label(label_registry: lr.LabelRegistry) -> None:
    """Make sure that we can't delete a label that doesn't exist."""
    label_registry.async_create("mock")

    with pytest.raises(KeyError):
        label_registry.async_delete("")

    assert len(label_registry.labels) == 1


async def test_update_label(
    hass: HomeAssistant,
    label_registry: lr.LabelRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Make sure that we can update labels."""
    created_at = datetime.fromisoformat("2024-01-01T01:00:00+00:00")
    freezer.move_to(created_at)
    update_events = async_capture_events(hass, lr.EVENT_LABEL_REGISTRY_UPDATED)
    label = label_registry.async_create("Mock")

    assert len(label_registry.labels) == 1
    assert label == lr.LabelEntry(
        label_id="mock",
        name="Mock",
        color=None,
        icon=None,
        description=None,
        created_at=created_at,
        modified_at=created_at,
    )

    modified_at = datetime.fromisoformat("2024-02-01T01:00:00+00:00")
    freezer.move_to(modified_at)
    updated_label = label_registry.async_update(
        label.label_id,
        name="Updated",
        color="#FFFFFF",
        icon="mdi:update",
        description="Updated description",
    )

    assert updated_label != label
    assert updated_label == lr.LabelEntry(
        label_id="mock",
        name="Updated",
        color="#FFFFFF",
        icon="mdi:update",
        description="Updated description",
        created_at=created_at,
        modified_at=modified_at,
    )
    assert len(label_registry.labels) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0].data == {
        "action": "create",
        "label_id": label.label_id,
    }
    assert update_events[1].data == {
        "action": "update",
        "label_id": label.label_id,
    }


async def test_update_label_with_same_data(
    hass: HomeAssistant, label_registry: lr.LabelRegistry
) -> None:
    """Make sure that we can reapply the same data to the label and it won't update."""
    update_events = async_capture_events(hass, lr.EVENT_LABEL_REGISTRY_UPDATED)
    label = label_registry.async_create(
        "mock",
        color="#FFFFFF",
        icon="mdi:test",
        description="Description",
    )

    udpated_label = label_registry.async_update(
        label_id=label.label_id,
        name="mock",
        color="#FFFFFF",
        icon="mdi:test",
        description="Description",
    )
    assert label == udpated_label

    await hass.async_block_till_done()

    # No update event
    assert len(update_events) == 1
    assert update_events[0].data == {
        "action": "create",
        "label_id": label.label_id,
    }


async def test_update_label_with_same_name_change_case(
    label_registry: lr.LabelRegistry,
) -> None:
    """Make sure that we can reapply the same name with a different case to the label."""
    label = label_registry.async_create("mock")

    updated_label = label_registry.async_update(label.label_id, name="Mock")

    assert updated_label.name == "Mock"
    assert updated_label.label_id == label.label_id
    assert updated_label.normalized_name == label.normalized_name
    assert len(label_registry.labels) == 1


async def test_update_label_with_name_already_in_use(
    label_registry: lr.LabelRegistry,
) -> None:
    """Make sure that we can't update a label with a name already in use."""
    label1 = label_registry.async_create("mock1")
    label2 = label_registry.async_create("mock2")

    with pytest.raises(
        ValueError, match=re.escape("The name mock2 (mock2) is already in use")
    ):
        label_registry.async_update(label1.label_id, name="mock2")

    assert label1.name == "mock1"
    assert label2.name == "mock2"
    assert len(label_registry.labels) == 2


async def test_update_label_with_normalized_name_already_in_use(
    label_registry: lr.LabelRegistry,
) -> None:
    """Make sure that we can't update a label with a normalized name already in use."""
    label1 = label_registry.async_create("mock1")
    label2 = label_registry.async_create("M O C K 2")

    with pytest.raises(
        ValueError, match=re.escape("The name mock2 (mock2) is already in use")
    ):
        label_registry.async_update(label1.label_id, name="mock2")

    assert label1.name == "mock1"
    assert label2.name == "M O C K 2"
    assert len(label_registry.labels) == 2


async def test_load_labels(
    hass: HomeAssistant,
    label_registry: lr.LabelRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Make sure that we can load/save data correctly."""
    label1_created = datetime.fromisoformat("2024-01-01T00:00:00+00:00")
    freezer.move_to(label1_created)
    label1 = label_registry.async_create(
        "Label One",
        color="#FF000",
        icon="mdi:one",
        description="This label is label one",
    )
    label2_created = datetime.fromisoformat("2024-02-01T00:00:00+00:00")
    freezer.move_to(label2_created)
    label2 = label_registry.async_create(
        "Label Two",
        color="#000FF",
        icon="mdi:two",
        description="This label is label two",
    )

    assert len(label_registry.labels) == 2

    registry2 = lr.LabelRegistry(hass)
    await flush_store(label_registry._store)
    await registry2.async_load()

    assert len(registry2.labels) == 2
    assert list(label_registry.labels) == list(registry2.labels)

    label1_registry2 = registry2.async_get_label_by_name("Label One")
    assert label1_registry2 == label1

    label2_registry2 = registry2.async_get_label_by_name("Label Two")
    assert label2_registry2 == label2


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_label_from_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading stored labels on start."""
    hass_storage[lr.STORAGE_KEY] = {
        "version": lr.STORAGE_VERSION_MAJOR,
        "data": {
            "labels": [
                {
                    "color": "#FFFFFF",
                    "description": None,
                    "icon": "mdi:test",
                    "label_id": "one",
                    "name": "One",
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "modified_at": "2024-02-01T00:00:00+00:00",
                }
            ]
        },
    }

    await lr.async_load(hass)
    registry = lr.async_get(hass)

    assert len(registry.labels) == 1


async def test_getting_label(label_registry: lr.LabelRegistry) -> None:
    """Make sure we can get the labels by name."""
    label = label_registry.async_create("Mock1")
    label2 = label_registry.async_get_label_by_name("mock1")
    label3 = label_registry.async_get_label_by_name("mock   1")

    assert label == label2
    assert label == label3
    assert label2 == label3

    get_label = label_registry.async_get_label(label.label_id)
    assert get_label == label


async def test_async_get_label_by_name_not_found(
    label_registry: lr.LabelRegistry,
) -> None:
    """Make sure we return None for non-existent labels."""
    label_registry.async_create("Mock1")

    assert len(label_registry.labels) == 1

    assert label_registry.async_get_label_by_name("non_exist") is None


async def test_labels_removed_from_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test if label gets removed from devices when the label is removed."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)

    label1 = label_registry.async_create("label1")
    label2 = label_registry.async_create("label2")
    assert len(label_registry.labels) == 2

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:23")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    device_registry.async_update_device(entry.id, labels={label1.label_id})
    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:56")},
        identifiers={("bridgeid", "0456")},
        manufacturer="manufacturer",
        model="model",
    )
    device_registry.async_update_device(entry.id, labels={label2.label_id})
    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:89")},
        identifiers={("bridgeid", "0789")},
        manufacturer="manufacturer",
        model="model",
    )
    device_registry.async_update_device(
        entry.id, labels={label1.label_id, label2.label_id}
    )

    entries = dr.async_entries_for_label(device_registry, label1.label_id)
    assert len(entries) == 2
    entries = dr.async_entries_for_label(device_registry, label2.label_id)
    assert len(entries) == 2

    label_registry.async_delete(label1.label_id)
    await hass.async_block_till_done()

    entries = dr.async_entries_for_label(device_registry, label1.label_id)
    assert len(entries) == 0
    entries = dr.async_entries_for_label(device_registry, label2.label_id)
    assert len(entries) == 2

    label_registry.async_delete(label2.label_id)
    await hass.async_block_till_done()

    entries = dr.async_entries_for_label(device_registry, label1.label_id)
    assert len(entries) == 0
    entries = dr.async_entries_for_label(device_registry, label2.label_id)
    assert len(entries) == 0


async def test_labels_removed_from_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test if label gets removed from entity when the label is removed."""
    label1 = label_registry.async_create("label1")
    label2 = label_registry.async_create("label2")
    assert len(label_registry.labels) == 2

    entry = entity_registry.async_get_or_create(
        domain="light",
        platform="hue",
        unique_id="123",
    )
    entity_registry.async_update_entity(entry.entity_id, labels={label1.label_id})
    entry = entity_registry.async_get_or_create(
        domain="light",
        platform="hue",
        unique_id="456",
    )
    entity_registry.async_update_entity(entry.entity_id, labels={label2.label_id})
    entry = entity_registry.async_get_or_create(
        domain="light",
        platform="hue",
        unique_id="789",
    )
    entity_registry.async_update_entity(
        entry.entity_id, labels={label1.label_id, label2.label_id}
    )

    entries = er.async_entries_for_label(entity_registry, label1.label_id)
    assert len(entries) == 2
    entries = er.async_entries_for_label(entity_registry, label2.label_id)
    assert len(entries) == 2

    label_registry.async_delete(label1.label_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_label(entity_registry, label1.label_id)
    assert len(entries) == 0
    entries = er.async_entries_for_label(entity_registry, label2.label_id)
    assert len(entries) == 2

    label_registry.async_delete(label2.label_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_label(entity_registry, label1.label_id)
    assert len(entries) == 0
    entries = er.async_entries_for_label(entity_registry, label2.label_id)
    assert len(entries) == 0


async def test_async_create_thread_safety(
    hass: HomeAssistant,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test async_create raises when called from wrong thread."""
    with pytest.raises(
        RuntimeError,
        match="Detected code that calls label_registry.async_create from a thread.",
    ):
        await hass.async_add_executor_job(label_registry.async_create, "any")


async def test_async_delete_thread_safety(
    hass: HomeAssistant,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test async_delete raises when called from wrong thread."""
    any_label = label_registry.async_create("any")

    with pytest.raises(
        RuntimeError,
        match="Detected code that calls label_registry.async_delete from a thread.",
    ):
        await hass.async_add_executor_job(label_registry.async_delete, any_label)


async def test_async_update_thread_safety(
    hass: HomeAssistant,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test async_update raises when called from wrong thread."""
    any_label = label_registry.async_create("any")

    with pytest.raises(
        RuntimeError,
        match="Detected code that calls label_registry.async_update from a thread.",
    ):
        await hass.async_add_executor_job(
            partial(label_registry.async_update, any_label.label_id, name="new name")
        )


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_from_1_1(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test migration from version 1.1."""
    hass_storage[lr.STORAGE_KEY] = {
        "version": 1,
        "data": {
            "labels": [
                {
                    "color": None,
                    "description": None,
                    "icon": None,
                    "label_id": "12345A",
                    "name": "mock",
                }
            ]
        },
    }

    await lr.async_load(hass)
    registry = lr.async_get(hass)

    # Test data was loaded
    entry = registry.async_get_label_by_name("mock")
    assert entry.label_id == "12345A"

    # Check we store migrated data
    await flush_store(registry._store)
    assert hass_storage[lr.STORAGE_KEY] == {
        "version": lr.STORAGE_VERSION_MAJOR,
        "minor_version": lr.STORAGE_VERSION_MINOR,
        "key": lr.STORAGE_KEY,
        "data": {
            "labels": [
                {
                    "color": None,
                    "description": None,
                    "icon": None,
                    "label_id": "12345A",
                    "name": "mock",
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "modified_at": "1970-01-01T00:00:00+00:00",
                }
            ]
        },
    }
