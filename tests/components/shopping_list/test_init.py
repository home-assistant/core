"""Test shopping list component."""

from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.const import HTTP_NOT_FOUND
from homeassistant.helpers import intent


async def test_add_item(hass, sl_setup):
    """Test adding an item intent."""

    response = await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )

    assert response.speech["plain"]["speech"] == "I've added beer to your shopping list"


async def test_recent_items_intent(hass, sl_setup):
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


async def test_deprecated_api_get_all(hass, hass_client, sl_setup):
    """Test the API."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )

    client = await hass_client()
    resp = await client.get("/api/shopping_list")

    assert resp.status == 200
    data = await resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "beer"
    assert not data[0]["complete"]
    assert data[1]["name"] == "wine"
    assert not data[1]["complete"]


async def test_ws_get_items(hass, hass_ws_client, sl_setup):
    """Test get shopping_list items websocket command."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )

    client = await hass_ws_client(hass)

    await client.send_json({"id": 5, "type": "shopping_list/items"})
    msg = await client.receive_json()
    assert msg["success"] is True

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    data = msg["result"]
    assert len(data) == 2
    assert data[0]["name"] == "beer"
    assert not data[0]["complete"]
    assert data[1]["name"] == "wine"
    assert not data[1]["complete"]


async def test_deprecated_api_update(hass, hass_client, sl_setup):
    """Test the API."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )

    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]

    client = await hass_client()
    resp = await client.post(
        f"/api/shopping_list/item/{beer_id}", json={"name": "soda"}
    )

    assert resp.status == 200
    data = await resp.json()
    assert data == {"id": beer_id, "name": "soda", "complete": False}

    resp = await client.post(
        f"/api/shopping_list/item/{wine_id}", json={"complete": True}
    )

    assert resp.status == 200
    data = await resp.json()
    assert data == {"id": wine_id, "name": "wine", "complete": True}

    beer, wine = hass.data["shopping_list"].items
    assert beer == {"id": beer_id, "name": "soda", "complete": False}
    assert wine == {"id": wine_id, "name": "wine", "complete": True}


async def test_ws_update_item(hass, hass_ws_client, sl_setup):
    """Test update shopping_list item websocket command."""
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )

    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "shopping_list/items/update",
            "item_id": beer_id,
            "name": "soda",
        }
    )
    msg = await client.receive_json()
    assert msg["success"] is True
    data = msg["result"]
    assert data == {"id": beer_id, "name": "soda", "complete": False}
    await client.send_json(
        {
            "id": 6,
            "type": "shopping_list/items/update",
            "item_id": wine_id,
            "complete": True,
        }
    )
    msg = await client.receive_json()
    assert msg["success"] is True
    data = msg["result"]
    assert data == {"id": wine_id, "name": "wine", "complete": True}

    beer, wine = hass.data["shopping_list"].items
    assert beer == {"id": beer_id, "name": "soda", "complete": False}
    assert wine == {"id": wine_id, "name": "wine", "complete": True}


async def test_api_update_fails(hass, hass_client, sl_setup):
    """Test the API."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )

    client = await hass_client()
    resp = await client.post("/api/shopping_list/non_existing", json={"name": "soda"})

    assert resp.status == HTTP_NOT_FOUND

    beer_id = hass.data["shopping_list"].items[0]["id"]
    resp = await client.post(f"/api/shopping_list/item/{beer_id}", json={"name": 123})

    assert resp.status == 400


async def test_ws_update_item_fail(hass, hass_ws_client, sl_setup):
    """Test failure of update shopping_list item websocket command."""
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "shopping_list/items/update",
            "item_id": "non_existing",
            "name": "soda",
        }
    )
    msg = await client.receive_json()
    assert msg["success"] is False
    data = msg["error"]
    assert data == {"code": "item_not_found", "message": "Item not found"}
    await client.send_json({"id": 6, "type": "shopping_list/items/update", "name": 123})
    msg = await client.receive_json()
    assert msg["success"] is False


