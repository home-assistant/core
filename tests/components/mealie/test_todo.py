"""Tests for the Mealie todo."""

from datetime import timedelta
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
from homeassistant.components.mealie.todo import _convert_api_item, _parse_description
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
    async_load_fixture,
    load_fixture,
    snapshot_platform,
)
from tests.typing import WebSocketGenerator


@pytest.mark.parametrize(
    ("item_index", "expected_summary", "expected_description"),
    [
        pytest.param(0, "2 Apples", None, id="non_food_keeps_display"),
        pytest.param(1, "acorn squash", "1 can", id="food_with_unit"),
        pytest.param(2, "aubergine", None, id="food_no_quantity"),
        pytest.param(3, "flour", "1 US cup", id="food_with_quantity_and_unit"),
    ],
)
def test_convert_api_item(
    item_index: int,
    expected_summary: str,
    expected_description: str | None,
) -> None:
    """Test _convert_api_item splits food name into summary and quantity/unit into description."""
    items = ShoppingItemsResponse.from_json(
        load_fixture("get_shopping_items.json", DOMAIN)
    ).items

    todo = _convert_api_item(items[item_index])

    assert todo.summary == expected_summary
    assert todo.description == expected_description


@pytest.mark.parametrize(
    ("description", "expected_quantity", "expected_note"),
    [
        pytest.param(None, 0.0, "", id="none"),
        pytest.param("", 0.0, "", id="empty"),
        pytest.param("2", 2.0, "", id="quantity_only"),
        pytest.param("2.5", 2.5, "", id="fractional_quantity"),
        pytest.param("2 Gramm", 2.0, "", id="quantity_and_unit"),
        pytest.param("2 Gramm, organic", 2.0, "organic", id="quantity_unit_note"),
        pytest.param(", organic", 0.0, "organic", id="note_only_with_comma"),
        pytest.param("buy fresh", 0.0, "buy fresh", id="text_note_no_comma"),
        pytest.param("1 can, ripe", 1.0, "ripe", id="quantity_unit_note_short"),
    ],
)
def test_parse_description(
    description: str | None,
    expected_quantity: float,
    expected_note: str,
) -> None:
    """Test _parse_description extracts quantity and note from a description string."""
    quantity, note = _parse_description(description)

    assert quantity == expected_quantity
    assert note == expected_note


async def test_update_todo_item_description(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test updating description on a food item updates quantity and note."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ITEM: "acorn squash",
            ATTR_RENAME: "acorn squash",
            "description": "3 can, organic",
        },
        target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
        blocking=True,
    )

    mock_mealie_client.update_shopping_item.assert_called_once()
    _, mutate = mock_mealie_client.update_shopping_item.call_args[0]
    assert mutate.quantity == 3.0
    assert mutate.note == "organic"


async def test_update_todo_item_status_keeps_description(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test toggling status does not rewrite quantity/note from the rendered description.

    The todo component re-sends the rendered description on every update; parsing it
    back must be skipped when it is unchanged to avoid clobbering the Mealie item.
    """
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "acorn squash", ATTR_STATUS: "completed"},
        target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
        blocking=True,
    )

    mock_mealie_client.update_shopping_item.assert_called_once()
    _, mutate = mock_mealie_client.update_shopping_item.call_args[0]
    assert mutate.checked is True
    assert mutate.quantity == 1.0
    assert mutate.note == ""
    assert mutate.unit_id == "7bf539d4-fc78-48bc-b48e-c35ccccec34a"


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
