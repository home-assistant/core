"""Test shopping list component."""
import asyncio
from unittest.mock import patch

import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.helpers import intent


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
def test_api_get_all(hass, test_client):
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
    assert len(data) == 2
    assert data[0]['name'] == 'beer'
    assert not data[0]['complete']
    assert data[1]['name'] == 'wine'
    assert not data[1]['complete']


@asyncio.coroutine
def test_api_update(hass, test_client):
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

    client = yield from test_client(hass.http.app)
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


@asyncio.coroutine
def test_api_update_fails(hass, test_client):
    """Test the API."""
    yield from async_setup_component(hass, 'shopping_list', {})

    yield from intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'beer'}}
    )

    client = yield from test_client(hass.http.app)
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


@asyncio.coroutine
def test_api_clear_completed(hass, test_client):
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

    client = yield from test_client(hass.http.app)

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


@asyncio.coroutine
def test_api_create(hass, test_client):
    """Test the API."""
    yield from async_setup_component(hass, 'shopping_list', {})

    client = yield from test_client(hass.http.app)
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
def test_api_create_fail(hass, test_client):
    """Test the API."""
    yield from async_setup_component(hass, 'shopping_list', {})

    client = yield from test_client(hass.http.app)
    resp = yield from client.post('/api/shopping_list/item', json={
        'name': 1234
    })

    assert resp.status == 400
    assert len(hass.data['shopping_list'].items) == 0
