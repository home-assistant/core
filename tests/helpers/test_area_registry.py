"""Tests for the Area Registry."""
import asyncio

import asynctest
import pytest

from homeassistant.helpers import area_registry
from tests.common import mock_area_registry, flush_store


@pytest.fixture
def registry(hass):
    """Return an empty, loaded, registry."""
    return mock_area_registry(hass)


async def test_list_areas(registry):
    """Make sure that we can read areas."""
    registry.async_create('mock')

    areas = registry.async_list_areas()

    assert len(areas) == len(registry.areas)


async def test_create_area(registry):
    """Make sure that we can create an area."""
    area = registry.async_create('mock')

    assert area.name == 'mock'
    assert len(registry.areas) == 1


async def test_create_area_with_name_already_in_use(registry):
    """Make sure that we can't create an area with a name already in use."""
    area1 = registry.async_create('mock')

    with pytest.raises(ValueError) as e_info:
        area2 = registry.async_create('mock')
        assert area1 != area2
        assert e_info == "Name is already in use"

    assert len(registry.areas) == 1


async def test_delete_area(registry):
    """Make sure that we can delete an area."""
    area = registry.async_create('mock')

    await registry.async_delete(area.id)

    assert not registry.areas


async def test_delete_non_existing_area(registry):
    """Make sure that we can't delete an area that doesn't exist."""
    registry.async_create('mock')

    with pytest.raises(KeyError):
        await registry.async_delete('')

    assert len(registry.areas) == 1


async def test_update_area(registry):
    """Make sure that we can read areas."""
    area = registry.async_create('mock')

    updated_area = registry.async_update(area.id, name='mock1')

    assert updated_area != area
    assert updated_area.name == 'mock1'
    assert len(registry.areas) == 1


async def test_update_area_with_same_name(registry):
    """Make sure that we can reapply the same name to the area."""
    area = registry.async_create('mock')

    updated_area = registry.async_update(area.id, name='mock')

    assert updated_area == area
    assert len(registry.areas) == 1


async def test_update_area_with_name_already_in_use(registry):
    """Make sure that we can't update an area with a name already in use."""
    area1 = registry.async_create('mock1')
    area2 = registry.async_create('mock2')

    with pytest.raises(ValueError) as e_info:
        registry.async_update(area1.id, name='mock2')
        assert e_info == "Name is already in use"

    assert area1.name == 'mock1'
    assert area2.name == 'mock2'
    assert len(registry.areas) == 2


async def test_load_area(hass, registry):
    """Make sure that we can load/save data correctly."""
    registry.async_create('mock1')
    registry.async_create('mock2')

    assert len(registry.areas) == 2

    registry2 = area_registry.AreaRegistry(hass)
    await flush_store(registry._store)
    await registry2.async_load()

    assert list(registry.areas) == list(registry2.areas)


async def test_loading_area_from_storage(hass, hass_storage):
    """Test loading stored areas on start."""
    hass_storage[area_registry.STORAGE_KEY] = {
        'version': area_registry.STORAGE_VERSION,
        'data': {
            'areas': [
                {
                    'id': '12345A',
                    'name': 'mock'
                }
            ]
        }
    }

    registry = await area_registry.async_get_registry(hass)

    assert len(registry.areas) == 1


async def test_loading_race_condition(hass):
    """Test only one storage load called when concurrent loading occurred ."""
    with asynctest.patch(
        'homeassistant.helpers.area_registry.AreaRegistry.async_load',
    ) as mock_load:
        results = await asyncio.gather(
            area_registry.async_get_registry(hass),
            area_registry.async_get_registry(hass),
        )

        mock_load.assert_called_once_with()
        assert results[0] == results[1]
