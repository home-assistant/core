"""Tests for the folder registry."""
import re
from typing import Any

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import folder_registry as fr
from homeassistant.helpers.folder_registry import (
    EVENT_FOLDER_REGISTRY_UPDATED,
    STORAGE_KEY,
    STORAGE_VERSION_MAJOR,
    FolderRegistry,
    async_get,
    async_load,
)

from tests.common import async_capture_events, flush_store


async def test_create_folder(
    hass: HomeAssistant, folder_registry: fr.FolderRegistry
) -> None:
    """Make sure that we can create folders."""
    update_events = async_capture_events(hass, EVENT_FOLDER_REGISTRY_UPDATED)
    folder = folder_registry.async_create(
        domain="test",
        name="My Folder",
        icon="mdi:test",
    )

    assert folder.folder_id
    assert folder.name == "My Folder"
    assert folder.normalized_name == "myfolder"

    assert len(folder_registry.folders) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 1
    assert update_events[0].data == {
        "action": "create",
        "domain": "test",
        "folder_id": folder.folder_id,
    }


async def test_create_folder_with_name_already_in_use(
    hass: HomeAssistant, folder_registry: fr.FolderRegistry
) -> None:
    """Make sure that we can't create a folder with a name already in use."""
    update_events = async_capture_events(hass, EVENT_FOLDER_REGISTRY_UPDATED)
    folder_registry.async_create("test", "mock")

    with pytest.raises(
        ValueError, match=re.escape("The name mock (mock) is already in use")
    ):
        folder_registry.async_create("test", "mock")

    await hass.async_block_till_done()

    assert len(folder_registry.folders) == 1
    assert len(update_events) == 1


async def test_delete_folder(
    hass: HomeAssistant, folder_registry: fr.FolderRegistry
) -> None:
    """Make sure that we can delete a folder."""
    update_events = async_capture_events(hass, EVENT_FOLDER_REGISTRY_UPDATED)
    folder = folder_registry.async_create("automation", "My living room automations")
    assert len(folder_registry.folders) == 1

    folder_registry.async_delete(folder.folder_id)

    assert not folder_registry.folders

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0].data == {
        "action": "create",
        "domain": "automation",
        "folder_id": folder.folder_id,
    }
    assert update_events[1].data == {
        "action": "remove",
        "domain": "automation",
        "folder_id": folder.folder_id,
    }


@pytest.mark.usefixtures("hass")
async def test_delete_non_existing_folder(folder_registry: fr.FolderRegistry) -> None:
    """Make sure that we can't delete a folder that doesn't exist."""
    folder_registry.async_create("test", "mock")

    with pytest.raises(KeyError):
        folder_registry.async_delete("")

    assert len(folder_registry.folders) == 1


async def test_update_folder(
    hass: HomeAssistant, folder_registry: fr.FolderRegistry
) -> None:
    """Make sure that we can update folders."""
    update_events = async_capture_events(hass, EVENT_FOLDER_REGISTRY_UPDATED)
    folder = folder_registry.async_create("script", "My notification script")

    assert len(folder_registry.folders) == 1
    assert folder.folder_id
    assert folder.name == "My notification script"
    assert folder.normalized_name == "mynotificationscript"
    assert folder.icon is None

    updated_folder = folder_registry.async_update(
        folder.folder_id,
        name="My notification thingies",
        icon="mdi:update",
    )

    assert updated_folder != folder
    assert updated_folder.folder_id == folder.folder_id
    assert updated_folder.name == "My notification thingies"
    assert updated_folder.normalized_name == "mynotificationthingies"
    assert updated_folder.icon == "mdi:update"

    assert len(folder_registry.folders) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0].data == {
        "action": "create",
        "domain": "script",
        "folder_id": folder.folder_id,
    }
    assert update_events[1].data == {
        "action": "update",
        "domain": "script",
        "folder_id": folder.folder_id,
    }


async def test_update_folder_with_same_data(
    hass: HomeAssistant, folder_registry: fr.FolderRegistry
) -> None:
    """Make sure that we can reapply the same data to the folder and it won't update."""
    update_events = async_capture_events(hass, EVENT_FOLDER_REGISTRY_UPDATED)
    folder = folder_registry.async_create(
        "zone",
        "Shops",
        icon="mdi:shopping-cart",
    )

    updated_folder = folder_registry.async_update(
        folder_id=folder.folder_id,
        name="Shops",
        icon="mdi:shopping-cart",
    )
    assert folder == updated_folder

    await hass.async_block_till_done()

    # No update event
    assert len(update_events) == 1
    assert update_events[0].data == {
        "action": "create",
        "domain": "zone",
        "folder_id": folder.folder_id,
    }


