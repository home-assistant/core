"""Test data validator decorator."""

from http import HTTPStatus
from unittest.mock import Mock

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.helpers.http import KEY_ALLOW_CONFIGRED_CORS

from tests.typing import ClientSessionGenerator


async def get_client(aiohttp_client, validator):
    """Generate a client that hits a view decorated with validator."""
    app = web.Application()
    app[KEY_HASS] = Mock(is_stopping=False)
    app[KEY_ALLOW_CONFIGRED_CORS] = lambda _: None

    class TestView(HomeAssistantView):
        url = "/"
        name = "test"
        requires_auth = False

        @validator
        async def post(self, request, data):
            """Test method."""
            return b""

    TestView().register(app[KEY_HASS], app, app.router)
    return await aiohttp_client(app)


async def test_validator(aiohttp_client: ClientSessionGenerator) -> None:
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


async def test_validator_allow_empty(aiohttp_client: ClientSessionGenerator) -> None:
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
