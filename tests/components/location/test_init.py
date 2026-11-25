"""Tests for location based integration matching."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.location.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.generated import locations as generated_locations
from homeassistant.setup import async_setup_component

from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.fixture(autouse=True)
def mock_locations() -> Generator[None]:
    """Mock the generated locations."""
    with patch.dict(
        generated_locations.LOCATIONS,
        {"NL": ["test", "other"], "BE": ["belgian"]},
        clear=True,
    ):
        yield


async def _get_integrations(client: MockHAClientWebSocket) -> dict[str, Any]:
    """Return the integrations serving the home location."""
    await client.send_json_auto_id({"type": "location/integrations"})
    response = await client.receive_json()
    assert response["success"]
    return response["result"]


@pytest.mark.parametrize(
    ("country", "integrations"),
    [
        pytest.param("NL", {"other": ["NL"], "test": ["NL"]}, id="served_country"),
        pytest.param("DE", {}, id="unserved_country"),
        pytest.param(None, {}, id="no_country"),
    ],
)
async def test_integrations(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    country: str | None,
    integrations: dict[str, list[str]],
) -> None:
    """Test getting the integrations serving the home location."""
    hass.config.country = country
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)

    assert await _get_integrations(client) == integrations


async def test_country_updated(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the integrations follow the country of the home location."""
    hass.config.country = "NL"
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)

    assert await _get_integrations(client) == {"other": ["NL"], "test": ["NL"]}

    await hass.config.async_update(country="BE")
    assert await _get_integrations(client) == {"belgian": ["BE"]}


async def test_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test only admins can get the integrations."""
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json_auto_id({"type": "location/integrations"})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"