async def test_deprecated_api_clear_completed(hass, hass_client, sl_setup):
    """Test the API."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )

    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]

    client = await hass_client()

    # Mark beer as completed
    resp = await client.post(
        f"/api/shopping_list/item/{beer_id}", json={"complete": True}
    )
    assert resp.status == 200

    resp = await client.post("/api/shopping_list/clear_completed")
    assert resp.status == 200

    items = hass.data["shopping_list"].items
    assert len(items) == 1

    assert items[0] == {"id": wine_id, "name": "wine", "complete": False}


async def test_ws_clear_items(hass, hass_ws_client, sl_setup):
    """Test clearing shopping_list items websocket command."""
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )
    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "shopping_list/items/update",
            "item_id": beer_id,
            "complete": True,
        }
    )
    msg = await client.receive_json()
    assert msg["success"] is True
    await client.send_json({"id": 6, "type": "shopping_list/items/clear"})
    msg = await client.receive_json()
    assert msg["success"] is True
    items = hass.data["shopping_list"].items
    assert len(items) == 1
    assert items[0] == {"id": wine_id, "name": "wine", "complete": False}


async def test_deprecated_api_create(hass, hass_client, sl_setup):
    """Test the API."""

    client = await hass_client()
    resp = await client.post("/api/shopping_list/item", json={"name": "soda"})

    assert resp.status == 200
    data = await resp.json()
    assert data["name"] == "soda"
    assert data["complete"] is False

    items = hass.data["shopping_list"].items
    assert len(items) == 1
    assert items[0]["name"] == "soda"
    assert items[0]["complete"] is False


async def test_deprecated_api_create_fail(hass, hass_client, sl_setup):
    """Test the API."""

    client = await hass_client()
    resp = await client.post("/api/shopping_list/item", json={"name": 1234})

    assert resp.status == 400
    assert len(hass.data["shopping_list"].items) == 0


async def test_ws_add_item(hass, hass_ws_client, sl_setup):
    """Test adding shopping_list item websocket command."""
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "shopping_list/items/add", "name": "soda"})
    msg = await client.receive_json()
    assert msg["success"] is True
    data = msg["result"]
    assert data["name"] == "soda"
    assert data["complete"] is False
    items = hass.data["shopping_list"].items
    assert len(items) == 1
    assert items[0]["name"] == "soda"
    assert items[0]["complete"] is False


async def test_ws_add_item_fail(hass, hass_ws_client, sl_setup):
    """Test adding shopping_list item failure websocket command."""
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "shopping_list/items/add", "name": 123})
    msg = await client.receive_json()
    assert msg["success"] is False
    assert len(hass.data["shopping_list"].items) == 0


async def test_api_move_up_down_item_basic(hass, hass_client, sl_setup):
    """Test moving up and down shopping_list item API."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )
    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]

    client = await hass_client()

    resp = await client.post(f"/api/shopping_list/item/{wine_id}/move_up")
    assert resp.status == 200
    assert hass.data["shopping_list"].items[0]["id"] == wine_id
    assert hass.data["shopping_list"].items[0]["name"] == "wine"
    assert hass.data["shopping_list"].items[1]["id"] == beer_id
    assert hass.data["shopping_list"].items[1]["name"] == "beer"

    resp = await client.post(f"/api/shopping_list/item/{wine_id}/move_down")
    assert resp.status == 200
    assert hass.data["shopping_list"].items[0]["id"] == beer_id
    assert hass.data["shopping_list"].items[0]["name"] == "beer"
    assert hass.data["shopping_list"].items[1]["id"] == wine_id
    assert hass.data["shopping_list"].items[1]["name"] == "wine"


