"""Tests for the HTTP integration WebSocket configuration API."""

from typing import Any
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.http.storage import USER_CONFIG_STORAGE_KEY
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
def disable_http_server(socket_enabled: None) -> None:
    """Allow the HTTP server to start."""
    return


@pytest.fixture
async def setup_http(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Set up the HTTP integration without any pre-existing YAML."""
    with patch("asyncio.BaseEventLoop.create_server", return_value=Mock()):
        assert await async_setup_component(hass, "http", {})
        await hass.async_start()
        await hass.async_block_till_done()


async def test_get_returns_stored_config(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    setup_http: None,
) -> None:
    """A get call returns the currently stored config."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "http/config/get"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["config"]["server_port"] == 8123


async def test_update_persists_valid_config(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    setup_http: None,
) -> None:
    """A valid update is persisted and returned."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "http/config/update",
            "config": {
                "server_port": 8124,
                "cors_allowed_origins": ["https://updated.example"],
            },
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["config"]["server_port"] == 8124
    assert hass_storage[USER_CONFIG_STORAGE_KEY]["data"]["server_port"] == 8124


async def test_update_merges_partial_config(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    setup_http: None,
) -> None:
    """A partial update keeps previously stored keys."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "http/config/update",
            "config": {"cors_allowed_origins": ["https://first.example"]},
        }
    )
    await client.receive_json()

    await client.send_json_auto_id(
        {"type": "http/config/update", "config": {"server_port": 8125}}
    )
    response = await client.receive_json()

    assert response["success"]
    stored = hass_storage[USER_CONFIG_STORAGE_KEY]["data"]
    assert stored["server_port"] == 8125
    assert stored["cors_allowed_origins"] == ["https://first.example"]


async def test_update_rejects_inclusive_proxy_violation(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    setup_http: None,
) -> None:
    """use_x_forwarded_for without trusted_proxies is rejected."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "http/config/update",
            "config": {"use_x_forwarded_for": True},
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


async def test_update_rejects_invalid_ssl_path(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    setup_http: None,
) -> None:
    """A non-existent SSL path is rejected by the schema."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "http/config/update",
            "config": {"ssl_certificate": "/path/does/not/exist.pem"},
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"
    assert "ssl_certificate" in response["error"]["message"]


async def test_get_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    setup_http: None,
) -> None:
    """A non-admin connection cannot read the config."""
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json_auto_id({"type": "http/config/get"})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"


async def test_update_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    setup_http: None,
) -> None:
    """A non-admin connection cannot update the config."""
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json_auto_id(
        {"type": "http/config/update", "config": {"server_port": 8124}}
    )
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"
