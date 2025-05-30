"""Tests for the Mealie todo."""

from datetime import timedelta
from unittest.mock import AsyncMock, call, patch

from aiomealie import MealieError, MutateShoppingItem, ShoppingListsResponse
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.mealie import DOMAIN
from homeassistant.components.todo import (
    ATTR_ITEM,
    ATTR_RENAME,
    ATTR_STATUS,
    DOMAIN as TODO_DOMAIN,
    TodoServices,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_fixture,
    snapshot_platform,
)
from tests.typing import WebSocketGenerator


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test todo entities."""
    with patch("homeassistant.components.mealie.PLATFORMS", [Platform.TODO]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "data", "method"),
    [
        (TodoServices.ADD_ITEM, {ATTR_ITEM: "Soda"}, "add_shopping_item"),
        (
            TodoServices.UPDATE_ITEM,
            {ATTR_ITEM: "aubergine", ATTR_RENAME: "Eggplant", ATTR_STATUS: "completed"},
            "update_shopping_item",
        ),
        (TodoServices.REMOVE_ITEM, {ATTR_ITEM: "aubergine"}, "delete_shopping_item"),
    ],
)
async def test_todo_actions(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    data: dict[str, str],
    method: str,
) -> None:
    """Test todo actions."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        service,
        data,
        target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
        blocking=True,
    )

    getattr(mock_mealie_client, method).assert_called_once()


async def test_add_todo_list_item_error(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for failing to add a To-do Item."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.add_shopping_item.side_effect = MealieError

    with pytest.raises(
        HomeAssistantError, match="An error occurred adding an item to Supermarket"
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.ADD_ITEM,
            {ATTR_ITEM: "Soda"},
            target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
            blocking=True,
        )


async def test_update_todo_list_item_error(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for failing to update a To-do Item."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.update_shopping_item.side_effect = MealieError

    with pytest.raises(
        HomeAssistantError, match="An error occurred updating an item in Supermarket"
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            {ATTR_ITEM: "aubergine", ATTR_RENAME: "Eggplant", ATTR_STATUS: "completed"},
            target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
            blocking=True,
        )


async def test_update_non_existent_item(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for updating a non-existent To-do Item."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        ServiceValidationError, match="Unable to find to-do list item: eggplant"
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            {ATTR_ITEM: "eggplant", ATTR_RENAME: "Aubergine", ATTR_STATUS: "completed"},
            target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
            blocking=True,
        )


async def test_delete_todo_list_item_error(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for failing to delete a To-do Item."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.delete_shopping_item = AsyncMock()
    mock_mealie_client.delete_shopping_item.side_effect = MealieError

    with pytest.raises(
        HomeAssistantError, match="An error occurred deleting an item in Supermarket"
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.REMOVE_ITEM,
            {ATTR_ITEM: "aubergine"},
            target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
            blocking=True,
        )


async def test_moving_todo_item(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test for moving a To-do Item to place."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "todo/item/move",
            "entity_id": "todo.mealie_supermarket",
            "uid": "f45430f7-3edf-45a9-a50f-73bb375090be",
            "previous_uid": "84d8fd74-8eb0-402e-84b6-71f251bfb7cc",
        }
    )
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("success")
    assert resp.get("result") is None

    assert mock_mealie_client.update_shopping_item.call_count == 3
    calls = mock_mealie_client.update_shopping_item.mock_calls

    assert calls[0] == call(
        "84d8fd74-8eb0-402e-84b6-71f251bfb7cc",
        MutateShoppingItem(
            item_id="84d8fd74-8eb0-402e-84b6-71f251bfb7cc",
            list_id="9ce096fe-ded2-4077-877d-78ba450ab13e",
            note="",
            display=None,
            checked=False,
            position=0,
            is_food=True,
            disable_amount=None,
            quantity=1.0,
            label_id=None,
            food_id="09322430-d24c-4b1a-abb6-22b6ed3a88f5",
            unit_id="7bf539d4-fc78-48bc-b48e-c35ccccec34a",
        ),
    )

    assert calls[1] == call(
        "f45430f7-3edf-45a9-a50f-73bb375090be",
        MutateShoppingItem(
            item_id="f45430f7-3edf-45a9-a50f-73bb375090be",
            list_id="9ce096fe-ded2-4077-877d-78ba450ab13e",
            note="Apples",
            display=None,
            checked=False,
            position=1,
            is_food=False,
            disable_amount=None,
            quantity=2.0,
            label_id=None,
            food_id=None,
            unit_id=None,
        ),
    )

    assert calls[2] == call(
        "69913b9a-7c75-4935-abec-297cf7483f88",
        MutateShoppingItem(
            item_id="69913b9a-7c75-4935-abec-297cf7483f88",
            list_id="9ce096fe-ded2-4077-877d-78ba450ab13e",
            note="",
            display=None,
            checked=False,
            position=2,
            is_food=True,
            disable_amount=None,
            quantity=0.0,
            label_id=None,
            food_id="96801494-4e26-4148-849a-8155deb76327",
            unit_id=None,
        ),
    )


async def test_not_moving_todo_item(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test for moving a To-do Item to the same place."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "todo/item/move",
            "entity_id": "todo.mealie_supermarket",
            "uid": "f45430f7-3edf-45a9-a50f-73bb375090be",
            "previous_uid": "f45430f7-3edf-45a9-a50f-73bb375090be",
        }
    )
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("success")
    assert resp.get("result") is None

    assert mock_mealie_client.update_shopping_item.call_count == 0


async def test_moving_todo_item_invalid_uid(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test for moving a To-do Item to place with invalid UID."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "todo/item/move",
            "entity_id": "todo.mealie_supermarket",
            "uid": "cheese",
        }
    )
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("success") is False
    assert resp.get("result") is None
    assert resp["error"]["code"] == "failed"
    assert resp["error"]["message"] == "Item cheese not found"

    assert mock_mealie_client.update_shopping_item.call_count == 0


async def test_moving_todo_item_invalid_previous_uid(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test for moving a To-do Item to place with invalid previous UID."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "todo/item/move",
            "entity_id": "todo.mealie_supermarket",
            "uid": "f45430f7-3edf-45a9-a50f-73bb375090be",
            "previous_uid": "cheese",
        }
    )
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("success") is False
    assert resp.get("result") is None
    assert resp["error"]["code"] == "failed"
    assert resp["error"]["message"] == "Item cheese not found"

    assert mock_mealie_client.update_shopping_item.call_count == 0


async def test_runtime_management(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test for creating and deleting shopping lists."""
    response = ShoppingListsResponse.from_json(
        load_fixture("get_shopping_lists.json", DOMAIN)
    ).items
    mock_mealie_client.get_shopping_lists.return_value = ShoppingListsResponse(
        items=[response[0]]
    )
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("todo.mealie_supermarket") is not None
    assert hass.states.get("todo.mealie_special_groceries") is None

    mock_mealie_client.get_shopping_lists.return_value = ShoppingListsResponse(
        items=response[0:2]
    )
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("todo.mealie_special_groceries") is not None

    mock_mealie_client.get_shopping_lists.return_value = ShoppingListsResponse(
        items=[response[0]]
    )
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("todo.mealie_special_groceries") is None
