"""Unit tests for the OurGroceries todo platform."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.ourgroceries.coordinator import SCAN_INTERVAL
from homeassistant.components.todo import (
    ATTR_DESCRIPTION,
    ATTR_ITEM,
    ATTR_RENAME,
    ATTR_STATUS,
    DOMAIN as TODO_DOMAIN,
    TodoServices,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from . import items_to_shopping_list

from tests.common import async_fire_time_changed


def _mock_version_id(og: AsyncMock, version: int) -> None:
    og.get_my_lists.return_value["shoppingLists"][0]["versionId"] = str(version)


@pytest.mark.parametrize(
    ("items", "expected_state"),
    [
        ([], "0"),
        ([{"id": "12345", "name": "Soda"}], "1"),
        ([{"id": "12345", "name": "Soda", "crossedOffAt": 1699107501}], "0"),
        (
            [
                {"id": "12345", "name": "Soda"},
                {"id": "54321", "name": "Milk"},
            ],
            "2",
        ),
    ],
)
async def test_todo_item_state(
    hass: HomeAssistant,
    setup_integration: None,
    expected_state: str,
) -> None:
    """Test for a shopping list entity state."""

    state = hass.states.get("todo.test_list")
    assert state
    assert state.state == expected_state


async def test_add_todo_list_item(
    hass: HomeAssistant,
    setup_integration: None,
    ourgroceries: AsyncMock,
) -> None:
    """Test for adding an item."""

    state = hass.states.get("todo.test_list")
    assert state
    assert state.state == "0"

    ourgroceries.add_item_to_list = AsyncMock()
    # Fake API response when state is refreshed after create
    _mock_version_id(ourgroceries, 2)
    ourgroceries.get_list_items.return_value = items_to_shopping_list(
        [{"id": "12345", "name": "Soda"}],
        version_id="2",
    )

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ITEM: "Soda"},
        target={ATTR_ENTITY_ID: "todo.test_list"},
        blocking=True,
    )

    args = ourgroceries.add_item_to_list.call_args
    assert args
    assert args.args == ("test_list", "Soda")
    assert args.kwargs.get("auto_category") is True

    # Verify state is refreshed
    state = hass.states.get("todo.test_list")
    assert state
    assert state.state == "1"


@pytest.mark.parametrize(("items"), [[{"id": "12345", "name": "Soda"}]])
async def test_update_todo_item_status(
    hass: HomeAssistant,
    setup_integration: None,
    ourgroceries: AsyncMock,
) -> None:
    """Test for updating the completion status of an item."""

    state = hass.states.get("todo.test_list")
    assert state
    assert state.state == "1"

    ourgroceries.toggle_item_crossed_off = AsyncMock()

    # Fake API response when state is refreshed after crossing off
    _mock_version_id(ourgroceries, 2)
    ourgroceries.get_list_items.return_value = items_to_shopping_list(
        [{"id": "12345", "name": "Soda", "crossedOffAt": 1699107501}]
    )

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "12345", ATTR_STATUS: "completed"},
        target={ATTR_ENTITY_ID: "todo.test_list"},
        blocking=True,
    )
    assert ourgroceries.toggle_item_crossed_off.called
    args = ourgroceries.toggle_item_crossed_off.call_args
    assert args
    assert args.args == ("test_list", "12345")
    assert args.kwargs.get("cross_off") is True

    # Verify state is refreshed
    state = hass.states.get("todo.test_list")
    assert state
    assert state.state == "0"

    # Fake API response when state is refreshed after reopen
    _mock_version_id(ourgroceries, 2)
    ourgroceries.get_list_items.return_value = items_to_shopping_list(
        [{"id": "12345", "name": "Soda"}]
    )

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "12345", ATTR_STATUS: "needs_action"},
        target={ATTR_ENTITY_ID: "todo.test_list"},
        blocking=True,
    )
    assert ourgroceries.toggle_item_crossed_off.called
    args = ourgroceries.toggle_item_crossed_off.call_args
    assert args
    assert args.args == ("test_list", "12345")
    assert args.kwargs.get("cross_off") is False

    # Verify state is refreshed
    state = hass.states.get("todo.test_list")
    assert state
    assert state.state == "1"


@pytest.mark.parametrize(
    ("items", "category"),
    [
        (
            [{"id": "12345", "name": "Soda", "categoryId": "test_category"}],
            "test_category",
        ),
        ([{"id": "12345", "name": "Uncategorized"}], "uncategorized"),
    ],
)
async def test_update_todo_item_summary(
    hass: HomeAssistant,
    setup_integration: None,
    ourgroceries: AsyncMock,
    category: str | None,
) -> None:
    """Test for updating an item summary."""

    state = hass.states.get("todo.test_list")
    assert state
    assert state.state == "1"

    ourgroceries.change_item_on_list = AsyncMock()

    # Fake API response when state is refreshed update
    _mock_version_id(ourgroceries, 2)
    ourgroceries.get_list_items.return_value = items_to_shopping_list(
        [{"id": "12345", "name": "Milk"}]
    )

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "12345", ATTR_RENAME: "Milk"},
        target={ATTR_ENTITY_ID: "todo.test_list"},
        blocking=True,
    )
    assert ourgroceries.change_item_on_list
    args = ourgroceries.change_item_on_list.call_args
    assert args.args == ("test_list", "12345", category, "Milk")


@pytest.mark.parametrize(
    ("items"),
    [
        [
            {"id": "12345", "name": "Soda"},
            {"id": "54321", "name": "Milk"},
        ]
    ],
)
async def test_remove_todo_item(
    hass: HomeAssistant,
    setup_integration: None,
    ourgroceries: AsyncMock,
) -> None:
    """Test for removing an item."""

    state = hass.states.get("todo.test_list")
    assert state
    assert state.state == "2"

    ourgroceries.remove_item_from_list = AsyncMock()
    # Fake API response when state is refreshed after remove
    _mock_version_id(ourgroceries, 2)
    ourgroceries.get_list_items.return_value = items_to_shopping_list([])

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_ITEM,
        {ATTR_ITEM: ["12345", "54321"]},
        target={ATTR_ENTITY_ID: "todo.test_list"},
        blocking=True,
    )
    assert ourgroceries.remove_item_from_list.call_count == 2
    args = ourgroceries.remove_item_from_list.call_args_list
    assert args[0].args == ("test_list", "12345")
    assert args[1].args == ("test_list", "54321")

    await async_update_entity(hass, "todo.test_list")
    state = hass.states.get("todo.test_list")
    assert state
    assert state.state == "0"


async def test_version_id_optimization(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_integration: None,
    ourgroceries: AsyncMock,
) -> None:
    """Test that list items aren't being retrieved if version id stays the same."""
    state = hass.states.get("todo.test_list")
    assert state.state == "0"
    assert ourgroceries.get_list_items.call_count == 1
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("todo.test_list")
    assert state.state == "0"
    assert ourgroceries.get_list_items.call_count == 1