async def test_api_move_up_item_complex_case(hass, hass_client, sl_setup):
    """Test moving up shopping_list item API."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "apple"}}
    )

    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]
    apple_id = hass.data["shopping_list"].items[2]["id"]

    client = await hass_client()

    # Mark wine as completed.
    resp = await client.post(
        f"/api/shopping_list/item/{wine_id}", json={"complete": True}
    )

    # The item apple should be moved from index 2 all the way up to index 0.
    resp = await client.post(f"/api/shopping_list/item/{apple_id}/move_up")
    assert resp.status == 200
    assert hass.data["shopping_list"].items[0]["id"] == apple_id
    assert hass.data["shopping_list"].items[0]["name"] == "apple"
    assert hass.data["shopping_list"].items[1]["id"] == beer_id
    assert hass.data["shopping_list"].items[1]["name"] == "beer"
    assert hass.data["shopping_list"].items[2]["id"] == wine_id
    assert hass.data["shopping_list"].items[2]["name"] == "wine"


async def test_api_move_down_item_complex_case(hass, hass_client, sl_setup):
    """Test moving down shopping_list item API."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "apple"}}
    )

    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]
    apple_id = hass.data["shopping_list"].items[2]["id"]

    client = await hass_client()

    # Mark wine as completed.
    resp = await client.post(
        f"/api/shopping_list/item/{wine_id}", json={"complete": True}
    )

    # The item beer should be moved from index 0 all the way down to index 2.
    resp = await client.post(f"/api/shopping_list/item/{beer_id}/move_down")
    assert resp.status == 200
    assert hass.data["shopping_list"].items[0]["id"] == wine_id
    assert hass.data["shopping_list"].items[0]["name"] == "wine"
    assert hass.data["shopping_list"].items[1]["id"] == apple_id
    assert hass.data["shopping_list"].items[1]["name"] == "apple"
    assert hass.data["shopping_list"].items[2]["id"] == beer_id
    assert hass.data["shopping_list"].items[2]["name"] == "beer"


async def test_api_move_up_down_item_fail(hass, hass_client, sl_setup):
    """Test moving up and down shopping_list item API."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )
    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]

    client = await hass_client()

    resp = await client.post("/api/shopping_list/item/BAD_ID/move_up")
    assert resp.status == 404

    resp = await client.post(f"/api/shopping_list/item/{beer_id}/move_up")
    # The item 'beer' is already at the top, api should return 400 and the list order shouldn't change.
    assert resp.status == 400
    assert hass.data["shopping_list"].items[0]["id"] == beer_id
    assert hass.data["shopping_list"].items[0]["name"] == "beer"
    assert hass.data["shopping_list"].items[1]["id"] == wine_id
    assert hass.data["shopping_list"].items[1]["name"] == "wine"

    resp = await client.post(f"/api/shopping_list/item/{wine_id}/move_down")
    # The item 'wine' is already at the top, api should return 400 and the list order shouldn't change.
    assert resp.status == 400
    assert hass.data["shopping_list"].items[0]["id"] == beer_id
    assert hass.data["shopping_list"].items[0]["name"] == "beer"
    assert hass.data["shopping_list"].items[1]["id"] == wine_id
    assert hass.data["shopping_list"].items[1]["name"] == "wine"


async def test_ws_move_up_down_item_basic(hass, hass_ws_client, sl_setup):
    """Test moving up and down shopping_list item websocket command."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )
    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]

    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 7, "type": "shopping_list/items/move_up", "item_id": wine_id}
    )
    msg = await client.receive_json()
    assert msg["success"] is True
    assert hass.data["shopping_list"].items[0]["id"] == wine_id
    assert hass.data["shopping_list"].items[0]["name"] == "wine"
    assert hass.data["shopping_list"].items[1]["id"] == beer_id
    assert hass.data["shopping_list"].items[1]["name"] == "beer"

    await client.send_json(
        {"id": 8, "type": "shopping_list/items/move_down", "item_id": wine_id}
    )
    msg = await client.receive_json()
    assert msg["success"] is True
    assert hass.data["shopping_list"].items[0]["id"] == beer_id
    assert hass.data["shopping_list"].items[0]["name"] == "beer"
    assert hass.data["shopping_list"].items[1]["id"] == wine_id
    assert hass.data["shopping_list"].items[1]["name"] == "wine"


