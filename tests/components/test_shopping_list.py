"""Test shopping list component."""
import asyncio

from homeassistant.bootstrap import async_setup_component
from homeassistant.helpers import intent


@asyncio.coroutine
def test_add_item(hass):
    """Test adding an item intent."""
    yield from async_setup_component(hass, 'shopping_list', {})

    response = yield from intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'beer'}}
    )

    assert response.speech['plain']['speech'] == \
        "I've added beer to your shopping list"


@asyncio.coroutine
def test_recent_items_intent(hass):
    """Test recent items."""
    yield from async_setup_component(hass, 'shopping_list', {})

    yield from intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'beer'}}
    )
    yield from intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'wine'}}
    )
    yield from intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'soda'}}
    )

    response = yield from intent.async_handle(
        hass, 'test', 'HassShoppingListLastItems'
    )

    assert response.speech['plain']['speech'] == \
        "These are the top 5 items in your shopping list: soda, wine, beer"


@asyncio.coroutine
def test_api(hass, test_client):
    """Test the API."""
    yield from async_setup_component(hass, 'shopping_list', {})

    yield from intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'beer'}}
    )
    yield from intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'wine'}}
    )

    client = yield from test_client(hass.http.app)
    resp = yield from client.get('/api/shopping_list')

    assert resp.status == 200
    data = yield from resp.json()
    assert data == ['beer', 'wine']
