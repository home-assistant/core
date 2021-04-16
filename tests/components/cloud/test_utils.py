"""Test aiohttp request helper."""
from aiohttp import web

from homeassistant.components.cloud import utils


def test_serialize_text():
    """Test serializing a text response."""
    response = web.Response(status=201, text="Hello")
    assert utils.aiohttp_serialize_response(response) == {
        "status": 201,
        "body": "Hello",
        "headers": {"Content-Type": "text/plain; charset=utf-8"},
    }


def test_serialize_body_str():
    """Test serializing a response with a str as body."""
    response = web.Response(status=201, body="Hello")
    assert utils.aiohttp_serialize_response(response) == {
        "status": 201,
        "body": "Hello",
        "headers": {"Content-Length": "5", "Content-Type": "text/plain; charset=utf-8"},
    }


def test_serialize_body_None():
    """Test serializing a response with a str as body."""
    response = web.Response(status=201, body=None)
    assert utils.aiohttp_serialize_response(response) == {
        "status": 201,
        "body": None,
        "headers": {},
    }


def test_serialize_body_bytes():
    """Test serializing a response with a str as body."""
    response = web.Response(status=201, body=b"Hello")
    assert utils.aiohttp_serialize_response(response) == {
        "status": 201,
        "body": "Hello",
        "headers": {},
    }


def test_serialize_json():
    """Test serializing a JSON response."""
    response = web.json_response({"how": "what"})
    assert utils.aiohttp_serialize_response(response) == {
        "status": 200,
        "body": '{"how": "what"}',
        "headers": {"Content-Type": "application/json; charset=utf-8"},
    }
