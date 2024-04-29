"""Tests for the Area Registry."""

from functools import partial
from typing import Any

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    floor_registry as fr,
    label_registry as lr,
)

from tests.common import ANY, async_capture_events, flush_store


async def test_list_areas(area_registry: ar.AreaRegistry) -> None:
    """Make sure that we can read areas."""
    area_registry.async_create("mock")

    areas = area_registry.async_list_areas()

    assert len(areas) == len(area_registry.areas)


async def test_create_area(hass: HomeAssistant, area_registry: ar.AreaRegistry) -> None:
    """Make sure that we can create an area."""
    update_events = async_capture_events(hass, ar.EVENT_AREA_REGISTRY_UPDATED)

    # Create area with only mandatory parameters
    area = area_registry.async_create("mock")

    assert area == ar.AreaEntry(
        aliases=set(),
        floor_id=None,
        icon=None,
        id=ANY,
        labels=set(),
        name="mock",
        normalized_name=ANY,
        picture=None,
    )
    assert len(area_registry.areas) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 1
    assert update_events[-1].data == {
        "action": "create",
        "area_id": area.id,
    }

    # Create area with all parameters
    area = area_registry.async_create(
        "mock 2",
        aliases={"alias_1", "alias_2"},
        labels={"label1", "label2"},
        picture="/image/example.png",
    )

    assert area == ar.AreaEntry(
        aliases={"alias_1", "alias_2"},
        floor_id=None,
        icon=None,
        id=ANY,
        labels={"label1", "label2"},
        name="mock 2",
        normalized_name=ANY,
        picture="/image/example.png",
    )
    assert len(area_registry.areas) == 2

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[-1].data == {
        "action": "create",
        "area_id": area.id,
    }


async def test_create_area_with_name_already_in_use(
    hass: HomeAssistant, area_registry: ar.AreaRegistry
) -> None:
    """Make sure that we can't create an area with a name already in use."""
    update_events = async_capture_events(hass, ar.EVENT_AREA_REGISTRY_UPDATED)
    area1 = area_registry.async_create("mock")

    with pytest.raises(ValueError) as e_info:
        area2 = area_registry.async_create("mock")
        assert area1 != area2
        assert e_info == "The name mock 2 (mock2) is already in use"

    await hass.async_block_till_done()

    assert len(area_registry.areas) == 1
    assert len(update_events) == 1


async def test_create_area_with_id_already_in_use(
    area_registry: ar.AreaRegistry,
) -> None:
    """Make sure that we can't create an area with a name already in use."""
    area1 = area_registry.async_create("mock")

    updated_area1 = area_registry.async_update(area1.id, name="New Name")
    assert updated_area1.id == area1.id

    area2 = area_registry.async_create("mock")
    assert area2.id == "mock_2"


async def test_delete_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
) -> None:
    """Make sure that we can delete an area."""
    update_events = async_capture_events(hass, ar.EVENT_AREA_REGISTRY_UPDATED)
    area = area_registry.async_create("mock")

    area_registry.async_delete(area.id)

    assert not area_registry.areas

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0].data == {
        "action": "create",
        "area_id": area.id,
    }
    assert update_events[1].data == {
        "action": "remove",
        "area_id": area.id,
    }


async def test_delete_non_existing_area(area_registry: ar.AreaRegistry) -> None:
    """Make sure that we can't delete an area that doesn't exist."""
    area_registry.async_create("mock")

    with pytest.raises(KeyError):
        await area_registry.async_delete("")

    assert len(area_registry.areas) == 1


