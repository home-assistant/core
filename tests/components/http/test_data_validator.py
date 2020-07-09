"""Test data validator decorator."""
from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator

from tests.async_mock import Mock


async def get_client(aiohttp_client, validator):
    """Generate a client that hits a view decorated with validator."""
    app = web.Application()
    app["hass"] = Mock(is_stopping=False)

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
    assert resp.status == 200

    resp = await client.post("/", json={"test": 100})
    assert resp.status == 400

    resp = await client.post("/")
    assert resp.status == 400


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
    assert resp.status == 200

    resp = await client.post("/", json={"test": 100})
    assert resp.status == 400

    resp = await client.post("/")
    assert resp.status == 200
