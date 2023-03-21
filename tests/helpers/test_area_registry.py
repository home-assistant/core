"""Tests for the Area Registry."""
from typing import Any

import pytest

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar

from tests.common import ANY, flush_store


@pytest.fixture
def update_events(hass):
    """Capture update events."""
    events = []

    @callback
    def async_capture(event):
        events.append(event.data)

    hass.bus.async_listen(ar.EVENT_AREA_REGISTRY_UPDATED, async_capture)

    return events


async def test_list_areas(area_registry: ar.AreaRegistry) -> None:
    """Make sure that we can read areas."""
    area_registry.async_create("mock")

    areas = area_registry.async_list_areas()

    assert len(areas) == len(area_registry.areas)


async def test_create_area(
    hass: HomeAssistant, area_registry: ar.AreaRegistry, update_events
) -> None:
    """Make sure that we can create an area."""
    # Create area with only mandatory parameters
    area = area_registry.async_create("mock")

    assert area == ar.AreaEntry(
        name="mock", normalized_name=ANY, aliases=set(), id=ANY, picture=None
    )
    assert len(area_registry.areas) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 1
    assert update_events[-1]["action"] == "create"
    assert update_events[-1]["area_id"] == area.id

    # Create area with all parameters
    area = area_registry.async_create(
        "mock 2", aliases={"alias_1", "alias_2"}, picture="/image/example.png"
    )

    assert area == ar.AreaEntry(
        name="mock 2",
        normalized_name=ANY,
        aliases={"alias_1", "alias_2"},
        id=ANY,
        picture="/image/example.png",
    )
    assert len(area_registry.areas) == 2

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[-1]["action"] == "create"
    assert update_events[-1]["area_id"] == area.id


async def test_create_area_with_name_already_in_use(
    hass: HomeAssistant, area_registry: ar.AreaRegistry, update_events
) -> None:
    """Make sure that we can't create an area with a name already in use."""
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
    hass: HomeAssistant, area_registry: ar.AreaRegistry, update_events
) -> None:
    """Make sure that we can delete an area."""
    area = area_registry.async_create("mock")

    area_registry.async_delete(area.id)

    assert not area_registry.areas

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0]["action"] == "create"
    assert update_events[0]["area_id"] == area.id
    assert update_events[1]["action"] == "remove"
    assert update_events[1]["area_id"] == area.id


async def test_delete_non_existing_area(area_registry: ar.AreaRegistry) -> None:
    """Make sure that we can't delete an area that doesn't exist."""
    area_registry.async_create("mock")

    with pytest.raises(KeyError):
        await area_registry.async_delete("")

    assert len(area_registry.areas) == 1


async def test_update_area(
    hass: HomeAssistant, area_registry: ar.AreaRegistry, update_events
) -> None:
    """Make sure that we can read areas."""
    area = area_registry.async_create("mock")

    updated_area = area_registry.async_update(
        area.id,
        aliases={"alias_1", "alias_2"},
        name="mock1",
        picture="/image/example.png",
    )

    assert updated_area != area
    assert updated_area == ar.AreaEntry(
        name="mock1",
        normalized_name=ANY,
        aliases={"alias_1", "alias_2"},
        id=ANY,
        picture="/image/example.png",
    )
    assert len(area_registry.areas) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0]["action"] == "create"
    assert update_events[0]["area_id"] == area.id
    assert update_events[1]["action"] == "update"
    assert update_events[1]["area_id"] == area.id


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
                    "id": "12345A",
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
            "areas": [{"aliases": [], "id": "12345A", "name": "mock", "picture": None}]
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
