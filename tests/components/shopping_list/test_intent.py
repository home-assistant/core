"""Test Shopping List intents."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent


async def test_complete_item_intent(hass: HomeAssistant, sl_setup) -> None:
    """Test complete item."""
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "soda"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )

    response = await intent.async_handle(
        hass, "test", "HassShoppingListCompleteItem", {"item": {"value": "beer"}}
    )

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    completed_items = response.speech_slots.get("completed_items")
    assert len(completed_items) == 2
    assert completed_items[0]["name"] == "beer"
    assert hass.data["shopping_list"].items[1]["complete"]
    assert hass.data["shopping_list"].items[2]["complete"]

    # Complete again
    response = await intent.async_handle(
        hass, "test", "HassShoppingListCompleteItem", {"item": {"value": "beer"}}
    )

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.speech_slots.get("completed_items") == []
    assert hass.data["shopping_list"].items[1]["complete"]
    assert hass.data["shopping_list"].items[2]["complete"]


async def test_complete_item_intent_not_found(hass: HomeAssistant, sl_setup) -> None:
    """Test completing a missing item."""
    response = await intent.async_handle(
        hass, "test", "HassShoppingListCompleteItem", {"item": {"value": "beer"}}
    )
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
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
