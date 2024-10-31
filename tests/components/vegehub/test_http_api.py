"""Unit tests for VegeHub integration's http_api.py."""

from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components import http
from homeassistant.components.vegehub.const import API_PATH, DOMAIN
from homeassistant.components.vegehub.http_api import async_setup
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


@pytest.fixture
async def mock_vegehub_view(hass: HomeAssistant, hass_client: ClientSessionGenerator):
    """Fixture to set up VegeHub HTTP endpoint."""
    hass.http = hass.http or http.HomeAssistantHTTP(
        hass,
        ssl_certificate=None,
        ssl_peer_certificate=None,
        ssl_key=None,
        server_host="0.0.0.0",
        server_port=8123,
        trusted_proxies=[],
        ssl_profile=None,
    )

    await async_setup_component(hass, "http", {})
    await async_setup(hass)

    return await hass_client()


async def test_post_update_sensor(mock_vegehub_view, hass: HomeAssistant) -> None:
    """Test handling a POST request to update a sensor entity."""
    # Mock hass.data to store a fake sensor entity for testing
    entity_mock = Mock()
    entity_mock.async_update_sensor = AsyncMock()

    hass.data[DOMAIN] = {
        "vegehub_key_1": entity_mock,
    }

    response = await mock_vegehub_view.post(
        API_PATH,
        json={
            "api_key": "key",
            "sensors": [
                {
                    "slot": 1,
                    "samples": [
                        {"t": "2024-10-08T12:34:56Z", "v": 42.5},
                    ],
                }
            ],
        },
    )

    assert response.status == 200
    data = await response.json()
    assert data["status"] == "ok"
    entity_mock.async_update_sensor.assert_awaited_once_with(42.5)


async def test_post_missing_entity(mock_vegehub_view, hass: HomeAssistant) -> None:
    """Test handling a POST request for an unknown sensor entity."""
    hass.data[DOMAIN] = {}

    response = await mock_vegehub_view.post(
        API_PATH,
        json={
            "api_key": "key",
            "sensors": [
                {
                    "slot": 1,
                    "samples": [
                        {"t": "2024-10-08T12:34:56Z", "v": 50.0},
                    ],
                }
            ],
        },
    )

    assert response.status == 200
    data = await response.json()
    assert data["status"] == "ok"
    # Expecting an error log about the missing entity


@pytest.mark.asyncio
async def test_post_invalid_json(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator, mock_vegehub_view
) -> None:
    """Test the POST request with invalid JSON data."""
    hass.data[DOMAIN] = {}

    response = await mock_vegehub_view.post(API_PATH, json="Invalid JSON")

    assert response.status == 500  # Expecting a Bad Request response for invalid JSON
