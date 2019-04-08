"""Test shopping list component."""
import asyncio
from unittest.mock import patch

import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.helpers import intent
from homeassistant.components.websocket_api.const import TYPE_RESULT


@pytest.fixture(autouse=True)
def mock_shopping_list_io():
    """Stub out the persistence."""
    with patch('homeassistant.components.shopping_list.ShoppingData.save'), \
            patch('homeassistant.components.shopping_list.'
                  'ShoppingData.async_load'):
        yield


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
        "These are the top 3 items on your shopping list: soda, wine, beer"


@asyncio.coroutine
def test_deprecated_api_get_all(hass, hass_client):
    """Test the API."""
    yield from async_setup_component(hass, 'shopping_list', {})

    yield from intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'beer'}}
    )
    yield from intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'wine'}}
    )

    client = yield from hass_client()
    resp = yield from client.get('/api/shopping_list')

    assert resp.status == 200
    data = yield from resp.json()
    assert len(data) == 2
    assert data[0]['name'] == 'beer'
    assert not data[0]['complete']
    assert data[1]['name'] == 'wine'
    assert not data[1]['complete']


async def test_ws_get_items(hass, hass_ws_client):
    """Test get shopping_list items websocket command."""
    await async_setup_component(hass, 'shopping_list', {})

    await intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'beer'}}
    )
    await intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'wine'}}
    )

    client = await hass_ws_client(hass)

    await client.send_json({
        'id': 5,
        'type': 'shopping_list/items',
    })
    msg = await client.receive_json()
    assert msg['success'] is True

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    data = msg['result']
    assert len(data) == 2
    assert data[0]['name'] == 'beer'
    assert not data[0]['complete']
    assert data[1]['name'] == 'wine'
    assert not data[1]['complete']


@asyncio.coroutine
def test_deprecated_api_update(hass, hass_client):
    """Test the API."""
    yield from async_setup_component(hass, 'shopping_list', {})

    yield from intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'beer'}}
    )
    yield from intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'wine'}}
    )

    beer_id = hass.data['shopping_list'].items[0]['id']
    wine_id = hass.data['shopping_list'].items[1]['id']

    client = yield from hass_client()
    resp = yield from client.post(
        '/api/shopping_list/item/{}'.format(beer_id), json={
            'name': 'soda'
        })

    assert resp.status == 200
    data = yield from resp.json()
    assert data == {
        'id': beer_id,
        'name': 'soda',
        'complete': False
    }

    resp = yield from client.post(
        '/api/shopping_list/item/{}'.format(wine_id), json={
            'complete': True
        })

    assert resp.status == 200
    data = yield from resp.json()
    assert data == {
        'id': wine_id,
        'name': 'wine',
        'complete': True
    }

    beer, wine = hass.data['shopping_list'].items
    assert beer == {
        'id': beer_id,
        'name': 'soda',
        'complete': False
    }
    assert wine == {
        'id': wine_id,
        'name': 'wine',
        'complete': True
    }


async def test_ws_update_item(hass, hass_ws_client):
    """Test update shopping_list item websocket command."""
    await async_setup_component(hass, 'shopping_list', {})
    await intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'beer'}}
    )
    await intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'wine'}}
    )

    beer_id = hass.data['shopping_list'].items[0]['id']
    wine_id = hass.data['shopping_list'].items[1]['id']
    client = await hass_ws_client(hass)
    await client.send_json({
        'id': 5,
        'type': 'shopping_list/items/update',
        'item_id': beer_id,
        'name': 'soda'
    })
    msg = await client.receive_json()
    assert msg['success'] is True
    data = msg['result']
    assert data == {
        'id': beer_id,
        'name': 'soda',
        'complete': False
    }
    await client.send_json({
        'id': 6,
        'type': 'shopping_list/items/update',
        'item_id': wine_id,
        'complete': True
    })
    msg = await client.receive_json()
    assert msg['success'] is True
    data = msg['result']
    assert data == {
        'id': wine_id,
        'name': 'wine',
        'complete': True
    }

    beer, wine = hass.data['shopping_list'].items
    assert beer == {
        'id': beer_id,
        'name': 'soda',
        'complete': False
    }
    assert wine == {
        'id': wine_id,
        'name': 'wine',
        'complete': True
    }


@asyncio.coroutine
def test_api_update_fails(hass, hass_client):
    """Test the API."""
    yield from async_setup_component(hass, 'shopping_list', {})

    yield from intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'beer'}}
    )

    client = yield from hass_client()
    resp = yield from client.post(
        '/api/shopping_list/non_existing', json={
            'name': 'soda'
        })

    assert resp.status == 404

    beer_id = hass.data['shopping_list'].items[0]['id']
    resp = yield from client.post(
        '/api/shopping_list/item/{}'.format(beer_id), json={
            'name': 123,
        })

    assert resp.status == 400