async def test_ws_move_up_item_complex_case(hass, hass_ws_client, sl_setup):
    """Test moving up and down shopping_list item websocket command."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "apple"}}
    )

    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]
    apple_id = hass.data["shopping_list"].items[2]["id"]

    client = await hass_ws_client(hass)

    # Mark wine as completed.
    await client.send_json(
        {
            "id": 9,
            "type": "shopping_list/items/update",
            "item_id": wine_id,
            "complete": True,
        }
    )
    _ = await client.receive_json()

    # The item apple should be moved from index 2 all the way up to index 0.
    await client.send_json(
        {"id": 10, "type": "shopping_list/items/move_up", "item_id": apple_id}
    )
    msg = await client.receive_json()
    assert msg["success"] is True
    assert hass.data["shopping_list"].items[0]["id"] == apple_id
    assert hass.data["shopping_list"].items[0]["name"] == "apple"
    assert hass.data["shopping_list"].items[1]["id"] == beer_id
    assert hass.data["shopping_list"].items[1]["name"] == "beer"
    assert hass.data["shopping_list"].items[2]["id"] == wine_id
    assert hass.data["shopping_list"].items[2]["name"] == "wine"


async def test_ws_move_down_item_complex_case(hass, hass_ws_client, sl_setup):
    """Test the API."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "apple"}}
    )

    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]
    apple_id = hass.data["shopping_list"].items[2]["id"]

    client = await hass_ws_client(hass)

    # Mark wine as completed.
    await client.send_json(
        {
            "id": 11,
            "type": "shopping_list/items/update",
            "item_id": wine_id,
            "complete": True,
        }
    )
    _ = await client.receive_json()

    # The item beer should be moved from index 0 all the way down to index 2.
    await client.send_json(
        {"id": 12, "type": "shopping_list/items/move_down", "item_id": beer_id}
    )
    msg = await client.receive_json()
    assert msg["success"] is True
    assert hass.data["shopping_list"].items[0]["id"] == wine_id
    assert hass.data["shopping_list"].items[0]["name"] == "wine"
    assert hass.data["shopping_list"].items[1]["id"] == apple_id
    assert hass.data["shopping_list"].items[1]["name"] == "apple"
    assert hass.data["shopping_list"].items[2]["id"] == beer_id
    assert hass.data["shopping_list"].items[2]["name"] == "beer"


async def test_ws_move_up_down_item_fail(hass, hass_ws_client, sl_setup):
    """Test moving up and down shopping_list item websocket command."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )
    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]

    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 13, "type": "shopping_list/items/move_up", "item_id": "BAD_ID"}
    )
    msg = await client.receive_json()
    assert msg["success"] is False

    await client.send_json(
        {"id": 14, "type": "shopping_list/items/move_up", "item_id": beer_id}
    )
    msg = await client.receive_json()
    # The item 'beer' is already at the top, the ws message should be failure and the list order should be the same.
    assert msg["success"] is False
    assert hass.data["shopping_list"].items[0]["id"] == beer_id
    assert hass.data["shopping_list"].items[0]["name"] == "beer"
    assert hass.data["shopping_list"].items[1]["id"] == wine_id
    assert hass.data["shopping_list"].items[1]["name"] == "wine"

    await client.send_json(
        {"id": 15, "type": "shopping_list/items/move_down", "item_id": wine_id}
    )
    msg = await client.receive_json()
    # The item 'beer' is already at the top, the ws message should be failure and the list order should be the same.
    assert msg["success"] is False
    assert hass.data["shopping_list"].items[0]["id"] == beer_id
    assert hass.data["shopping_list"].items[0]["name"] == "beer"
    assert hass.data["shopping_list"].items[1]["id"] == wine_id
    assert hass.data["shopping_list"].items[1]["name"] == "wine"
