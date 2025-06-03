"""Tests for the floor registry."""

from datetime import datetime
from functools import partial
import re
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, floor_registry as fr
from homeassistant.util.dt import utcnow

from tests.common import async_capture_events, flush_store


async def test_list_floors(floor_registry: fr.FloorRegistry) -> None:
    """Make sure that we can read floors."""
    floors = floor_registry.async_list_floors()
    assert len(list(floors)) == len(floor_registry.floors)


@pytest.mark.usefixtures("freezer")
async def test_create_floor(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Make sure that we can create floors."""
    update_events = async_capture_events(hass, fr.EVENT_FLOOR_REGISTRY_UPDATED)
    floor = floor_registry.async_create(
        name="First floor",
        icon="mdi:home-floor-1",
        aliases={"first", "ground", "ground floor"},
        level=1,
    )

    assert floor == fr.FloorEntry(
        floor_id="first_floor",
        name="First floor",
        icon="mdi:home-floor-1",
        aliases={"first", "ground", "ground floor"},
        level=1,
        created_at=utcnow(),
        modified_at=utcnow(),
    )

    assert len(floor_registry.floors) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 1
    assert update_events[0].data == {
        "action": "create",
        "floor_id": floor.floor_id,
    }


async def test_create_floor_with_name_already_in_use(
    hass: HomeAssistant, floor_registry: fr.FloorRegistry
) -> None:
    """Make sure that we can't create a floor with a name already in use."""
    update_events = async_capture_events(hass, fr.EVENT_FLOOR_REGISTRY_UPDATED)
    floor_registry.async_create("First floor")

    with pytest.raises(
        ValueError,
        match=re.escape("The name First floor (firstfloor) is already in use"),
    ):
        floor_registry.async_create("First floor")

    await hass.async_block_till_done()

    assert len(floor_registry.floors) == 1
    assert len(update_events) == 1


async def test_create_floor_with_id_already_in_use(
    floor_registry: fr.FloorRegistry,
) -> None:
    """Make sure that we can't create an floor with an id already in use."""
    floor = floor_registry.async_create("First")

    updated_floor = floor_registry.async_update(floor.floor_id, name="Second")
    assert updated_floor.floor_id == floor.floor_id

    another_floor = floor_registry.async_create("First")
    assert floor.floor_id != another_floor.floor_id
    assert another_floor.floor_id == "first_2"


async def test_delete_floor(
    hass: HomeAssistant, floor_registry: fr.FloorRegistry
) -> None:
    """Make sure that we can delete a floor."""
    update_events = async_capture_events(hass, fr.EVENT_FLOOR_REGISTRY_UPDATED)
    floor = floor_registry.async_create("First floor")
    assert len(floor_registry.floors) == 1

    floor_registry.async_delete(floor.floor_id)

    assert not floor_registry.floors

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0].data == {
        "action": "create",
        "floor_id": floor.floor_id,
    }
    assert update_events[1].data == {
        "action": "remove",
        "floor_id": floor.floor_id,
    }


async def test_delete_non_existing_floor(floor_registry: fr.FloorRegistry) -> None:
    """Make sure that we can't delete a floor that doesn't exist."""
    floor_registry.async_create("First floor")

    with pytest.raises(KeyError):
        floor_registry.async_delete("")

    assert len(floor_registry.floors) == 1


