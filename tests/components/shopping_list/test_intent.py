"""Test Shopping List intents."""

from homeassistant.components.shopping_list.common import _get_shopping_data
from homeassistant.components.shopping_list.const import EVENT_SHOPPING_LIST_UPDATED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from tests.common import async_capture_events


async def test_add_item_intent_reactivates_first_completed_match(
    hass: HomeAssistant, sl_setup: None
) -> None:
    """Test reactivating the first completed matching item."""
    shopping_data = _get_shopping_data(hass)
    first_item = await shopping_data.async_add("Beer", complete=True)
    second_item = await shopping_data.async_add("BEER", complete=True)
    first_item_id = first_item["id"]
    second_item_id = second_item["id"]
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)

    response = await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )

    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(shopping_data.items) == 2
    assert shopping_data.items[0]["id"] == first_item_id
    assert shopping_data.items[0]["name"] == "Beer"
    assert shopping_data.items[0]["complete"] is False
    assert shopping_data.items[1]["id"] == second_item_id
    assert shopping_data.items[1]["complete"] is True
    assert len(events) == 1
    assert events[0].data["action"] == "update"


async def test_add_item_intent_keeps_existing_active_match(
    hass: HomeAssistant, sl_setup: None
) -> None:
    """Test keeping an existing active matching item."""
    shopping_data = _get_shopping_data(hass)
    completed_item = await shopping_data.async_add("Beer", complete=True)
    active_item = await shopping_data.async_add("BEER")
    completed_item_id = completed_item["id"]
    active_item_id = active_item["id"]
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)

    response = await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )

    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(shopping_data.items) == 2
    assert shopping_data.items[0]["id"] == completed_item_id
    assert shopping_data.items[0]["complete"] is True
    assert shopping_data.items[1]["id"] == active_item_id
    assert shopping_data.items[1]["complete"] is False
    assert not events


async def test_complete_item_intent(hass: HomeAssistant, sl_setup) -> None:
    """Test complete item."""
    shopping_data = _get_shopping_data(hass)
    await shopping_data.async_add("soda")
    await shopping_data.async_add("beer")
    await shopping_data.async_add("beer")
    await shopping_data.async_add("wine")

    response = await intent.async_handle(
        hass, "test", "HassShoppingListCompleteItem", {"item": {"value": "beer"}}
    )

    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    completed_items = response.speech_slots.get("completed_items")
    assert len(completed_items) == 2
    assert completed_items[0]["name"] == "beer"
    assert shopping_data.items[1]["complete"]
    assert shopping_data.items[2]["complete"]

    # Complete again
    response = await intent.async_handle(
        hass, "test", "HassShoppingListCompleteItem", {"item": {"value": "beer"}}
    )

    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert response.speech_slots.get("completed_items") == []
    assert shopping_data.items[1]["complete"]
    assert shopping_data.items[2]["complete"]


async def test_complete_item_intent_not_found(hass: HomeAssistant, sl_setup) -> None:
    """Test completing a missing item."""
    response = await intent.async_handle(
        hass, "test", "HassShoppingListCompleteItem", {"item": {"value": "beer"}}
    )
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert response.speech_slots.get("completed_items") == []


async def test_recent_items_intent(hass: HomeAssistant, sl_setup) -> None:
    """Test recent items."""
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "soda"}}
    )

    response = await intent.async_handle(hass, "test", "HassShoppingListLastItems")

    assert (
        response.speech["plain"]["speech"]
        == "These are the top 3 items on your shopping list: soda, wine, beer"
    )


async def test_recent_items_intent_no_items(hass: HomeAssistant, sl_setup) -> None:
    """Test recent items."""
    response = await intent.async_handle(hass, "test", "HassShoppingListLastItems")

    assert (
        response.speech["plain"]["speech"] == "There are no items on your shopping list"
    )