async def test_ws_update_item_fail(hass, hass_ws_client):
    """Test failure of update shopping_list item websocket command."""
    await async_setup_component(hass, 'shopping_list', {})
    await intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'beer'}}
    )
    client = await hass_ws_client(hass)
    await client.send_json({
        'id': 5,
        'type': 'shopping_list/items/update',
        'item_id': 'non_existing',
        'name': 'soda'
    })
    msg = await client.receive_json()
    assert msg['success'] is False
    data = msg['error']
    assert data == {
        'code': 'item_not_found',
        'message': 'Item not found'
    }
    await client.send_json({
        'id': 6,
        'type': 'shopping_list/items/update',
        'name': 123,
    })
    msg = await client.receive_json()
    assert msg['success'] is False


@asyncio.coroutine
def test_deprecated_api_clear_completed(hass, hass_client):
    """Test the API."""
    yield from async_setup_component(hass, 'shopping_list', {})

    yield from intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'beer'}}
    )
    yield from intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'wine'}}
    )

    beer_id = hass.data['shopping_list'].items[0]['id']
    wine_id = hass.data['shopping_list'].items[1]['id']

    client = yield from hass_client()

    # Mark beer as completed
    resp = yield from client.post(
        '/api/shopping_list/item/{}'.format(beer_id), json={
            'complete': True
        })
    assert resp.status == 200

    resp = yield from client.post('/api/shopping_list/clear_completed')
    assert resp.status == 200

    items = hass.data['shopping_list'].items
    assert len(items) == 1

    assert items[0] == {
        'id': wine_id,
        'name': 'wine',
        'complete': False
    }


async def test_ws_clear_items(hass, hass_ws_client):
    """Test clearing shopping_list items websocket command."""
    await async_setup_component(hass, 'shopping_list', {})
    await intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'beer'}}
    )
    await intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'wine'}}
    )
    beer_id = hass.data['shopping_list'].items[0]['id']
    wine_id = hass.data['shopping_list'].items[1]['id']
    client = await hass_ws_client(hass)
    await client.send_json({
        'id': 5,
        'type': 'shopping_list/items/update',
        'item_id': beer_id,
        'complete': True
    })
    msg = await client.receive_json()
    assert msg['success'] is True
    await client.send_json({
        'id': 6,
        'type': 'shopping_list/items/clear'
    })
    msg = await client.receive_json()
    assert msg['success'] is True
    items = hass.data['shopping_list'].items
    assert len(items) == 1
    assert items[0] == {
        'id': wine_id,
        'name': 'wine',
        'complete': False
     }


@asyncio.coroutine
def test_deprecated_api_create(hass, hass_client):
    """Test the API."""
    yield from async_setup_component(hass, 'shopping_list', {})

    client = yield from hass_client()
    resp = yield from client.post('/api/shopping_list/item', json={
        'name': 'soda'
    })

    assert resp.status == 200
    data = yield from resp.json()
    assert data['name'] == 'soda'
    assert data['complete'] is False

    items = hass.data['shopping_list'].items
    assert len(items) == 1
    assert items[0]['name'] == 'soda'
    assert items[0]['complete'] is False


@asyncio.coroutine
def test_deprecated_api_create_fail(hass, hass_client):
    """Test the API."""
    yield from async_setup_component(hass, 'shopping_list', {})

    client = yield from hass_client()
    resp = yield from client.post('/api/shopping_list/item', json={
        'name': 1234
    })

    assert resp.status == 400
    assert len(hass.data['shopping_list'].items) == 0


async def test_ws_add_item(hass, hass_ws_client):
    """Test adding shopping_list item websocket command."""
    await async_setup_component(hass, 'shopping_list', {})
    client = await hass_ws_client(hass)
    await client.send_json({
        'id': 5,
        'type': 'shopping_list/items/add',
        'name': 'soda',
    })
    msg = await client.receive_json()
    assert msg['success'] is True
    data = msg['result']
    assert data['name'] == 'soda'
    assert data['complete'] is False
    items = hass.data['shopping_list'].items
    assert len(items) == 1
    assert items[0]['name'] == 'soda'
    assert items[0]['complete'] is False


async def test_ws_add_item_fail(hass, hass_ws_client):
    """Test adding shopping_list item failure websocket command."""
    await async_setup_component(hass, 'shopping_list', {})
    client = await hass_ws_client(hass)
    await client.send_json({
        'id': 5,
        'type': 'shopping_list/items/add',
        'name': 123,
    })
    msg = await client.receive_json()
    assert msg['success'] is False
    assert len(hass.data['shopping_list'].items) == 0
