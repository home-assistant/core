"""Tests for the Mealie todo."""

from datetime import timedelta
import json
from unittest.mock import AsyncMock, call, patch

from aiomealie import (
    MealieError,
    MutateShoppingItem,
    ShoppingItemsResponse,
    ShoppingListsResponse,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.mealie import DOMAIN
from homeassistant.components.todo import (
    ATTR_DESCRIPTION,
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
    async_load_fixture,
    snapshot_platform,
)
from tests.typing import WebSocketGenerator

ENTITY_SUPERMARKET = "todo.mealie_supermarket"


async def _get_items(
    hass_ws_client: WebSocketGenerator, entity_id: str
) -> list[dict[str, str]]:
    """Fetch todo items for an entity through the websocket API."""
    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "todo/item/list", "entity_id": entity_id})
    resp = await client.receive_json()
    assert resp["success"]
    return resp["result"]["items"]


async def test_todo_items_split_name_and_description(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test items expose the name as summary and quantity/unit/note as description."""
    await setup_integration(hass, mock_config_entry)

    items = await _get_items(hass_ws_client, ENTITY_SUPERMARKET)

    assert [(item["summary"], item.get("description")) for item in items] == [
        ("Apples", "2"),
        ("acorn squash", "1 can"),
        ("aubergine", None),
        ("flour", "1 US cup"),
    ]


@pytest.mark.parametrize(
    ("description", "expected_quantity", "expected_note"),
    [
        pytest.param("3 can, organic", 3.0, "organic", id="quantity_unit_note"),
        pytest.param("2", 2.0, "", id="quantity_only"),
        pytest.param("2.5", 2.5, "", id="fractional_quantity"),
        pytest.param("2 Gramm", 2.0, "", id="quantity_and_unit"),
        pytest.param(", organic", 0.0, "organic", id="note_only_with_comma"),
        pytest.param("buy fresh", 0.0, "buy fresh", id="text_note_no_comma"),
        pytest.param(
            "buy fresh, organic", 0.0, "buy fresh, organic", id="text_note_with_comma"
        ),
        pytest.param("1 can, ripe", 1.0, "ripe", id="quantity_unit_note_short"),
    ],
)
async def test_update_food_item_description(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    description: str,
    expected_quantity: float,
    expected_note: str,
) -> None:
    """Test editing a food item's description updates its quantity and note."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "acorn squash", ATTR_DESCRIPTION: description},
        target={ATTR_ENTITY_ID: ENTITY_SUPERMARKET},
        blocking=True,
    )

    mock_mealie_client.update_shopping_item.assert_called_once()
    _, mutate = mock_mealie_client.update_shopping_item.call_args[0]
    assert mutate.quantity == expected_quantity
    assert mutate.note == expected_note


async def test_update_nonfood_item_description(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test editing a non-food item's description updates quantity but keeps the note."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "Apples", ATTR_DESCRIPTION: "5"},
        target={ATTR_ENTITY_ID: ENTITY_SUPERMARKET},
        blocking=True,
    )

    mock_mealie_client.update_shopping_item.assert_called_once()
    _, mutate = mock_mealie_client.update_shopping_item.call_args[0]
    assert mutate.quantity == 5.0
    assert mutate.note == "Apples"


async def test_create_item_with_description(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating an item derives the quantity from the description."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ITEM: "Soda", ATTR_DESCRIPTION: "6"},
        target={ATTR_ENTITY_ID: ENTITY_SUPERMARKET},
        blocking=True,
    )

    mock_mealie_client.add_shopping_item.assert_called_once()
    (mutate,) = mock_mealie_client.add_shopping_item.call_args[0]
    assert mutate.note == "Soda"
    assert mutate.quantity == 6.0


async def test_update_todo_item_status_keeps_description(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test toggling status does not rewrite quantity/note from the rendered description.

    Uses a food item whose note starts with a digit so that parsing the description
    back would return a different (quantity, note) pair — proving the
    unchanged-description guard is load-bearing and not just incidentally passing.
    """
    items_data = json.loads(
        await async_load_fixture(hass, "get_shopping_items.json", DOMAIN)
    )
    items_data["items"][1]["quantity"] = 0.0
    items_data["items"][1]["note"] = "3 large"
    items_data["items"][1]["unit"] = None
    items_data["items"][1]["unitId"] = None
    mock_mealie_client.get_shopping_items.return_value = (
        ShoppingItemsResponse.from_json(json.dumps(items_data))
    )

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "acorn squash", ATTR_STATUS: "completed"},
        target={ATTR_ENTITY_ID: ENTITY_SUPERMARKET},
        blocking=True,
    )

    mock_mealie_client.update_shopping_item.assert_called_once()
    _, mutate = mock_mealie_client.update_shopping_item.call_args[0]
    assert mutate.checked is True
    assert mutate.quantity == 0.0
    assert mutate.note == "3 large"
    assert mutate.unit_id is None


async def test_update_todo_item_nonfood_status_keeps_quantity(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test toggling status on a non-food item does not reset its quantity.

    A status toggle re-sends the rendered description, which for a non-food item
    matches its quantity; the unchanged-description guard must keep the quantity
    and note intact.
    """
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "Apples", ATTR_STATUS: "completed"},
        target={ATTR_ENTITY_ID: ENTITY_SUPERMARKET},
        blocking=True,
    )

    mock_mealie_client.update_shopping_item.assert_called_once()
    _, mutate = mock_mealie_client.update_shopping_item.call_args[0]
    assert mutate.checked is True
    assert mutate.quantity == 2.0
    assert mutate.note == "Apples"


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

    assert mock_mealie_client.update_shopping_item.call_count == 4
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
        await async_load_fixture(hass, "get_shopping_lists.json", DOMAIN)
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
