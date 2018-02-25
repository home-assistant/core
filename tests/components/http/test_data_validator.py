"""Test data validator decorator."""
import asyncio
from unittest.mock import Mock

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator


@asyncio.coroutine
def get_client(test_client, validator):
    """Generate a client that hits a view decorated with validator."""
    app = web.Application()
    app['hass'] = Mock(is_running=True)

    class TestView(HomeAssistantView):
        url = '/'
        name = 'test'
        requires_auth = False

        @asyncio.coroutine
        @validator
        def post(self, request, data):
            """Test method."""
            return b''

    TestView().register(app.router)
    client = yield from test_client(app)
    return client


@asyncio.coroutine
def test_validator(test_client):
    """Test the validator."""
    client = yield from get_client(
        test_client, RequestDataValidator(vol.Schema({
            vol.Required('test'): str
        })))

    resp = yield from client.post('/', json={
        'test': 'bla'
    })
    assert resp.status == 200

    resp = yield from client.post('/', json={
        'test': 100
    })
    assert resp.status == 400

    resp = yield from client.post('/')
    assert resp.status == 400


@asyncio.coroutine
def test_validator_allow_empty(test_client):
    """Test the validator with empty data."""
    client = yield from get_client(
        test_client, RequestDataValidator(vol.Schema({
            # Although we allow empty, our schema should still be able
            # to validate an empty dict.
            vol.Optional('test'): str
        }), allow_empty=True))

    resp = yield from client.post('/', json={
        'test': 'bla'
    })
    assert resp.status == 200

    resp = yield from client.post('/', json={
        'test': 100
    })
    assert resp.status == 400

    resp = yield from client.post('/')
    assert resp.status == 200