@pytest.mark.usefixtures("hass")
async def test_update_folder_with_same_name_change_case(
    folder_registry: fr.FolderRegistry,
) -> None:
    """Make sure that we can reapply the same name with a different case to the folder."""
    folder = folder_registry.async_create("automation", "frenck")

    updated_folder = folder_registry.async_update(folder.folder_id, name="Frenck")

    assert updated_folder.name == "Frenck"
    assert updated_folder.folder_id == folder.folder_id
    assert updated_folder.normalized_name == folder.normalized_name
    assert len(folder_registry.folders) == 1


@pytest.mark.usefixtures("hass")
async def test_update_folder_with_name_already_in_use(
    folder_registry: fr.FolderRegistry,
) -> None:
    """Make sure that we can't update an folder with a name already in use."""
    folder1 = folder_registry.async_create("automation", "Kitchen")
    folder2 = folder_registry.async_create("automation", "Another kitchen")

    with pytest.raises(
        ValueError, match=re.escape("The name kitchen (kitchen) is already in use")
    ):
        folder_registry.async_update(folder2.folder_id, name="kitchen")

    assert folder1.name == "Kitchen"
    assert folder2.name == "Another kitchen"
    assert len(folder_registry.folders) == 2


@pytest.mark.usefixtures("hass")
async def test_update_folder_with_normalized_name_already_in_use(
    folder_registry: fr.FolderRegistry,
) -> None:
    """Make sure that we can't update a folder with a normalized name already in use."""
    folder1 = folder_registry.async_create("scripts", "mock1")
    folder2 = folder_registry.async_create("scripts", "M O C K 2")

    with pytest.raises(
        ValueError, match=re.escape("The name mock2 (mock2) is already in use")
    ):
        folder_registry.async_update(folder1.folder_id, name="mock2")

    assert folder1.name == "mock1"
    assert folder2.name == "M O C K 2"
    assert len(folder_registry.folders) == 2


async def test_load_folders(
    hass: HomeAssistant, folder_registry: fr.FolderRegistry
) -> None:
    """Make sure that we can load/save data correctly."""
    folder1 = folder_registry.async_create(
        "automation",
        "One",
        icon="mdi:one",
    )
    folder2 = folder_registry.async_create(
        "script",
        "Two",
        icon="mdi:two",
    )

    assert len(folder_registry.folders) == 2

    registry2 = FolderRegistry(hass)
    await flush_store(folder_registry._store)
    await registry2.async_load()

    assert len(registry2.folders) == 2
    assert list(folder_registry.folders) == list(registry2.folders)

    folder1_registry2 = registry2.async_get_or_create("automation", "One")
    assert folder1_registry2.folder_id == folder1.folder_id
    assert folder1_registry2.domain == folder1.domain
    assert folder1_registry2.name == folder1.name
    assert folder1_registry2.icon == folder1.icon
    assert folder1_registry2.normalized_name == folder1.normalized_name

    folder2_registry2 = registry2.async_get_or_create("script", "Two")
    assert folder2_registry2.folder_id == folder2.folder_id
    assert folder2_registry2.domain == folder2.domain
    assert folder2_registry2.name == folder2.name
    assert folder2_registry2.icon == folder2.icon
    assert folder2_registry2.normalized_name == folder2.normalized_name


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_folders_from_storage(
    hass: HomeAssistant, hass_storage: Any
) -> None:
    """Test loading stored folders on start."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION_MAJOR,
        "data": {
            "folders": [
                {
                    "domain": "automation",
                    "icon": "mdi:one",
                    "folder_id": "uuid1",
                    "name": "One",
                },
                {
                    "domain": "script",
                    "icon": None,
                    "folder_id": "uuid2",
                    "name": "Two",
                },
            ]
        },
    }

    await async_load(hass)
    registry = async_get(hass)

    assert len(registry.folders) == 2


@pytest.mark.usefixtures("hass")
async def test_getting_folders(folder_registry: fr.FolderRegistry) -> None:
    """Make sure we can get the folderrs by name."""
    folder1 = folder_registry.async_get_or_create("automation", "Living room")
    folder2 = folder_registry.async_get_or_create("automation", "living room")
    folder3 = folder_registry.async_get_or_create("automation", "living    room")

    assert folder1 == folder2
    assert folder1 == folder3
    assert folder2 == folder3

    get_folder = folder_registry.async_get_folder_by_name(
        "automation", "l i v i n g   r o o m"
    )
    assert get_folder == folder1

    get_folder = folder_registry.async_get_folder(folder1.folder_id)
    assert get_folder == folder1


@pytest.mark.usefixtures("hass")
async def test_async_get_folder_by_name_not_found(
    folder_registry: fr.FolderRegistry,
) -> None:
    """Make sure we return None for non-existent folders."""
    folder_registry.async_create("automation", "Bathroom")

    assert len(folder_registry.folders) == 1

    assert folder_registry.async_get_folder_by_name("automation", "mancave") is None