async def test_update_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Make sure that we can read areas."""
    update_events = async_capture_events(hass, ar.EVENT_AREA_REGISTRY_UPDATED)
    floor_registry.async_create("first")
    area = area_registry.async_create("mock")

    updated_area = area_registry.async_update(
        area.id,
        aliases={"alias_1", "alias_2"},
        floor_id="first",
        icon="mdi:garage",
        labels={"label1", "label2"},
        name="mock1",
        picture="/image/example.png",
    )

    assert updated_area != area
    assert updated_area == ar.AreaEntry(
        aliases={"alias_1", "alias_2"},
        floor_id="first",
        icon="mdi:garage",
        id=ANY,
        labels={"label1", "label2"},
        name="mock1",
        normalized_name=ANY,
        picture="/image/example.png",
    )
    assert len(area_registry.areas) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0].data == {
        "action": "create",
        "area_id": area.id,
    }
    assert update_events[1].data == {
        "action": "update",
        "area_id": area.id,
    }


async def test_update_area_with_same_name(area_registry: ar.AreaRegistry) -> None:
    """Make sure that we can reapply the same name to the area."""
    area = area_registry.async_create("mock")

    updated_area = area_registry.async_update(area.id, name="mock")

    assert updated_area == area
    assert len(area_registry.areas) == 1


async def test_update_area_with_same_name_change_case(
    area_registry: ar.AreaRegistry,
) -> None:
    """Make sure that we can reapply the same name with a different case to the area."""
    area = area_registry.async_create("mock")

    updated_area = area_registry.async_update(area.id, name="Mock")

    assert updated_area.name == "Mock"
    assert updated_area.id == area.id
    assert updated_area.normalized_name == area.normalized_name
    assert len(area_registry.areas) == 1


async def test_update_area_with_name_already_in_use(
    area_registry: ar.AreaRegistry,
) -> None:
    """Make sure that we can't update an area with a name already in use."""
    area1 = area_registry.async_create("mock1")
    area2 = area_registry.async_create("mock2")

    with pytest.raises(ValueError) as e_info:
        area_registry.async_update(area1.id, name="mock2")
        assert e_info == "The name mock 2 (mock2) is already in use"

    assert area1.name == "mock1"
    assert area2.name == "mock2"
    assert len(area_registry.areas) == 2


async def test_update_area_with_normalized_name_already_in_use(
    area_registry: ar.AreaRegistry,
) -> None:
    """Make sure that we can't update an area with a normalized name already in use."""
    area1 = area_registry.async_create("mock1")
    area2 = area_registry.async_create("Moc k2")

    with pytest.raises(ValueError) as e_info:
        area_registry.async_update(area1.id, name="mock2")
        assert e_info == "The name mock 2 (mock2) is already in use"

    assert area1.name == "mock1"
    assert area2.name == "Moc k2"
    assert len(area_registry.areas) == 2


async def test_load_area(hass: HomeAssistant, area_registry: ar.AreaRegistry) -> None:
    """Make sure that we can load/save data correctly."""
    area1 = area_registry.async_create("mock1")
    area2 = area_registry.async_create("mock2")

    assert len(area_registry.areas) == 2

    registry2 = ar.AreaRegistry(hass)
    await flush_store(area_registry._store)
    await registry2.async_load()

    assert list(area_registry.areas) == list(registry2.areas)

    area1_registry2 = registry2.async_get_or_create("mock1")
    assert area1_registry2.id == area1.id
    area2_registry2 = registry2.async_get_or_create("mock2")
    assert area2_registry2.id == area2.id


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_area_from_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading stored areas on start."""
    hass_storage[ar.STORAGE_KEY] = {
        "version": ar.STORAGE_VERSION_MAJOR,
        "minor_version": ar.STORAGE_VERSION_MINOR,
        "data": {
            "areas": [
                {
                    "aliases": ["alias_1", "alias_2"],
                    "floor_id": "first_floor",
                    "id": "12345A",
                    "icon": "mdi:garage",
                    "labels": ["mock-label1", "mock-label2"],
                    "name": "mock",
                    "picture": "blah",
                }
            ]
        },
    }

    await ar.async_load(hass)
    registry = ar.async_get(hass)

    assert len(registry.areas) == 1


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_from_1_1(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test migration from version 1.1."""
    hass_storage[ar.STORAGE_KEY] = {
        "version": 1,
        "data": {"areas": [{"id": "12345A", "name": "mock"}]},
    }

    await ar.async_load(hass)
    registry = ar.async_get(hass)

    # Test data was loaded
    entry = registry.async_get_or_create("mock")
    assert entry.id == "12345A"

    # Check we store migrated data
    await flush_store(registry._store)
    assert hass_storage[ar.STORAGE_KEY] == {
        "version": ar.STORAGE_VERSION_MAJOR,
        "minor_version": ar.STORAGE_VERSION_MINOR,
        "key": ar.STORAGE_KEY,
        "data": {
            "areas": [
                {
                    "aliases": [],
                    "floor_id": None,
                    "icon": None,
                    "id": "12345A",
                    "labels": [],
                    "name": "mock",
                    "picture": None,
                }
            ]
        },
    }


