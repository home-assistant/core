"""Tests for the category registry."""

from datetime import datetime
from functools import partial
import re
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import category_registry as cr
from homeassistant.util.dt import UTC

from tests.common import async_capture_events, flush_store


async def test_list_categories_for_scope(
    category_registry: cr.CategoryRegistry,
) -> None:
    """Make sure that we can read categories for scope."""
    categories = category_registry.async_list_categories(scope="automation")
    assert len(list(categories)) == len(
        category_registry.categories.get("automation", {})
    )


async def test_create_category(
    hass: HomeAssistant, category_registry: cr.CategoryRegistry
) -> None:
    """Make sure that we can create new categories."""
    update_events = async_capture_events(hass, cr.EVENT_CATEGORY_REGISTRY_UPDATED)
    category = category_registry.async_create(
        scope="automation",
        name="Energy saving",
        icon="mdi:leaf",
    )

    assert category.category_id
    assert category.name == "Energy saving"
    assert category.icon == "mdi:leaf"

    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 1
    assert update_events[0].data == {
        "action": "create",
        "scope": "automation",
        "category_id": category.category_id,
    }


async def test_create_category_with_name_already_in_use(
    hass: HomeAssistant, category_registry: cr.CategoryRegistry
) -> None:
    """Make sure that we can't create a category with the same name within a scope."""
    update_events = async_capture_events(hass, cr.EVENT_CATEGORY_REGISTRY_UPDATED)
    category_registry.async_create(
        scope="automation",
        name="Energy saving",
        icon="mdi:leaf",
    )

    with pytest.raises(
        ValueError,
        match=re.escape("The name 'ENERGY SAVING' is already in use"),
    ):
        category_registry.async_create(
            scope="automation",
            name="ENERGY SAVING",
            icon="mdi:leaf",
        )

    await hass.async_block_till_done()

    assert len(category_registry.categories["automation"]) == 1
    assert len(update_events) == 1


async def test_create_category_with_duplicate_name_in_other_scopes(
    hass: HomeAssistant, category_registry: cr.CategoryRegistry
) -> None:
    """Make we can create the same category in multiple scopes."""
    update_events = async_capture_events(hass, cr.EVENT_CATEGORY_REGISTRY_UPDATED)
    category_registry.async_create(
        scope="automation",
        name="Energy saving",
        icon="mdi:leaf",
    )
    category_registry.async_create(
        scope="script",
        name="Energy saving",
        icon="mdi:leaf",
    )

    await hass.async_block_till_done()

    assert len(category_registry.categories["script"]) == 1
    assert len(category_registry.categories["automation"]) == 1
    assert len(update_events) == 2


async def test_delete_category(
    hass: HomeAssistant, category_registry: cr.CategoryRegistry
) -> None:
    """Make sure that we can delete a category."""
    update_events = async_capture_events(hass, cr.EVENT_CATEGORY_REGISTRY_UPDATED)
    category = category_registry.async_create(
        scope="automation",
        name="Energy saving",
        icon="mdi:leaf",
    )

    assert len(category_registry.categories["automation"]) == 1

    category_registry.async_delete(scope="automation", category_id=category.category_id)

    assert not category_registry.categories["automation"]

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0].data == {
        "action": "create",
        "scope": "automation",
        "category_id": category.category_id,
    }
    assert update_events[1].data == {
        "action": "remove",
        "scope": "automation",
        "category_id": category.category_id,
    }


async def test_delete_non_existing_category(
    category_registry: cr.CategoryRegistry,
) -> None:
    """Make sure that we can't delete a category that doesn't exist."""
    category = category_registry.async_create(
        scope="automation",
        name="Energy saving",
        icon="mdi:leaf",
    )

    with pytest.raises(KeyError):
        category_registry.async_delete(scope="automation", category_id="")

    with pytest.raises(KeyError):
        category_registry.async_delete(scope="", category_id=category.category_id)

    assert len(category_registry.categories["automation"]) == 1


