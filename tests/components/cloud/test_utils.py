"""Test aiohttp request helper."""
from aiohttp import web

from homeassistant.components.cloud import utils


def test_serialize_text():
    """Test serializing a text response."""
    response = web.Response(status=201, text='Hello')
    assert utils.aiohttp_serialize_response(response) == {
        'status': 201,
        'body': 'Hello',
        'headers': {'Content-Type': 'text/plain; charset=utf-8'},
    }


def test_serialize_json():
    """Test serializing a JSON response."""
    response = web.json_response({"how": "what"})
    assert utils.aiohttp_serialize_response(response) == {
        'status': 200,
        'body': '{"how": "what"}',
        'headers': {'Content-Type': 'application/json; charset=utf-8'},
    }
