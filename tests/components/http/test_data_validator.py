"""Test data validator decorator."""
from http import HTTPStatus
from unittest.mock import Mock

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator


async def get_client(aiohttp_client, validator):
    """Generate a client that hits a view decorated with validator."""
    app = web.Application()
    app["hass"] = Mock(is_stopping=False)
    app["allow_configured_cors"] = lambda _: None

    class TestView(HomeAssistantView):
        url = "/"
        name = "test"
        requires_auth = False

        @validator
        async def post(self, request, data):
            """Test method."""
            return b""

    TestView().register(app, app.router)
    client = await aiohttp_client(app)
    return client


async def test_validator(aiohttp_client):
    """Test the validator."""
    client = await get_client(
        aiohttp_client, RequestDataValidator(vol.Schema({vol.Required("test"): str}))
    )

    resp = await client.post("/", json={"test": "bla"})
    assert resp.status == HTTPStatus.OK

    resp = await client.post("/", json={"test": 100})
    assert resp.status == HTTPStatus.BAD_REQUEST

    resp = await client.post("/")
    assert resp.status == HTTPStatus.BAD_REQUEST


async def test_validator_allow_empty(aiohttp_client):
    """Test the validator with empty data."""
    client = await get_client(
        aiohttp_client,
        RequestDataValidator(
            vol.Schema(
                {
                    # Although we allow empty, our schema should still be able
                    # to validate an empty dict.
                    vol.Optional("test"): str
                }
            ),
            allow_empty=True,
        ),
    )

    resp = await client.post("/", json={"test": "bla"})
    assert resp.status == HTTPStatus.OK

    resp = await client.post("/", json={"test": 100})
    assert resp.status == HTTPStatus.BAD_REQUEST

    resp = await client.post("/")
    assert resp.status == HTTPStatus.OK