@pytest.mark.parametrize(
    ("exception"),
    [
        (ClientError),
        (TimeoutError),
    ],
)
async def test_coordinator_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_integration: None,
    ourgroceries: AsyncMock,
    exception: Exception,
) -> None:
    """Test error on coordinator update."""
    state = hass.states.get("todo.test_list")
    assert state.state == "0"

    _mock_version_id(ourgroceries, 2)
    ourgroceries.get_list_items.side_effect = exception
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("todo.test_list")
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("items", "expected_descriptions"),
    [
        (
            [{"id": "12345", "name": "Soda", "categoryId": "test_category"}],
            ["Test Category"],
        ),
        (
            [{"id": "12345", "name": "Soda"}],
            [None],
        ),
        (
            [
                {"id": "1", "name": "A", "categoryId": "test_category"},
                {"id": "2", "name": "B", "categoryId": "other_category"},
            ],
            ["Other Category", "Test Category"],
        ),
    ],
)
async def test_todo_item_category_description(
    hass: HomeAssistant,
    setup_integration: None,
    expected_descriptions: list[str | None],
) -> None:
    """Test that category names are shown as item descriptions."""
    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {},
        target={ATTR_ENTITY_ID: "todo.test_list"},
        blocking=True,
        return_response=True,
    )
    items = result["todo.test_list"]["items"]
    assert [item.get("description") for item in items] == expected_descriptions