async def test_update_floor(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Make sure that we can update floors."""
    created_at = datetime.fromisoformat("2024-01-01T01:00:00+00:00")
    freezer.move_to(created_at)

    update_events = async_capture_events(hass, fr.EVENT_FLOOR_REGISTRY_UPDATED)
    floor = floor_registry.async_create("First floor")

    assert floor == fr.FloorEntry(
        floor_id="first_floor",
        name="First floor",
        icon=None,
        aliases=set(),
        level=None,
        created_at=created_at,
        modified_at=created_at,
    )
    assert len(floor_registry.floors) == 1

    modified_at = datetime.fromisoformat("2024-02-01T01:00:00+00:00")
    freezer.move_to(modified_at)

    updated_floor = floor_registry.async_update(
        floor.floor_id,
        name="Second floor",
        icon="mdi:home-floor-2",
        aliases={"ground", "downstairs"},
        level=2,
    )

    assert updated_floor != floor
    assert updated_floor == fr.FloorEntry(
        floor_id="first_floor",
        name="Second floor",
        icon="mdi:home-floor-2",
        aliases={"ground", "downstairs"},
        level=2,
        created_at=created_at,
        modified_at=modified_at,
    )

    assert len(floor_registry.floors) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0].data == {
        "action": "create",
        "floor_id": floor.floor_id,
    }
    assert update_events[1].data == {
        "action": "update",
        "floor_id": floor.floor_id,
    }


async def test_update_floor_with_same_data(
    hass: HomeAssistant, floor_registry: fr.FloorRegistry
) -> None:
    """Make sure that we can reapply the same data to a floor and it won't update."""
    update_events = async_capture_events(hass, fr.EVENT_FLOOR_REGISTRY_UPDATED)
    floor = floor_registry.async_create(
        "First floor",
        icon="mdi:home-floor-1",
    )

    updated_floor = floor_registry.async_update(
        floor_id=floor.floor_id,
        name="First floor",
        icon="mdi:home-floor-1",
    )
    assert floor == updated_floor

    await hass.async_block_till_done()

    # No update event
    assert len(update_events) == 1
    assert update_events[0].data == {
        "action": "create",
        "floor_id": floor.floor_id,
    }


async def test_update_floor_with_same_name_change_case(
    floor_registry: fr.FloorRegistry,
) -> None:
    """Make sure that we can reapply the same name with a different case to a floor."""
    floor = floor_registry.async_create("first floor")

    updated_floor = floor_registry.async_update(floor.floor_id, name="First floor")

    assert updated_floor.floor_id == floor.floor_id
    assert updated_floor.name == "First floor"
    assert updated_floor.normalized_name == floor.normalized_name
    assert len(floor_registry.floors) == 1


async def test_update_floor_with_name_already_in_use(
    floor_registry: fr.FloorRegistry,
) -> None:
    """Make sure that we can't update a floor with a name already in use."""
    floor1 = floor_registry.async_create("First floor")
    floor2 = floor_registry.async_create("Second floor")

    with pytest.raises(
        ValueError,
        match=re.escape("The name Second floor (secondfloor) is already in use"),
    ):
        floor_registry.async_update(floor1.floor_id, name="Second floor")

    assert floor1.name == "First floor"
    assert floor2.name == "Second floor"
    assert len(floor_registry.floors) == 2


async def test_update_floor_with_normalized_name_already_in_use(
    floor_registry: fr.FloorRegistry,
) -> None:
    """Make sure that we can't update a floor with a normalized name already in use."""
    floor1 = floor_registry.async_create("first")
    floor2 = floor_registry.async_create("S E C O N D")

    with pytest.raises(
        ValueError, match=re.escape("The name second (second) is already in use")
    ):
        floor_registry.async_update(floor1.floor_id, name="second")

    assert floor1.name == "first"
    assert floor2.name == "S E C O N D"
    assert len(floor_registry.floors) == 2


async def test_load_floors(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Make sure that we can load/save data correctly."""
    floor1_created = datetime.fromisoformat("2024-01-01T00:00:00+00:00")
    freezer.move_to(floor1_created)
    floor1 = floor_registry.async_create(
        "First floor",
        icon="mdi:home-floor-1",
        aliases={"first", "ground"},
        level=1,
    )

    floor2_created = datetime.fromisoformat("2024-02-01T00:00:00+00:00")
    freezer.move_to(floor2_created)
    floor2 = floor_registry.async_create(
        "Second floor",
        icon="mdi:home-floor-2",
        aliases={"first", "ground"},
        level=2,
    )

    assert len(floor_registry.floors) == 2

    registry2 = fr.FloorRegistry(hass)
    await flush_store(floor_registry._store)
    await registry2.async_load()

    assert len(registry2.floors) == 2
    assert list(floor_registry.floors) == list(registry2.floors)

    floor1_registry2 = registry2.async_get_floor_by_name("First floor")
    assert floor1_registry2 == floor1

    floor2_registry2 = registry2.async_get_floor_by_name("Second floor")
    assert floor2_registry2 == floor2


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_floors_from_storage(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test loading stored floors on start."""
    hass_storage[fr.STORAGE_KEY] = {
        "version": fr.STORAGE_VERSION_MAJOR,
        "data": {
            "floors": [
                {
                    "icon": "mdi:home-floor-1",
                    "floor_id": "first_floor",
                    "name": "First floor",
                    "aliases": ["first", "ground"],
                    "level": 1,
                }
            ]
        },
    }

    await fr.async_load(hass)
    registry = fr.async_get(hass)

    assert len(registry.floors) == 1


async def test_getting_floor_by_name(floor_registry: fr.FloorRegistry) -> None:
    """Make sure we can get the floors by name."""
    floor = floor_registry.async_create("First floor")
    floor2 = floor_registry.async_get_floor_by_name("first floor")
    floor3 = floor_registry.async_get_floor_by_name("first    floor")

    assert floor == floor2
    assert floor == floor3
    assert floor2 == floor3

    get_floor = floor_registry.async_get_floor(floor.floor_id)
    assert get_floor == floor


async def test_async_get_floors_by_alias(
    floor_registry: fr.FloorRegistry,
) -> None:
    """Make sure we can get the floors by alias."""
    floor1 = floor_registry.async_create("First floor", aliases=("alias_1", "alias_2"))
    floor2 = floor_registry.async_create("Second floor", aliases=("alias_1", "alias_3"))

    alias1_list = floor_registry.async_get_floors_by_alias("A l i a s_1")
    alias2_list = floor_registry.async_get_floors_by_alias("A l i a s_2")
    alias3_list = floor_registry.async_get_floors_by_alias("A l i a s_3")

    assert len(alias1_list) == 2
    assert len(alias2_list) == 1
    assert len(alias3_list) == 1

    assert floor1 in alias1_list
    assert floor1 in alias2_list
    assert floor2 in alias1_list
    assert floor2 in alias3_list


async def test_async_get_floor_by_name_not_found(
    floor_registry: fr.FloorRegistry,
) -> None:
    """Make sure we return None for non-existent floors."""
    floor_registry.async_create("First floor")

    assert len(floor_registry.floors) == 1

    assert floor_registry.async_get_floor_by_name("non_exist") is None


async def test_floor_removed_from_areas(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test if floor gets removed from areas when the floor is removed."""

    floor = floor_registry.async_create("First floor")
    assert len(floor_registry.floors) == 1

    entry = area_registry.async_create(name="Kitchen")
    area_registry.async_update(entry.id, floor_id=floor.floor_id)

    entries = ar.async_entries_for_floor(area_registry, floor.floor_id)
    assert len(entries) == 1

    floor_registry.async_delete(floor.floor_id)
    await hass.async_block_till_done()

    entries = ar.async_entries_for_floor(area_registry, floor.floor_id)
    assert len(entries) == 0


async def test_async_create_thread_safety(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test async_create raises when called from wrong thread."""
    with pytest.raises(
        RuntimeError,
        match="Detected code that calls floor_registry.async_create from a thread.",
    ):
        await hass.async_add_executor_job(floor_registry.async_create, "any")


async def test_async_delete_thread_safety(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test async_delete raises when called from wrong thread."""
    any_floor = floor_registry.async_create("any")

    with pytest.raises(
        RuntimeError,
        match="Detected code that calls floor_registry.async_delete from a thread.",
    ):
        await hass.async_add_executor_job(floor_registry.async_delete, any_floor)


async def test_async_update_thread_safety(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test async_update raises when called from wrong thread."""
    any_floor = floor_registry.async_create("any")

    with pytest.raises(
        RuntimeError,
        match="Detected code that calls floor_registry.async_update from a thread.",
    ):
        await hass.async_add_executor_job(
            partial(floor_registry.async_update, any_floor.floor_id, name="new name")
        )


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_from_1_1(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test migration from version 1.1."""
    hass_storage[fr.STORAGE_KEY] = {
        "version": 1,
        "data": {
            "floors": [
                {
                    "floor_id": "12345A",
                    "name": "mock",
                    "aliases": [],
                    "icon": None,
                    "level": None,
                }
            ]
        },
    }

    await fr.async_load(hass)
    registry = fr.async_get(hass)

    # Test data was loaded
    entry = registry.async_get_floor_by_name("mock")
    assert entry.floor_id == "12345A"

    # Check we store migrated data
    await flush_store(registry._store)
    assert hass_storage[fr.STORAGE_KEY] == {
        "version": fr.STORAGE_VERSION_MAJOR,
        "minor_version": fr.STORAGE_VERSION_MINOR,
        "key": fr.STORAGE_KEY,
        "data": {
            "floors": [
                {
                    "aliases": [],
                    "icon": None,
                    "floor_id": "12345A",
                    "level": None,
                    "name": "mock",
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "modified_at": "1970-01-01T00:00:00+00:00",
                }
            ]
        },
    }
