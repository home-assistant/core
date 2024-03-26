"""Test aiohttp request helper."""

from aiohttp import web

from homeassistant.util import aiohttp


async def test_request_json() -> None:
    """Test a JSON request."""
    request = aiohttp.MockRequest(b'{"hello": 2}', mock_source="test")
    assert request.status == 200
    assert await request.json() == {"hello": 2}


async def test_request_text() -> None:
    """Test bytes in request."""
    request = aiohttp.MockRequest(b"hello", status=201, mock_source="test")
    assert request.body_exists
    assert request.status == 201
    assert await request.text() == "hello"


async def test_request_body_exists() -> None:
    """Test body exists."""
    request = aiohttp.MockRequest(b"", mock_source="test")
    assert not request.body_exists


async def test_request_post_query() -> None:
    """Test a JSON request."""
    request = aiohttp.MockRequest(
        b"hello=2&post=true", query_string="get=true", method="POST", mock_source="test"
    )
    assert request.method == "POST"
    assert await request.post() == {"hello": "2", "post": "true"}
    assert request.query == {"get": "true"}


def test_serialize_text() -> None:
    """Test serializing a text response."""
    response = web.Response(status=201, text="Hello")
    assert aiohttp.serialize_response(response) == {
        "status": 201,
        "body": "Hello",
        "headers": {"Content-Type": "text/plain; charset=utf-8"},
    }


def test_serialize_body_str() -> None:
    """Test serializing a response with a str as body."""
    response = web.Response(status=201, body="Hello")
    assert aiohttp.serialize_response(response) == {
        "status": 201,
        "body": "Hello",
        "headers": {"Content-Type": "text/plain; charset=utf-8"},
    }


def test_serialize_body_None() -> None:
    """Test serializing a response with a str as body."""
    response = web.Response(status=201, body=None)
    assert aiohttp.serialize_response(response) == {
        "status": 201,
        "body": None,
        "headers": {},
    }


def test_serialize_body_bytes() -> None:
    """Test serializing a response with a str as body."""
    response = web.Response(status=201, body=b"Hello")
    assert aiohttp.serialize_response(response) == {
        "status": 201,
        "body": "Hello",
        "headers": {},
    }


def test_serialize_json() -> None:
    """Test serializing a JSON response."""
    response = web.json_response({"how": "what"})
    assert aiohttp.serialize_response(response) == {
        "status": 200,
        "body": '{"how": "what"}',
        "headers": {"Content-Type": "application/json; charset=utf-8"},
    }