async def test_async_get_or_create(area_registry: ar.AreaRegistry) -> None:
    """Make sure we can get the area by name."""
    area = area_registry.async_get_or_create("Mock1")
    area2 = area_registry.async_get_or_create("mock1")
    area3 = area_registry.async_get_or_create("mock   1")

    assert area == area2
    assert area == area3
    assert area2 == area3


async def test_async_get_area_by_name(area_registry: ar.AreaRegistry) -> None:
    """Make sure we can get the area by name."""
    area_registry.async_create("Mock1")

    assert len(area_registry.areas) == 1

    assert area_registry.async_get_area_by_name("M o c k 1").normalized_name == "mock1"


async def test_async_get_area_by_name_not_found(area_registry: ar.AreaRegistry) -> None:
    """Make sure we return None for non-existent areas."""
    area_registry.async_create("Mock1")

    assert len(area_registry.areas) == 1

    assert area_registry.async_get_area_by_name("non_exist") is None


async def test_async_get_area(area_registry: ar.AreaRegistry) -> None:
    """Make sure we can get the area by id."""
    area = area_registry.async_create("Mock1")

    assert len(area_registry.areas) == 1

    assert area_registry.async_get_area(area.id).normalized_name == "mock1"


async def test_removing_floors(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Make sure we can clear floors."""
    first_floor = floor_registry.async_create("First floor")
    second_floor = floor_registry.async_create("Second floor")

    kitchen = area_registry.async_create("Kitchen")
    kitchen = area_registry.async_update(kitchen.id, floor_id=first_floor.floor_id)
    bedroom = area_registry.async_create("Bedroom")
    bedroom = area_registry.async_update(bedroom.id, floor_id=second_floor.floor_id)

    floor_registry.async_delete(first_floor.floor_id)
    await hass.async_block_till_done()
    assert area_registry.async_get_area(kitchen.id).floor_id is None
    assert area_registry.async_get_area(bedroom.id).floor_id == second_floor.floor_id

    floor_registry.async_delete(second_floor.floor_id)
    await hass.async_block_till_done()
    assert area_registry.async_get_area(kitchen.id).floor_id is None
    assert area_registry.async_get_area(bedroom.id).floor_id is None


@pytest.mark.usefixtures("hass")
async def test_entries_for_floor(
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test getting area entries by floor."""
    first_floor = floor_registry.async_create("First floor")
    second_floor = floor_registry.async_create("Second floor")

    kitchen = area_registry.async_create("Kitchen")
    kitchen = area_registry.async_update(kitchen.id, floor_id=first_floor.floor_id)
    living_room = area_registry.async_create("Living room")
    living_room = area_registry.async_update(
        living_room.id, floor_id=first_floor.floor_id
    )
    bedroom = area_registry.async_create("Bedroom")
    bedroom = area_registry.async_update(bedroom.id, floor_id=second_floor.floor_id)

    entries = ar.async_entries_for_floor(area_registry, first_floor.floor_id)
    assert len(entries) == 2
    assert entries == [kitchen, living_room]

    entries = ar.async_entries_for_floor(area_registry, second_floor.floor_id)
    assert len(entries) == 1
    assert entries == [bedroom]

    assert not ar.async_entries_for_floor(area_registry, "unknown")
    assert not ar.async_entries_for_floor(area_registry, "")


async def test_removing_labels(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Make sure we can clear labels."""
    label1 = label_registry.async_create("Label 1")
    label2 = label_registry.async_create("Label 2")

    kitchen = area_registry.async_create("Kitchen")
    kitchen = area_registry.async_update(
        kitchen.id, labels={label1.label_id, label2.label_id}
    )

    bedroom = area_registry.async_create("Bedroom")
    bedroom = area_registry.async_update(bedroom.id, labels={label2.label_id})

    assert area_registry.async_get_area(kitchen.id).labels == {
        label1.label_id,
        label2.label_id,
    }
    assert area_registry.async_get_area(bedroom.id).labels == {label2.label_id}

    label_registry.async_delete(label1.label_id)
    await hass.async_block_till_done()

    assert area_registry.async_get_area(kitchen.id).labels == {label2.label_id}
    assert area_registry.async_get_area(bedroom.id).labels == {label2.label_id}

    label_registry.async_delete(label2.label_id)
    await hass.async_block_till_done()

    assert not area_registry.async_get_area(kitchen.id).labels
    assert not area_registry.async_get_area(bedroom.id).labels


@pytest.mark.usefixtures("hass")
async def test_entries_for_label(
    area_registry: ar.AreaRegistry, label_registry: lr.LabelRegistry
) -> None:
    """Test getting area entries by label."""
    label1 = label_registry.async_create("Label 1")
    label2 = label_registry.async_create("Label 2")

    kitchen = area_registry.async_create("Kitchen")
    kitchen = area_registry.async_update(
        kitchen.id, labels={label1.label_id, label2.label_id}
    )
    living_room = area_registry.async_create("Living room")
    living_room = area_registry.async_update(living_room.id, labels={label1.label_id})
    bedroom = area_registry.async_create("Bedroom")
    bedroom = area_registry.async_update(bedroom.id, labels={label2.label_id})

    entries = ar.async_entries_for_label(area_registry, label1.label_id)
    assert len(entries) == 2
    assert entries == [kitchen, living_room]

    entries = ar.async_entries_for_label(area_registry, label2.label_id)
    assert len(entries) == 2
    assert entries == [kitchen, bedroom]

    assert not ar.async_entries_for_label(area_registry, "unknown")
    assert not ar.async_entries_for_label(area_registry, "")


async def test_async_get_or_create_thread_checks(
    hass: HomeAssistant, area_registry: ar.AreaRegistry
) -> None:
    """We raise when trying to create in the wrong thread."""
    with pytest.raises(
        RuntimeError,
        match="Detected code that calls async_create from a thread. Please report this issue.",
    ):
        await hass.async_add_executor_job(area_registry.async_create, "Mock1")


async def test_async_update_thread_checks(
    hass: HomeAssistant, area_registry: ar.AreaRegistry
) -> None:
    """We raise when trying to update in the wrong thread."""
    area = area_registry.async_create("Mock1")
    with pytest.raises(
        RuntimeError,
        match="Detected code that calls _async_update from a thread. Please report this issue.",
    ):
        await hass.async_add_executor_job(
            partial(area_registry.async_update, area.id, name="Mock2")
        )


async def test_async_delete_thread_checks(
    hass: HomeAssistant, area_registry: ar.AreaRegistry
) -> None:
    """We raise when trying to delete in the wrong thread."""
    area = area_registry.async_create("Mock1")
    with pytest.raises(
        RuntimeError,
        match="Detected code that calls async_delete from a thread. Please report this issue.",
    ):
        await hass.async_add_executor_job(area_registry.async_delete, area.id)
