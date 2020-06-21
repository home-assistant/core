"""Test aiohttp request helper."""

from homeassistant.util import aiohttp


async def test_request_json():
    """Test a JSON request."""
    request = aiohttp.MockRequest(b'{"hello": 2}', mock_source="test")
    assert request.status == 200
    assert await request.json() == {"hello": 2}


async def test_request_text():
    """Test a JSON request."""
    request = aiohttp.MockRequest(b"hello", status=201, mock_source="test")
    assert request.status == 201
    assert await request.text() == "hello"


async def test_request_post_query():
    """Test a JSON request."""
    request = aiohttp.MockRequest(
        b"hello=2&post=true", query_string="get=true", method="POST", mock_source="test"
    )
    assert request.method == "POST"
    assert await request.post() == {"hello": "2", "post": "true"}
    assert request.query == {"get": "true"}
