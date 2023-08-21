"""Test Smart Home HTTP endpoints."""
from http import HTTPStatus
import json
from typing import Any

import pytest

from homeassistant.components.alexa import DOMAIN, smart_home
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .test_common import get_new_request

from tests.typing import ClientSessionGenerator


async def do_http_discovery(config, hass: HomeAssistant, hass_client):
    """Submit a request to the Smart Home HTTP API."""
    await async_setup_component(hass, DOMAIN, config)
    http_client = await hass_client()

    request = get_new_request("Alexa.Discovery", "Discover")
    response = await http_client.post(
        smart_home.SMART_HOME_HTTP_ENDPOINT,
        data=json.dumps(request),
        headers={"content-type": CONTENT_TYPE_JSON},
    )
    return response


@pytest.mark.parametrize(
    "config",
    [
        {"alexa": {"smart_home": None}},
        {
            "alexa": {
                "smart_home": {
                    "client_id": "someclientid",
                    "client_secret": "verysecret",
                }
            }
        },
    ],
)
async def test_http_api(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, config: dict[str, Any]
) -> None:
    """With `smart_home:` HTTP API is exposed."""
    response = await do_http_discovery(config, hass, hass_client)
    response_data = await response.json()

    # Here we're testing just the HTTP view glue -- details of discovery are
    # covered in other tests.
    assert response_data["event"]["header"]["name"] == "Discover.Response"


async def test_http_api_disabled(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Without `smart_home:`, the HTTP API is disabled."""
    config = {"alexa": {}}
    response = await do_http_discovery(config, hass, hass_client)

    assert response.status == HTTPStatus.NOT_FOUND
