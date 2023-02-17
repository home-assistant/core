"""Tests for the system health component init."""
import asyncio
from unittest.mock import AsyncMock, Mock, patch

from aiohttp.client_exceptions import ClientError

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import get_system_health_info, mock_platform
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator


async def gather_system_health_info(hass, hass_ws_client):
    """Gather all info."""
    client = await hass_ws_client(hass)

    resp = await client.send_json({"id": 6, "type": "system_health/info"})

    # Confirm subscription
    resp = await client.receive_json()
    assert resp["success"]

    data = {}

    # Get initial data
    resp = await client.receive_json()
    assert resp["event"]["type"] == "initial"
    data = resp["event"]["data"]

    while True:
        resp = await client.receive_json()
        event = resp["event"]

        if event["type"] == "finish":
            break

        assert event["type"] == "update"

        if event["success"]:
            data[event["domain"]]["info"][event["key"]] = event["data"]
        else:
            data[event["domain"]]["info"][event["key"]] = event["error"]

    return data


async def test_info_endpoint_return_info(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that the info endpoint works."""
    assert await async_setup_component(hass, "homeassistant", {})

    with patch(
        "homeassistant.components.homeassistant.system_health.system_health_info",
        return_value={"hello": True},
    ):
        assert await async_setup_component(hass, "system_health", {})

    data = await gather_system_health_info(hass, hass_ws_client)

    assert len(data) == 1
    data = data["homeassistant"]
    assert data == {"info": {"hello": True}}


async def test_info_endpoint_register_callback(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that the info endpoint allows registering callbacks."""

    async def mock_info(hass):
        return {"storage": "YAML"}

    hass.components.system_health.async_register_info("lovelace", mock_info)
    assert await async_setup_component(hass, "system_health", {})
    data = await gather_system_health_info(hass, hass_ws_client)

    assert len(data) == 1
    data = data["lovelace"]
    assert data == {"info": {"storage": "YAML"}}

    # Test our test helper works
    assert await get_system_health_info(hass, "lovelace") == {"storage": "YAML"}


async def test_info_endpoint_register_callback_timeout(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that the info endpoint timing out."""

    async def mock_info(hass):
        raise asyncio.TimeoutError

    hass.components.system_health.async_register_info("lovelace", mock_info)
    assert await async_setup_component(hass, "system_health", {})
    data = await gather_system_health_info(hass, hass_ws_client)

    assert len(data) == 1
    data = data["lovelace"]
    assert data == {"info": {"error": {"type": "failed", "error": "timeout"}}}


async def test_info_endpoint_register_callback_exc(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that the info endpoint requires auth."""

    async def mock_info(hass):
        raise Exception("TEST ERROR")

    hass.components.system_health.async_register_info("lovelace", mock_info)
    assert await async_setup_component(hass, "system_health", {})
    data = await gather_system_health_info(hass, hass_ws_client)

    assert len(data) == 1
    data = data["lovelace"]
    assert data == {"info": {"error": {"type": "failed", "error": "unknown"}}}


async def test_platform_loading(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test registering via platform."""
    aioclient_mock.get("http://example.com/status", text="")
    aioclient_mock.get("http://example.com/status_fail", exc=ClientError)
    aioclient_mock.get("http://example.com/timeout", exc=asyncio.TimeoutError)
    hass.config.components.add("fake_integration")
    mock_platform(
        hass,
        "fake_integration.system_health",
        Mock(
            async_register=lambda hass, register: register.async_register_info(
                AsyncMock(
                    return_value={
                        "hello": "info",
                        "server_reachable": system_health.async_check_can_reach_url(
                            hass, "http://example.com/status"
                        ),
                        "server_fail_reachable": system_health.async_check_can_reach_url(
                            hass,
                            "http://example.com/status_fail",
                            more_info="http://more-info-url.com",
                        ),
                        "server_timeout": system_health.async_check_can_reach_url(
                            hass,
                            "http://example.com/timeout",
                            more_info="http://more-info-url.com",
                        ),
                        "async_crash": AsyncMock(side_effect=ValueError)(),
                    }
                ),
                "/config/fake_integration",
            )
        ),
    )

    assert await async_setup_component(hass, "system_health", {})
    data = await gather_system_health_info(hass, hass_ws_client)

    assert data["fake_integration"] == {
        "info": {
            "hello": "info",
            "server_reachable": "ok",
            "server_fail_reachable": {
                "type": "failed",
                "error": "unreachable",
                "more_info": "http://more-info-url.com",
            },
            "server_timeout": {
                "type": "failed",
                "error": "timeout",
                "more_info": "http://more-info-url.com",
            },
            "async_crash": {
                "type": "failed",
                "error": "unknown",
            },
        },
        "manage_url": "/config/fake_integration",
    }
