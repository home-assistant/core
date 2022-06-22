"""Test Smart Home HTTP endpoints."""
from http import HTTPStatus
import json

from homeassistant.components.alexa import DOMAIN, smart_home_http
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.setup import async_setup_component

from .test_common import get_new_request


async def do_http_discovery(config, hass, hass_client):
    """Submit a request to the Smart Home HTTP API."""
    await async_setup_component(hass, DOMAIN, config)
    http_client = await hass_client()

    request = get_new_request("Alexa.Discovery", "Discover")
    response = await http_client.post(
        smart_home_http.SMART_HOME_HTTP_ENDPOINT,
        data=json.dumps(request),
        headers={"content-type": CONTENT_TYPE_JSON},
    )
    return response


async def test_http_api(hass, hass_client):
    """With `smart_home:` HTTP API is exposed."""
    config = {"alexa": {"smart_home": None}}

    response = await do_http_discovery(config, hass, hass_client)
    response_data = await response.json()

    # Here we're testing just the HTTP view glue -- details of discovery are
    # covered in other tests.
    assert response_data["event"]["header"]["name"] == "Discover.Response"


async def test_http_api_disabled(hass, hass_client):
    """Without `smart_home:`, the HTTP API is disabled."""
    config = {"alexa": {}}
    response = await do_http_discovery(config, hass, hass_client)

    assert response.status == HTTPStatus.NOT_FOUND
