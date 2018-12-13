"""Test aiohttp request helper."""
from aiohttp import web

from homeassistant.util import aiohttp


async def test_request_json():
    """Test a JSON request."""
    request = aiohttp.MockRequest(b'{"hello": 2}')
    assert request.status == 200
    assert await request.json() == {
        'hello': 2
    }


async def test_request_text():
    """Test a JSON request."""
    request = aiohttp.MockRequest(b'hello', status=201)
    assert request.status == 201
    assert await request.text() == 'hello'


async def test_request_post_query():
    """Test a JSON request."""
    request = aiohttp.MockRequest(
        b'hello=2&post=true', query_string='get=true', method='POST')
    assert request.method == 'POST'
    assert await request.post() == {
        'hello': '2',
        'post': 'true'
    }
    assert request.query == {
        'get': 'true'
    }


def test_serialize_text():
    """Test serializing a text response."""
    response = web.Response(status=201, text='Hello')
    assert aiohttp.serialize_response(response) == {
        'status': 201,
        'body': b'Hello',
        'headers': {'Content-Type': 'text/plain; charset=utf-8'},
    }


def test_serialize_json():
    """Test serializing a JSON response."""
    response = web.json_response({"how": "what"})
    assert aiohttp.serialize_response(response) == {
        'status': 200,
        'body': b'{"how": "what"}',
        'headers': {'Content-Type': 'application/json; charset=utf-8'},
    }