async def test_update_category(
    hass: HomeAssistant,
    category_registry: cr.CategoryRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Make sure that we can update categories."""
    created = datetime(2024, 2, 14, 12, 0, 0, tzinfo=UTC)
    freezer.move_to(created)
    update_events = async_capture_events(hass, cr.EVENT_CATEGORY_REGISTRY_UPDATED)
    category = category_registry.async_create(
        scope="automation",
        name="Energy saving",
    )

    assert len(category_registry.categories["automation"]) == 1
    assert category == cr.CategoryEntry(
        category_id=category.category_id,
        created_at=created,
        modified_at=created,
        name="Energy saving",
        icon=None,
    )

    modified = datetime(2024, 3, 14, 12, 0, 0, tzinfo=UTC)
    freezer.move_to(modified)

    updated_category = category_registry.async_update(
        scope="automation",
        category_id=category.category_id,
        name="ENERGY SAVING",
        icon="mdi:leaf",
    )

    assert updated_category != category
    assert updated_category == cr.CategoryEntry(
        category_id=category.category_id,
        created_at=created,
        modified_at=modified,
        name="ENERGY SAVING",
        icon="mdi:leaf",
    )

    assert len(category_registry.categories["automation"]) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0].data == {
        "action": "create",
        "scope": "automation",
        "category_id": category.category_id,
    }
    assert update_events[1].data == {
        "action": "update",
        "scope": "automation",
        "category_id": category.category_id,
    }


async def test_update_category_with_same_data(
    hass: HomeAssistant, category_registry: cr.CategoryRegistry
) -> None:
    """Make sure that we can reapply the same data to a category and it won't update."""
    update_events = async_capture_events(hass, cr.EVENT_CATEGORY_REGISTRY_UPDATED)
    category = category_registry.async_create(
        scope="automation",
        name="Energy saving",
        icon="mdi:leaf",
    )

    updated_category = category_registry.async_update(
        scope="automation",
        category_id=category.category_id,
        name="Energy saving",
        icon="mdi:leaf",
    )
    assert category == updated_category

    await hass.async_block_till_done()

    # No update event
    assert len(update_events) == 1
    assert update_events[0].data == {
        "action": "create",
        "scope": "automation",
        "category_id": category.category_id,
    }


async def test_update_category_with_same_name_change_case(
    category_registry: cr.CategoryRegistry,
) -> None:
    """Make sure that we can reapply the same name with a different case to a category."""
    category = category_registry.async_create(
        scope="automation",
        name="Energy saving",
        icon="mdi:leaf",
    )

    updated_category = category_registry.async_update(
        scope="automation",
        category_id=category.category_id,
        name="ENERGY SAVING",
    )

    assert updated_category.category_id == category.category_id
    assert updated_category.name == "ENERGY SAVING"
    assert updated_category.icon == "mdi:leaf"
    assert len(category_registry.categories["automation"]) == 1


async def test_update_category_with_name_already_in_use(
    category_registry: cr.CategoryRegistry,
) -> None:
    """Make sure that we can't update a category with a name already in use."""
    category1 = category_registry.async_create(
        scope="automation",
        name="Energy saving",
        icon="mdi:leaf",
    )
    category2 = category_registry.async_create(
        scope="automation",
        name="Something else",
        icon="mdi:leaf",
    )

    with pytest.raises(
        ValueError,
        match=re.escape("The name 'ENERGY SAVING' is already in use"),
    ):
        category_registry.async_update(
            scope="automation",
            category_id=category2.category_id,
            name="ENERGY SAVING",
        )

    assert category1.name == "Energy saving"
    assert category2.name == "Something else"
    assert len(category_registry.categories["automation"]) == 2


async def test_load_categories(
    hass: HomeAssistant, category_registry: cr.CategoryRegistry
) -> None:
    """Make sure that we can load/save data correctly."""
    category1 = category_registry.async_create(
        scope="automation",
        name="Energy saving",
        icon="mdi:leaf",
    )
    category2 = category_registry.async_create(
        scope="automation",
        name="Something else",
        icon="mdi:leaf",
    )
    category3 = category_registry.async_create(
        scope="zone",
        name="Grocery stores",
        icon="mdi:store",
    )

    assert len(category_registry.categories) == 2
    assert len(category_registry.categories["automation"]) == 2
    assert len(category_registry.categories["zone"]) == 1

    registry2 = cr.CategoryRegistry(hass)
    await flush_store(category_registry._store)
    await registry2.async_load()

    assert len(registry2.categories) == 2
    assert len(registry2.categories["automation"]) == 2
    assert len(registry2.categories["zone"]) == 1
    assert list(category_registry.categories) == list(registry2.categories)
    assert list(category_registry.categories["automation"]) == list(
        registry2.categories["automation"]
    )
    assert list(category_registry.categories["zone"]) == list(
        registry2.categories["zone"]
    )

    category1_registry2 = registry2.async_get_category(
        scope="automation", category_id=category1.category_id
    )
    assert category1_registry2.category_id == category1.category_id
    assert category1_registry2.name == category1.name
    assert category1_registry2.icon == category1.icon

    category2_registry2 = registry2.async_get_category(
        scope="automation", category_id=category2.category_id
    )
    assert category2_registry2.category_id == category2.category_id
    assert category2_registry2.name == category2.name
    assert category2_registry2.icon == category2.icon

    category3_registry2 = registry2.async_get_category(
        scope="zone", category_id=category3.category_id
    )
    assert category3_registry2.category_id == category3.category_id
    assert category3_registry2.name == category3.name
    assert category3_registry2.icon == category3.icon


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_categories_from_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading stored categories on start."""
    date_1 = datetime(2024, 2, 14, 12, 0, 0)
    date_2 = datetime(2024, 2, 14, 12, 0, 0)
    hass_storage[cr.STORAGE_KEY] = {
        "version": cr.STORAGE_VERSION_MAJOR,
        "minor_version": cr.STORAGE_VERSION_MINOR,
        "data": {
            "categories": {
                "automation": [
                    {
                        "category_id": "uuid1",
                        "created_at": date_1.isoformat(),
                        "modified_at": date_1.isoformat(),
                        "name": "Energy saving",
                        "icon": "mdi:leaf",
                    },
                    {
                        "category_id": "uuid2",
                        "created_at": date_1.isoformat(),
                        "modified_at": date_2.isoformat(),
                        "name": "Something else",
                        "icon": None,
                    },
                ],
                "zone": [
                    {
                        "category_id": "uuid3",
                        "created_at": date_2.isoformat(),
                        "modified_at": date_2.isoformat(),
                        "name": "Grocery stores",
                        "icon": "mdi:store",
                    },
                ],
            }
        },
    }

    await cr.async_load(hass)
    category_registry = cr.async_get(hass)

    assert len(category_registry.categories) == 2
    assert len(category_registry.categories["automation"]) == 2
    assert len(category_registry.categories["zone"]) == 1

    category1 = category_registry.async_get_category(
        scope="automation", category_id="uuid1"
    )
    assert category1 == cr.CategoryEntry(
        category_id="uuid1",
        created_at=date_1,
        modified_at=date_1,
        name="Energy saving",
        icon="mdi:leaf",
    )

    category2 = category_registry.async_get_category(
        scope="automation", category_id="uuid2"
    )
    assert category2 == cr.CategoryEntry(
        category_id="uuid2",
        created_at=date_1,
        modified_at=date_2,
        name="Something else",
        icon=None,
    )

    category3 = category_registry.async_get_category(scope="zone", category_id="uuid3")
    assert category3 == cr.CategoryEntry(
        category_id="uuid3",
        created_at=date_2,
        modified_at=date_2,
        name="Grocery stores",
        icon="mdi:store",
    )


async def test_async_create_thread_safety(
    hass: HomeAssistant, category_registry: cr.CategoryRegistry
) -> None:
    """Test async_create raises when called from wrong thread."""
    with pytest.raises(
        RuntimeError,
        match="Detected code that calls category_registry.async_create from a thread.",
    ):
        await hass.async_add_executor_job(
            partial(category_registry.async_create, name="any", scope="any")
        )


async def test_async_delete_thread_safety(
    hass: HomeAssistant, category_registry: cr.CategoryRegistry
) -> None:
    """Test async_delete raises when called from wrong thread."""
    any_category = category_registry.async_create(name="any", scope="any")

    with pytest.raises(
        RuntimeError,
        match="Detected code that calls category_registry.async_delete from a thread.",
    ):
        await hass.async_add_executor_job(
            partial(
                category_registry.async_delete,
                scope="any",
                category_id=any_category.category_id,
            )
        )


async def test_async_update_thread_safety(
    hass: HomeAssistant, category_registry: cr.CategoryRegistry
) -> None:
    """Test async_update raises when called from wrong thread."""
    any_category = category_registry.async_create(name="any", scope="any")

    with pytest.raises(
        RuntimeError,
        match="Detected code that calls category_registry.async_update from a thread.",
    ):
        await hass.async_add_executor_job(
            partial(
                category_registry.async_update,
                scope="any",
                category_id=any_category.category_id,
                name="new name",
            )
        )


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_from_1_1(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test migration from version 1.1."""
    hass_storage[cr.STORAGE_KEY] = {
        "version": 1,
        "data": {
            "categories": {
                "automation": [
                    {
                        "category_id": "uuid1",
                        "name": "Energy saving",
                        "icon": "mdi:leaf",
                    },
                    {
                        "category_id": "uuid2",
                        "name": "Something else",
                        "icon": None,
                    },
                ],
                "zone": [
                    {
                        "category_id": "uuid3",
                        "name": "Grocery stores",
                        "icon": "mdi:store",
                    },
                ],
            }
        },
    }

    await cr.async_load(hass)
    registry = cr.async_get(hass)

    # Test data was loaded
    assert len(registry.categories) == 2
    assert len(registry.categories["automation"]) == 2
    assert len(registry.categories["zone"]) == 1

    assert registry.async_get_category(scope="automation", category_id="uuid1")

    # Check we store migrated data
    await flush_store(registry._store)
    assert hass_storage[cr.STORAGE_KEY] == {
        "version": cr.STORAGE_VERSION_MAJOR,
        "minor_version": cr.STORAGE_VERSION_MINOR,
        "key": cr.STORAGE_KEY,
        "data": {
            "categories": {
                "automation": [
                    {
                        "category_id": "uuid1",
                        "created_at": "1970-01-01T00:00:00+00:00",
                        "modified_at": "1970-01-01T00:00:00+00:00",
                        "name": "Energy saving",
                        "icon": "mdi:leaf",
                    },
                    {
                        "category_id": "uuid2",
                        "created_at": "1970-01-01T00:00:00+00:00",
                        "modified_at": "1970-01-01T00:00:00+00:00",
                        "name": "Something else",
                        "icon": None,
                    },
                ],
                "zone": [
                    {
                        "category_id": "uuid3",
                        "created_at": "1970-01-01T00:00:00+00:00",
                        "modified_at": "1970-01-01T00:00:00+00:00",
                        "name": "Grocery stores",
                        "icon": "mdi:store",
                    },
                ],
            }
        },
    }
