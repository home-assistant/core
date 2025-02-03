"""Test for todo platform of the Bring! integration."""

from collections.abc import Generator
import re
from unittest.mock import AsyncMock, patch

from bring_api import BringItemOperation, BringItemsResponse, BringRequestException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bring.const import DOMAIN
from homeassistant.components.todo import (
    ATTR_DESCRIPTION,
    ATTR_ITEM,
    ATTR_RENAME,
    DOMAIN as TODO_DOMAIN,
    TodoServices,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, load_fixture, snapshot_platform


@pytest.fixture(autouse=True)
def todo_only() -> Generator[None]:
    """Enable only the todo platform."""
    with patch(
        "homeassistant.components.bring.PLATFORMS",
        [Platform.TODO],
    ):
        yield


@pytest.mark.usefixtures("mock_bring_client")
async def test_todo(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_bring_client: AsyncMock,
) -> None:
    """Snapshot test states of todo platform."""
    mock_bring_client.get_list.side_effect = [
        BringItemsResponse.from_json(load_fixture("items.json", DOMAIN)),
        BringItemsResponse.from_json(load_fixture("items2.json", DOMAIN)),
    ]
    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(
        hass, entity_registry, snapshot, bring_config_entry.entry_id
    )


@pytest.mark.usefixtures("mock_uuid")
async def test_add_item(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
) -> None:
    """Test add item to list."""

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        service_data={ATTR_ITEM: "Äpfel", ATTR_DESCRIPTION: "rot"},
        target={ATTR_ENTITY_ID: "todo.einkauf"},
        blocking=True,
    )

    mock_bring_client.save_item.assert_called_once_with(
        "e542eef6-dba7-4c31-a52c-29e6ab9d83a5",
        "Äpfel",
        "rot",
        "b669ad23-606a-4652-b302-995d34b1cb1c",
    )


async def test_add_item_exception(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
) -> None:
    """Test add item to list with exception."""

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.LOADED

    mock_bring_client.save_item.side_effect = BringRequestException
    with pytest.raises(
        HomeAssistantError, match="Failed to save item Äpfel to Bring! list"
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.ADD_ITEM,
            service_data={ATTR_ITEM: "Äpfel", ATTR_DESCRIPTION: "rot"},
            target={ATTR_ENTITY_ID: "todo.einkauf"},
            blocking=True,
        )


@pytest.mark.usefixtures("mock_uuid")
async def test_update_item(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
) -> None:
    """Test update item."""

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        service_data={
            ATTR_ITEM: "b5d0790b-5f32-4d5c-91da-e29066f167de",
            ATTR_RENAME: "Paprika",
            ATTR_DESCRIPTION: "Rot",
        },
        target={ATTR_ENTITY_ID: "todo.einkauf"},
        blocking=True,
    )

    mock_bring_client.batch_update_list.assert_called_once_with(
        "e542eef6-dba7-4c31-a52c-29e6ab9d83a5",
        {
            "itemId": "Paprika",
            "spec": "Rot",
            "uuid": "b5d0790b-5f32-4d5c-91da-e29066f167de",
        },
        BringItemOperation.ADD,
    )


async def test_update_item_exception(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
) -> None:
    """Test update item with exception."""

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.LOADED

    mock_bring_client.batch_update_list.side_effect = BringRequestException
    with pytest.raises(
        HomeAssistantError, match="Failed to update item Paprika to Bring! list"
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            service_data={
                ATTR_ITEM: "b5d0790b-5f32-4d5c-91da-e29066f167de",
                ATTR_RENAME: "Paprika",
                ATTR_DESCRIPTION: "Rot",
            },
            target={ATTR_ENTITY_ID: "todo.einkauf"},
            blocking=True,
        )


@pytest.mark.usefixtures("mock_uuid")
async def test_rename_item(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
) -> None:
    """Test rename item."""

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        service_data={
            ATTR_ITEM: "b5d0790b-5f32-4d5c-91da-e29066f167de",
            ATTR_RENAME: "Gurke",
            ATTR_DESCRIPTION: "",
        },
        target={ATTR_ENTITY_ID: "todo.einkauf"},
        blocking=True,
    )

    mock_bring_client.batch_update_list.assert_called_once_with(
        "e542eef6-dba7-4c31-a52c-29e6ab9d83a5",
        [
            {
                "itemId": "Paprika",
                "spec": "",
                "uuid": "b5d0790b-5f32-4d5c-91da-e29066f167de",
                "operation": BringItemOperation.REMOVE,
            },
            {
                "itemId": "Gurke",
                "spec": "",
                "uuid": "b669ad23-606a-4652-b302-995d34b1cb1c",
                "operation": BringItemOperation.ADD,
            },
        ],
    )


async def test_rename_item_exception(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
) -> None:
    """Test rename item with exception."""

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.LOADED

    mock_bring_client.batch_update_list.side_effect = BringRequestException
    with pytest.raises(
        HomeAssistantError, match="Failed to rename item Gurke to Bring! list"
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            service_data={
                ATTR_ITEM: "b5d0790b-5f32-4d5c-91da-e29066f167de",
                ATTR_RENAME: "Gurke",
                ATTR_DESCRIPTION: "",
            },
            target={ATTR_ENTITY_ID: "todo.einkauf"},
            blocking=True,
        )


@pytest.mark.usefixtures("mock_uuid")
async def test_delete_items(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
) -> None:
    """Test delete item."""

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_ITEM,
        service_data={ATTR_ITEM: "b5d0790b-5f32-4d5c-91da-e29066f167de"},
        target={ATTR_ENTITY_ID: "todo.einkauf"},
        blocking=True,
    )

    mock_bring_client.batch_update_list.assert_called_once_with(
        "e542eef6-dba7-4c31-a52c-29e6ab9d83a5",
        [
            {
                "itemId": "b5d0790b-5f32-4d5c-91da-e29066f167de",
                "spec": "",
                "uuid": "b5d0790b-5f32-4d5c-91da-e29066f167de",
            },
        ],
        BringItemOperation.REMOVE,
    )


async def test_delete_items_exception(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
) -> None:
    """Test delete item."""

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.LOADED
    mock_bring_client.batch_update_list.side_effect = BringRequestException
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Failed to delete 1 item(s) from Bring! list"),
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.REMOVE_ITEM,
            service_data={ATTR_ITEM: "b5d0790b-5f32-4d5c-91da-e29066f167de"},
            target={ATTR_ENTITY_ID: "todo.einkauf"},
            blocking=True,
        )
