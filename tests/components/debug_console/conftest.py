"""Fixtures for the Debug console tests."""

from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from typing import Any

from aiohttp.test_utils import make_mocked_request
from aiohttp.web import Request
import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser
from pytest_homeassistant.typing import MockHAClientWebSocket, WebSocketGenerator

from homeassistant.auth.models import RefreshToken
from homeassistant.components.debug_console.const import (
    CONF_WARNING_ACCEPTED,
    DOMAIN,
    WARNING_VERSION,
)
from homeassistant.components.http import (
    KEY_AUTHENTICATED,
    KEY_HASS_REFRESH_TOKEN_ID,
    KEY_HASS_USER,
    current_request,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

type MCPRequestScope = Callable[[RefreshToken], AbstractContextManager[Request]]


@pytest.fixture
async def mcp_refresh_token(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> RefreshToken:
    """Return an actual credential for an external administrator client."""
    return await hass.auth.async_create_refresh_token(
        hass_admin_user, "https://agent.example/"
    )


@pytest.fixture
def mcp_request_scope(hass: HomeAssistant) -> MCPRequestScope:
    """Provide the authenticated request context that MCP passes to LLM tools."""

    @contextmanager
    def request_scope(token: RefreshToken) -> Generator[Request]:
        request = make_mocked_request(
            "POST",
            "/api/mcp",
            headers={
                "Authorization": f"Bearer {hass.auth.async_create_access_token(token)}"
            },
        )
        request[KEY_AUTHENTICATED] = True
        request[KEY_HASS_USER] = token.user
        request[KEY_HASS_REFRESH_TOKEN_ID] = token.id
        scope_token = current_request.set(request)
        try:
            yield request
        finally:
            current_request.reset(scope_token)

    return request_scope


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, hass_storage: dict[str, Any], hass_admin_user: MockUser
) -> None:
    """Set up the Debug console, with the warning accepted by the admin."""
    hass_storage[DOMAIN] = {
        "version": 1,
        "key": DOMAIN,
        "data": {
            CONF_WARNING_ACCEPTED: {
                hass_admin_user.id: {
                    "version": WARNING_VERSION,
                    "accepted_at": "2026-01-01T00:00:00+00:00",
                }
            }
        },
    }
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})


@pytest.fixture
async def websocket_client(
    hass: HomeAssistant,
    setup_integration: None,
    hass_ws_client: WebSocketGenerator,
) -> MockHAClientWebSocket:
    """Create a websocket client, with the Debug console set up."""
    return await hass_ws_client(hass)


@pytest.fixture
def mcp_read_only() -> bool:
    """Return whether the MCP server exposes only read-only tools."""
    return False


@pytest.fixture
async def setup_mcp_server(hass: HomeAssistant, mcp_read_only: bool) -> None:
    """Expose the Debug console tools over MCP without granting consent."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    assert await async_setup_component(hass, "homeassistant", {})
    entry = MockConfigEntry(
        domain="mcp_server",
        data={
            "all_llm_apis": False,
            CONF_LLM_HASS_API: [llm.LLM_API_HOME_ASSISTANT],
            "require_admin": True,
            "read_only": mcp_read_only,
        },
        minor_version=4,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
