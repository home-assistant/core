"""Tests for the floor registry."""

import re
from typing import Any

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, floor_registry as fr
from homeassistant.helpers.floor_registry import (
    EVENT_FLOOR_REGISTRY_UPDATED,
    STORAGE_KEY,
    STORAGE_VERSION_MAJOR,
    FloorRegistry,
    async_get,
    async_load,
)

from tests.common import async_capture_events, flush_store


async def test_list_floors(floor_registry: fr.FloorRegistry) -> None:
    """Make sure that we can read floors."""
    floors = floor_registry.async_list_floors()
    assert len(list(floors)) == len(floor_registry.floors)


async def test_create_floor(
    hass: HomeAssistant, floor_registry: fr.FloorRegistry
) -> None:
    """Make sure that we can create floors."""
    update_events = async_capture_events(hass, EVENT_FLOOR_REGISTRY_UPDATED)
    floor = floor_registry.async_create(
        name="First floor",
        icon="mdi:home-floor-1",
        aliases={"first", "ground", "ground floor"},
        level=1,
    )

    assert floor.floor_id == "first_floor"
    assert floor.name == "First floor"
    assert floor.icon == "mdi:home-floor-1"
    assert floor.aliases == {"first", "ground", "ground floor"}
    assert floor.level == 1

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
    update_events = async_capture_events(hass, EVENT_FLOOR_REGISTRY_UPDATED)
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
    hass: HomeAssistant, floor_registry: fr.FloorRegistry
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
    update_events = async_capture_events(hass, EVENT_FLOOR_REGISTRY_UPDATED)
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
    hass: HomeAssistant, floor_registry: fr.FloorRegistry
) -> None:
    """Make sure that we can update floors."""
    update_events = async_capture_events(hass, EVENT_FLOOR_REGISTRY_UPDATED)
    floor = floor_registry.async_create("First floor")

    assert len(floor_registry.floors) == 1
    assert floor.floor_id == "first_floor"
    assert floor.name == "First floor"
    assert floor.icon is None
    assert floor.aliases == set()
    assert floor.level is None

    updated_floor = floor_registry.async_update(
        floor.floor_id,
        name="Second floor",
        icon="mdi:home-floor-2",
        aliases={"ground", "downstairs"},
        level=2,
    )

    assert updated_floor != floor
    assert updated_floor.floor_id == "first_floor"
    assert updated_floor.name == "Second floor"
    assert updated_floor.icon == "mdi:home-floor-2"
    assert updated_floor.aliases == {"ground", "downstairs"}
    assert updated_floor.level == 2

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
    update_events = async_capture_events(hass, EVENT_FLOOR_REGISTRY_UPDATED)
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
    hass: HomeAssistant, floor_registry: fr.FloorRegistry
) -> None:
    """Make sure that we can load/save data correctly."""
    floor1 = floor_registry.async_create(
        "First floor",
        icon="mdi:home-floor-1",
        aliases={"first", "ground"},
        level=1,
    )
    floor2 = floor_registry.async_create(
        "Second floor",
        icon="mdi:home-floor-2",
        aliases={"first", "ground"},
        level=2,
    )

    assert len(floor_registry.floors) == 2

    registry2 = FloorRegistry(hass)
    await flush_store(floor_registry._store)
    await registry2.async_load()

    assert len(registry2.floors) == 2
    assert list(floor_registry.floors) == list(registry2.floors)

    floor1_registry2 = registry2.async_get_floor_by_name("First floor")
    assert floor1_registry2.floor_id == floor1.floor_id
    assert floor1_registry2.name == floor1.name
    assert floor1_registry2.icon == floor1.icon
    assert floor1_registry2.aliases == floor1.aliases
    assert floor1_registry2.level == floor1.level
    assert floor1_registry2.normalized_name == floor1.normalized_name

    floor2_registry2 = registry2.async_get_floor_by_name("Second floor")
    assert floor2_registry2.floor_id == floor2.floor_id
    assert floor2_registry2.name == floor2.name
    assert floor2_registry2.icon == floor2.icon
    assert floor2_registry2.aliases == floor2.aliases
    assert floor2_registry2.level == floor2.level
    assert floor2_registry2.normalized_name == floor2.normalized_name


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_floors_from_storage(
    hass: HomeAssistant, hass_storage: Any
) -> None:
    """Test loading stored floors on start."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION_MAJOR,
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

    await async_load(hass)
    registry = async_get(hass)

    assert len(registry.floors) == 1


async def test_getting_floor(floor_registry: fr.FloorRegistry) -> None:
    """Make sure we can get the floors by name."""
    floor = floor_registry.async_create("First floor")
    floor2 = floor_registry.async_get_floor_by_name("first floor")
    floor3 = floor_registry.async_get_floor_by_name("first    floor")

    assert floor == floor2
    assert floor == floor3
    assert floor2 == floor3

    get_floor = floor_registry.async_get_floor(floor.floor_id)
    assert get_floor == floor


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
