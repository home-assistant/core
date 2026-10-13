"""Test Smart Home HTTP endpoints."""

from http import HTTPStatus
import json
import logging
from typing import Any

from aiohttp import ClientResponse
import pytest

from homeassistant.components.alexa import DOMAIN, smart_home
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .test_common import get_new_request

from tests.typing import ClientSessionGenerator


async def do_http_discovery(
    config: dict[str, Any], hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> ClientResponse:
    """Submit a request to the Smart Home HTTP API."""
    await async_setup_component(hass, DOMAIN, config)
    http_client = await hass_client()

    request = get_new_request("Alexa.Discovery", "Discover")
    return await http_client.post(
        smart_home.SMART_HOME_HTTP_ENDPOINT,
        data=json.dumps(request),
        headers={"content-type": CONTENT_TYPE_JSON},
    )


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
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    hass_client: ClientSessionGenerator,
    config: dict[str, Any],
) -> None:
    """With `smart_home:` HTTP API is exposed and debug log is redacted."""
    with caplog.at_level(logging.DEBUG):
        response = await do_http_discovery(config, hass, hass_client)
        response_data = await response.json()
        assert "'correlationToken': '**REDACTED**'" in caplog.text

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


@pytest.mark.parametrize(
    ("endpoint_id", "logged_entity_id"),
    [
        pytest.param("light#kitchen", "light.kitchen", id="string"),
        pytest.param(123, "123", id="non_string"),
    ],
)
async def test_http_api_logs_entity_id(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    hass_client: ClientSessionGenerator,
    endpoint_id: str | int,
    logged_entity_id: str,
) -> None:
    """Test the entity ID is logged and an unknown endpoint returns an error."""
    await async_setup_component(hass, DOMAIN, {"alexa": {"smart_home": None}})
    http_client = await hass_client()
    request = get_new_request("Alexa.PowerController", "TurnOn", "light#kitchen")
    request["directive"]["endpoint"]["endpointId"] = endpoint_id

    with caplog.at_level(logging.DEBUG):
        response = await http_client.post(
            smart_home.SMART_HOME_HTTP_ENDPOINT,
            data=json.dumps(request),
            headers={"content-type": CONTENT_TYPE_JSON},
        )
        response_data = await response.json()

    assert (
        f"Received Alexa Smart Home request for entity {logged_entity_id}:"
        in caplog.text
    )
    assert response_data["event"]["header"]["name"] == "ErrorResponse"
    assert response_data["event"]["payload"]["type"] == "NO_SUCH_ENDPOINT"
