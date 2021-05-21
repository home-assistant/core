"""Tests for the Area Registry."""
import pytest

from homeassistant.core import callback
from homeassistant.helpers import area_registry

from tests.common import flush_store, mock_area_registry


@pytest.fixture
def registry(hass):
    """Return an empty, loaded, registry."""
    return mock_area_registry(hass)


@pytest.fixture
def update_events(hass):
    """Capture update events."""
    events = []

    @callback
    def async_capture(event):
        events.append(event.data)

    hass.bus.async_listen(area_registry.EVENT_AREA_REGISTRY_UPDATED, async_capture)

    return events


async def test_list_areas(registry):
    """Make sure that we can read areas."""
    registry.async_create("mock")

    areas = registry.async_list_areas()

    assert len(areas) == len(registry.areas)


async def test_create_area(hass, registry, update_events):
    """Make sure that we can create an area."""
    area = registry.async_create("mock")

    assert area.id == "mock"
    assert area.name == "mock"
    assert len(registry.areas) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 1
    assert update_events[0]["action"] == "create"
    assert update_events[0]["area_id"] == area.id


async def test_create_area_with_name_already_in_use(hass, registry, update_events):
    """Make sure that we can't create an area with a name already in use."""
    area1 = registry.async_create("mock")

    with pytest.raises(ValueError) as e_info:
        area2 = registry.async_create("mock")
        assert area1 != area2
        assert e_info == "The name mock 2 (mock2) is already in use"

    await hass.async_block_till_done()

    assert len(registry.areas) == 1
    assert len(update_events) == 1


async def test_create_area_with_id_already_in_use(registry):
    """Make sure that we can't create an area with a name already in use."""
    area1 = registry.async_create("mock")

    updated_area1 = registry.async_update(area1.id, "New Name")
    assert updated_area1.id == area1.id

    area2 = registry.async_create("mock")
    assert area2.id == "mock_2"


async def test_delete_area(hass, registry, update_events):
    """Make sure that we can delete an area."""
    area = registry.async_create("mock")

    registry.async_delete(area.id)

    assert not registry.areas

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0]["action"] == "create"
    assert update_events[0]["area_id"] == area.id
    assert update_events[1]["action"] == "remove"
    assert update_events[1]["area_id"] == area.id


async def test_delete_non_existing_area(registry):
    """Make sure that we can't delete an area that doesn't exist."""
    registry.async_create("mock")

    with pytest.raises(KeyError):
        await registry.async_delete("")

    assert len(registry.areas) == 1


async def test_update_area(hass, registry, update_events):
    """Make sure that we can read areas."""
    area = registry.async_create("mock")

    updated_area = registry.async_update(area.id, name="mock1")

    assert updated_area != area
    assert updated_area.name == "mock1"
    assert len(registry.areas) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0]["action"] == "create"
    assert update_events[0]["area_id"] == area.id
    assert update_events[1]["action"] == "update"
    assert update_events[1]["area_id"] == area.id


async def test_update_area_with_same_name(registry):
    """Make sure that we can reapply the same name to the area."""
    area = registry.async_create("mock")

    updated_area = registry.async_update(area.id, name="mock")

    assert updated_area == area
    assert len(registry.areas) == 1


async def test_update_area_with_same_name_change_case(registry):
    """Make sure that we can reapply the same name with a different case to the area."""
    area = registry.async_create("mock")

    updated_area = registry.async_update(area.id, name="Mock")

    assert updated_area.name == "Mock"
    assert updated_area.id == area.id
    assert updated_area.normalized_name == area.normalized_name
    assert len(registry.areas) == 1


async def test_update_area_with_name_already_in_use(registry):
    """Make sure that we can't update an area with a name already in use."""
    area1 = registry.async_create("mock1")
    area2 = registry.async_create("mock2")

    with pytest.raises(ValueError) as e_info:
        registry.async_update(area1.id, name="mock2")
        assert e_info == "The name mock 2 (mock2) is already in use"

    assert area1.name == "mock1"
    assert area2.name == "mock2"
    assert len(registry.areas) == 2


async def test_update_area_with_normalized_name_already_in_use(registry):
    """Make sure that we can't update an area with a normalized name already in use."""
    area1 = registry.async_create("mock1")
    area2 = registry.async_create("Moc k2")

    with pytest.raises(ValueError) as e_info:
        registry.async_update(area1.id, name="mock2")
        assert e_info == "The name mock 2 (mock2) is already in use"

    assert area1.name == "mock1"
    assert area2.name == "Moc k2"
    assert len(registry.areas) == 2


async def test_load_area(hass, registry):
    """Make sure that we can load/save data correctly."""
    area1 = registry.async_create("mock1")
    area2 = registry.async_create("mock2")

    assert len(registry.areas) == 2

    registry2 = area_registry.AreaRegistry(hass)
    await flush_store(registry._store)
    await registry2.async_load()

    assert list(registry.areas) == list(registry2.areas)

    area1_registry2 = registry2.async_get_or_create("mock1")
    assert area1_registry2.id == area1.id
    area2_registry2 = registry2.async_get_or_create("mock2")
    assert area2_registry2.id == area2.id


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_area_from_storage(hass, hass_storage):
    """Test loading stored areas on start."""
    hass_storage[area_registry.STORAGE_KEY] = {
        "version": area_registry.STORAGE_VERSION,
        "data": {"areas": [{"id": "12345A", "name": "mock"}]},
    }

    await area_registry.async_load(hass)
    registry = area_registry.async_get(hass)

    assert len(registry.areas) == 1


async def test_async_get_or_create(hass, registry):
    """Make sure we can get the area by name."""
    area = registry.async_get_or_create("Mock1")
    area2 = registry.async_get_or_create("mock1")
    area3 = registry.async_get_or_create("mock   1")

    assert area == area2
    assert area == area3
    assert area2 == area3


async def test_async_get_area_by_name(hass, registry):
    """Make sure we can get the area by name."""
    registry.async_create("Mock1")

    assert len(registry.areas) == 1

    assert registry.async_get_area_by_name("M o c k 1").normalized_name == "mock1"


async def test_async_get_area_by_name_not_found(hass, registry):
    """Make sure we return None for non-existent areas."""
    registry.async_create("Mock1")

    assert len(registry.areas) == 1

    assert registry.async_get_area_by_name("non_exist") is None


async def test_async_get_area(hass, registry):
    """Make sure we can get the area by id."""
    area = registry.async_create("Mock1")

    assert len(registry.areas) == 1

    assert registry.async_get_area(area.id).normalized_name == "mock1"