@pytest.mark.parametrize(
    "items",
    [
        [
            {"id": "1", "name": "A", "categoryId": "test_category"},
            {"id": "2", "name": "B", "categoryId": "other_category"},
            {"id": "3", "name": "C"},
        ],
    ],
)
async def test_todo_items_sorted_by_category(
    hass: HomeAssistant,
    setup_integration: None,
) -> None:
    """Test that items are sorted by category sort order."""
    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {},
        target={ATTR_ENTITY_ID: "todo.test_list"},
        blocking=True,
        return_response=True,
    )
    items = result["todo.test_list"]["items"]
    summaries = [item["summary"] for item in items]
    # "B" has "other_category" (sort "A"), "A" has "test_category" (sort "B"),
    # "C" has no category (sorts last)
    assert summaries == ["B", "A", "C"]


@pytest.mark.parametrize(
    "items",
    [[{"id": "12345", "name": "Soda", "categoryId": "test_category"}]],
)
async def test_update_todo_item_description_existing_category(
    hass: HomeAssistant,
    setup_integration: None,
    ourgroceries: AsyncMock,
) -> None:
    """Test updating an item's description to an existing category."""
    ourgroceries.change_item_on_list = AsyncMock()
    _mock_version_id(ourgroceries, 2)
    ourgroceries.get_list_items.return_value = items_to_shopping_list(
        [{"id": "12345", "name": "Soda", "categoryId": "other_category"}],
        version_id="2",
    )

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "12345", ATTR_DESCRIPTION: "Other Category"},
        target={ATTR_ENTITY_ID: "todo.test_list"},
        blocking=True,
    )
    assert ourgroceries.change_item_on_list.called
    args = ourgroceries.change_item_on_list.call_args
    assert args.args == ("test_list", "12345", "other_category", "Soda")
    ourgroceries.create_category.assert_not_called()


@pytest.mark.parametrize(
    "items",
    [[{"id": "12345", "name": "Soda", "categoryId": "test_category"}]],
)
async def test_update_todo_item_description_new_category(
    hass: HomeAssistant,
    setup_integration: None,
    ourgroceries: AsyncMock,
) -> None:
    """Test updating an item's description creates a new category."""
    ourgroceries.change_item_on_list = AsyncMock()
    ourgroceries.create_category = AsyncMock()
    # After create_category, the refresh returns the new category
    ourgroceries.get_category_items.return_value = {
        "list": {
            "items": [
                {"id": "test_category", "name": "Test Category", "sortOrder": "B"},
                {"id": "other_category", "name": "Other Category", "sortOrder": "A"},
                {"id": "new_cat_id", "name": "New Category", "sortOrder": "C"},
            ]
        }
    }
    _mock_version_id(ourgroceries, 2)
    ourgroceries.get_list_items.return_value = items_to_shopping_list(
        [{"id": "12345", "name": "Soda", "categoryId": "new_cat_id"}],
        version_id="2",
    )

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "12345", ATTR_DESCRIPTION: "New Category"},
        target={ATTR_ENTITY_ID: "todo.test_list"},
        blocking=True,
    )
    ourgroceries.create_category.assert_called_once_with("New Category")
    assert ourgroceries.change_item_on_list.called
    args = ourgroceries.change_item_on_list.call_args
    assert args.args == ("test_list", "12345", "new_cat_id", "Soda")


@pytest.mark.parametrize(
    "items",
    [[{"id": "12345", "name": "Soda", "categoryId": "test_category"}]],
)
async def test_update_todo_item_clear_description(
    hass: HomeAssistant,
    setup_integration: None,
    ourgroceries: AsyncMock,
) -> None:
    """Test clearing an item's description sets uncategorized."""
    ourgroceries.change_item_on_list = AsyncMock()
    _mock_version_id(ourgroceries, 2)
    ourgroceries.get_list_items.return_value = items_to_shopping_list(
        [{"id": "12345", "name": "Soda"}],
        version_id="2",
    )

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "12345", ATTR_DESCRIPTION: ""},
        target={ATTR_ENTITY_ID: "todo.test_list"},
        blocking=True,
    )
    assert ourgroceries.change_item_on_list.called
    args = ourgroceries.change_item_on_list.call_args
    assert args.args == ("test_list", "12345", "uncategorized", "Soda")
