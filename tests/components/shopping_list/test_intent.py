"""Test Shopping List intents."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent


async def test_complete_item_intent(hass: HomeAssistant, sl_setup) -> None:
    """Test complete item."""
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )

    response = await intent.async_handle(
        hass, "test", "HassShoppingListCompleteItem", {"item": {"value": "beer"}}
    )

    assert response.response_type == intent.IntentResponseType.ACTION_DONE

    assert hass.data["shopping_list"].items[0]["complete"]


async def test_complete_item_intent_not_found(hass: HomeAssistant, sl_setup) -> None:
    """Test complete item."""
    response = await intent.async_handle(
        hass, "test", "HassShoppingListCompleteItem", {"item": {"value": "beer"}}
    )

    assert (
        response.speech["plain"]["speech"]
        == "Item beer not found on your shopping list"
    )


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
